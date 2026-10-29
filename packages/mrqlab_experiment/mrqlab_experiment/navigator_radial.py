"""Data-only global two-T2 navigation followed by unscaled spatial inversion.

Only exact k=0 samples enter navigation. The bounded two-component EPG model
estimates global curves, not a voxel T2 map. Late echoes are withheld from the
fit; no reference image, labels or true sample T2 enter either inverse.
"""
import numpy as np
from mrqlab_recon.echo_subspace import echo_subspace_cgls
from .tse_imaging import prepare_tse_echo_train
from .radial_tse import run_radial_tse
from .study_records import _checked_sources
from mrqlab_recon.spatial import image_quality
from .spatial_imaging import _hash


def estimate_tse_navigator(xy, samples, echo_for_sample, *, echoes, echo_spacing_s,
                           tr_s, t2_bounds_s, refocusing_angle=180.,
                           refocusing_end_angle=180., experiment=None,
                           fit_echoes=4, max_evaluations=128, max_work=20000000,
                           target_residual=1e-10, max_relative_t2_std=.05,
                           declared_sample_std=0.):
    """Fit complex DC mixtures; bounds and T1/PD are declared model priors.

    The fitted complex mixture coefficients are navigation nuisance parameters.
    They never scale the spatial inverse or its output. All model calls and
    bounded optimization attempts consume a shared deterministic work allowance.
    """
    xy=np.asarray(xy,float);data=np.asarray(samples,complex);ids=np.asarray(echo_for_sample)
    bounds=np.asarray(t2_bounds_s,float)
    if (xy.ndim!=2 or xy.shape[1]!=2 or data.ndim!=2 or not 1<=len(data)<=8 or data.shape[1]!=len(xy) or
            not np.isfinite(xy).all() or not np.isfinite(data).all()):
        raise ValueError('finite xy and centered-kz by xy complex samples required')
    if (type(echoes) is not int or type(fit_echoes) is not int or
            not 6<=echoes<=16 or not 4<=fit_echoes<=echoes-2 or
            ids.shape!=(len(xy),) or not np.issubdtype(ids.dtype,np.integer) or
            not np.isin(ids,np.arange(echoes)).all()):
        raise ValueError('at least four fit and two withheld echoes with integer sample assignments required')
    if (bounds.shape!=(2,2) or not np.isfinite(bounds).all() or
            not 1e-4<=bounds[0,0]<bounds[0,1]<bounds[1,0]<bounds[1,1]<=10):
        raise ValueError('two positive disjoint ordered T2 intervals in seconds required')
    if (type(max_evaluations) is not int or not 8<=max_evaluations<=512 or
            type(max_work) is not int or max_work<=0 or
            not np.isfinite([target_residual,max_relative_t2_std,declared_sample_std]).all() or
            not 0<target_residual<1 or not 0<max_relative_t2_std<1 or declared_sample_std<0):
        raise ValueError('bounded navigator evaluation/work and finite targets required')
    # This is exact coordinate selection, not nearest-center interpolation.
    indices=np.flatnonzero(np.all(xy==0.,axis=1))
    groups=[indices[ids[indices]==e] for e in range(echoes)]
    if any(len(g)<4 for g in groups):
        raise ValueError('at least four exact k=0 samples per echo required; even-point trajectories do not provide them')
    dc=data[len(data)//2]
    means=np.array([np.mean(dc[g]) for g in groups])
    fit=np.array([np.mean(dc[g[::2]]) for g in groups[:fit_echoes]])
    hold=np.array([np.mean(dc[g[1::2]]) for g in groups[:fit_echoes]]+
                  [np.mean(dc[g]) for g in groups[fit_echoes:]])
    if np.linalg.norm(fit)==0: raise ValueError('nonzero navigator fit signal required')
    empirical_std=float(np.sqrt(sum(np.sum(abs(dc[g]-means[e])**2) for e,g in enumerate(groups))/
                                (2*sum(len(g)-1 for g in groups))))
    sigma=max(float(declared_sample_std),empirical_std)
    repeat_relative=float(np.sqrt(sum(np.sum(abs(dc[g]-means[e])**2) for e,g in enumerate(groups)))/
                          max(np.linalg.norm(dc[indices]),np.finfo(float).tiny))
    center=bounds.mean(axis=1);half=np.diff(bounds,axis=1)[:,0]/2
    norm=float(np.linalg.norm(fit));calls=0;work=0;cache={};physical_cache={};history=[];exhausted=False

    def evaluate(x):
        nonlocal calls,work
        key=tuple(float(v) for v in x)
        if key in cache: return cache[key]
        if calls>=max_evaluations or work>=max_work: raise ValueError('navigator evaluation/work allowance exhausted')
        calls+=1
        curve=prepare_tse_echo_train(echoes=echoes,echo_spacing_s=echo_spacing_s,tr_s=tr_s,
            t2_s=center+half*x,refocusing_angle=refocusing_angle,
            refocusing_end_angle=refocusing_end_angle,experiment=experiment,max_work=max_work-work)
        cost=curve[5]+256*echoes
        if cost>max_work-work: raise ValueError('navigator EPG/least-squares work allowance exhausted')
        work+=cost;weights=curve[2]
        amplitudes=np.linalg.lstsq(weights[:,:fit_echoes].T,fit,rcond=None)[0]
        residual=(weights[:,:fit_echoes].T@amplitudes-fit)/norm
        real=np.r_[residual.real,residual.imag]
        value=(real,weights,amplitudes);cache[key]=value;physical_cache[key]=curve[3];return value

    def jacobian(x):
        columns=[]
        for k in range(2):
            delta=np.eye(2)[k]*1e-3;lo=np.maximum(-1.,x-delta);hi=np.minimum(1.,x+delta)
            columns.append((evaluate(hi)[0]-evaluate(lo)[0])/(hi[k]-lo[k]))
        return np.column_stack(columns)

    best=None
    try:
        # Multiple fixed starts, independent of sample truth or held-out data.
        for start in [np.zeros(2),np.array([-.5,-.5]),np.array([.5,.5]),np.array([-.5,.5]),np.array([.5,-.5])]:
            x=start.copy()
            for iteration in range(16):
                residual,weights,amplitudes=evaluate(x);loss=float(np.linalg.norm(residual))
                history.append(dict(start=start.tolist(),iteration=iteration,t2_s=(center+half*x).tolist(),relative_fit_residual=loss))
                if best is None or loss<best[0]: best=(loss,x.copy(),weights,amplitudes)
                if loss<1e-13: break
                jac=jacobian(x);step=np.linalg.lstsq(jac,-residual,rcond=None)[0]
                improved=False
                for factor in [1.,.5,.25,.125,.0625,.03125]:
                    trial=np.clip(x+factor*step,-1.,1.)
                    if np.linalg.norm(evaluate(trial)[0])<loss:
                        x=trial;improved=True;break
                if not improved: break
            # Keep enough allowance for the independent local sensitivity gate.
            if calls>max_evaluations-6: break
        loss,x,weights,amplitudes=best
        jac=jacobian(x)
    except ValueError:
        exhausted=True
        # A failed EPG call may already have spent its remaining allowance.
        work=max_work
        if best is None: raise
        loss,x,weights,amplitudes=best;jac=None
    fitted=center+half*x
    prediction=weights.T@amplitudes
    hold_residual=float(np.linalg.norm(prediction-hold)/max(np.linalg.norm(hold),np.finfo(float).tiny))
    singular=np.linalg.svd(jac,compute_uv=False) if jac is not None else np.zeros(2)
    identifiable=bool(singular[-1]>1e-10 and singular[-1]>singular[0]*1e-8)
    # Conditional local uncertainty from within-echo repeat noise / authored
    # acquisition noise. A numeric precision floor avoids a zero covariance.
    sigma_mean=max(sigma/np.sqrt(min(len(g[::2]) for g in groups[:fit_echoes])),norm*1e-14)
    std=np.sqrt(np.diag(np.linalg.inv(jac.T@jac)))*sigma_mean/norm*half if identifiable else None
    relative_std=float(np.max(std/fitted)) if std is not None else None
    reasons=[]
    if exhausted: reasons.append('navigator evaluation/work allowance exhausted')
    if loss>target_residual: reasons.append('fit echoes fail navigator residual target')
    if hold_residual>target_residual: reasons.append('withheld echoes/repeats fail navigator residual target')
    if not identifiable: reasons.append('two global T2 values are not locally identifiable')
    if relative_std is None or relative_std>max_relative_t2_std: reasons.append('conditional T2 uncertainty exceeds target')
    if repeat_relative>target_residual: reasons.append('within-echo center repeats fail static global-mixture assumption')
    return dict(passed=not reasons,reasons=reasons,t2_s=fitted.tolist(),t2_bounds_s=bounds.tolist(),
        t2_std_s=std.tolist() if std is not None else None,max_relative_t2_std=relative_std,
        weights=weights,mixture_coefficients=amplitudes,observed_center_means=means,prediction=prediction,
        fit_echoes=list(range(1,fit_echoes+1)),withheld_echoes=list(range(fit_echoes+1,echoes+1)),
        center_indices=indices.tolist(),fit_center_indices=[g[::2].tolist() for g in groups[:fit_echoes]],
        relative_fit_residual=loss,relative_holdout_residual=hold_residual,relative_repeat_residual=repeat_relative,
        target_residual=target_residual,empirical_sample_std=empirical_std,declared_sample_std=declared_sample_std,
        basis_physical=physical_cache[tuple(float(v) for v in x)],
        projected_jacobian_singular_values=singular.tolist(),locally_identifiable=identifiable,
        active_bounds=[bool(abs(v)>=1-1e-7) for v in x],evaluations=calls,estimated_work=work,history=history,
        navigator_hash=_hash([xy.tolist(),data.real.tolist(),data.imag.tolist(),ids.tolist()]),
        scope='two spatially homogeneous T2 classes, fixed T1/PD and exact centered-kz origin; local conditional uncertainty, not voxel mapping/global uniqueness/clinical bounds; complex DC mixture coefficients never rescale spatial images')


def run_navigator_radial_tse(labels, *, t2_bounds_s, navigator_max_work=20000000,
                             navigator_max_evaluations=128, **parameters):
    """Compare fixed and navigated inverses using the exact same acquired data.

    The existing fixed-prior chain supplies acquisition and a complete mismatch
    control. All of its acquisition/control costs remain charged. Navigation and
    a second CGLS solve spend separate reserved portions of the same scenario cap.
    """
    sources=_checked_sources();params=dict(parameters)
    if params.get('echoes',4)<6 or params.get('points',32)%2==0:
        raise ValueError('navigator design requires >=6 echoes and an explicit odd-point center-sampled trajectory')
    cap=params.get('max_work',50000000000)
    inverse_reserve=(cap-navigator_max_work)//2
    if inverse_reserve<=0: raise ValueError('cannot reserve navigator and both inverse computations')
    params['max_work']=cap-navigator_max_work-inverse_reserve
    control=run_radial_tse(labels,**params)
    fit=estimate_tse_navigator(control['coordinates'],control['samples'],control['echo_for_sample'],
        echoes=params['echoes'],echo_spacing_s=params.get('echo_spacing_s',.008),tr_s=params.get('tr_s',.4),
        t2_bounds_s=t2_bounds_s,refocusing_angle=params.get('refocusing_angle',180.),
        refocusing_end_angle=params.get('refocusing_end_angle',180.),experiment=params.get('experiment'),
        max_work=navigator_max_work,max_evaluations=navigator_max_evaluations)
    fixed=dict(image=control['image'],quality=control['quality'],validation=control['validation'],solvers=control['solvers'])
    result={**control,'navigator_fit':fit,'navigator_reconstruction_performed':False,'static_control':fixed,
        'fixed_prior_control':dict(image=control['image'],quality=control['quality'],validation=control['validation'],solvers=control['solvers']),
        'validation':{**control['validation'],'passed':False,'navigator_passed':fit['passed']},
        'provenance':{**control['provenance'],'estimated_work':control['provenance']['estimated_work']+fit['estimated_work']}}
    if fit['passed']:
        weights=fit['weights'];u,s,vh=np.linalg.svd(weights,full_matrices=False)
        if s[-1]<=s[0]*1e-10: raise ValueError('navigated EPG temporal basis is rank deficient')
        # The first operator's plans/basis are released when its solver returns;
        # retain its result buffers, not its historical peak allocation.
        retained=int(128*control['samples'].size+(256+64*params['echoes'])*np.asarray(labels).size+
                     512*len(control['timeline'])*params['echoes']+64*len(fit['history']))
        coeff,solver=echo_subspace_cgls(control['coordinates'],control['samples'],np.asarray(labels).shape,
            vh[:,control['echo_for_sample']],backend=params.get('backend','exact'),eps=params.get('nufft_eps',1e-13),
            max_iterations=params.get('inverse_max_iterations',6000),tolerance=params.get('inverse_tolerance',1e-10),
            max_work=inverse_reserve,max_memory_bytes=params.get('max_memory_bytes',134217728)-retained)
        components=((u/s[None,:])@coeff.reshape(2,-1)).reshape(control['reference_components'].shape)
        echo_images=(weights.T@components.reshape(2,-1)).reshape(control['reference_echoes'].shape)
        image=echo_images[params.get('display_echo',2)-1]
        quality=image_quality(control['reference'],image,params.get('target_image_error',1e-6))
        component_error=float(np.linalg.norm(components-control['reference_components'])/np.linalg.norm(control['reference_components']))
        lab=np.asarray(labels);contrast=float(abs(np.mean(abs(image[lab==0]))-np.mean(abs(image[lab==1]))))
        validation={**result['validation'],'max_image_error':quality['nrmse'],'coefficient_error':component_error,
            'data_residual':solver['relative_data_residual'],'roi_contrast':contrast,
            'max_relative_t2_error':float(np.max(abs(np.asarray(fit['t2_s'])/np.asarray(params.get('t2_s',[.04,.12]))-1)))}
        validation['passed']=bool(quality['passed'] and component_error<=params.get('target_coefficient_error',1e-6) and solver['converged'] and
            contrast>=params.get('target_min_contrast',.005) and validation['rf_energy_relative']<=params.get('target_max_rf_energy',200.))
        result.update(image=image,quality=quality,reconstructed_components=components,reconstructed_echoes=echo_images,
            basis_physical=fit['basis_physical'],
            coefficients=coeff,temporal_basis=vh,physical_to_basis=s[:,None]*u.conj().T,basis_echo_weights=weights,
            solvers=[solver],validation=validation,navigator_reconstruction_performed=True)
        result['provenance'].update(estimated_work=result['provenance']['estimated_work']+solver['estimated_work'],
            basis_hash=_hash(weights.tolist()),basis_singular_values=s.tolist(),
            estimated_peak_memory_bytes=max(control['provenance']['estimated_peak_memory_bytes'],retained+solver['estimated_memory_bytes']))
    result['scope']=('teaching/research data-only two-global-T2 navigation with withheld echo checks; no voxel T2 map, '
        'labels/reference/gain fit in the inverse; authored T1/PD and measured interval priors; ideal echo-center EPG, '
        'no within-ADC evolution/coils/trajectory calibration; no scanner validation/clinical certification; B/C parked')
    result['design']={**control['design'],'max_work':cap,'t2_bounds_s':fit['t2_bounds_s'],
        'navigator_max_work':navigator_max_work,'navigator_max_evaluations':navigator_max_evaluations}
    result['provenance'].update(version='navigator-radial-tse-v1',navigator_hash=fit['navigator_hash'],
        fixed_prior_basis_hash=control['provenance']['basis_hash'],
        basis_t2_estimated_from_data=fit['t2_s'] if fit['passed'] else None,
        replay=result['design'],input_hash=_hash(result['design']),
        reconstruction='unregularized CGLS after bounded global EPG navigator fit; DC mixture amplitudes are not used as image scale',
        reserved_work=cap)
    if _checked_sources()!=sources: raise ValueError('source changed during navigated study')
    return result
