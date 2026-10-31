"""Finite point-ADC spin-echo radial reference with authored B0/receive maps.

Ideal hard 180-degree CPMG only. Echo-center EPG supplies periodic amplitudes;
analytic free Bloch evolution supplies each ADC sample. This is not full RF,
motion, gradient switching or measured-coil/field calibration.
"""
import numpy as np
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from mrqlab_recon.readout_encoding import readout_cgls
from mrqlab_recon.spatial import image_quality
from .tse_imaging import prepare_tse_echo_train
from .spatial_imaging import _hash
from .study_records import _checked_sources,runtime_manifest


def authored_maps(shape,field_scale_hz,coil_count,field_hz=None,coils_ri=None):
    axes=[(np.arange(n)-n//2)/(n/2) for n in shape]
    grid=np.meshgrid(*axes,indexing='ij');y,x=grid[-2:];z=grid[0] if len(shape)==3 else 0.
    field=field_scale_hz*(x+.4*y+.2*z+.3*x*y) if field_hz is None else np.asarray(field_hz,float)
    if field.shape!=shape or not np.isfinite(field).all() or np.max(abs(field))>2000: raise ValueError('compatible finite authored B0 map in Hz, bounded by 2000 Hz, required')
    if coils_ri is None:
        coils=np.array([(.8+.2*x*np.cos(theta)+.2*y*np.sin(theta))*np.exp(1j*(.3*x*np.sin(theta)+.4*y*np.cos(theta)+.1*z)) for theta in np.arange(coil_count)*2*np.pi/coil_count])
    else:
        ri=np.asarray(coils_ri,float)
        if ri.shape!=(coil_count,*shape,2) or not np.isfinite(ri).all(): raise ValueError('coil maps must have shape (coil_count,*spatial_shape,2) with explicit real/imaginary values')
        coils=ri[...,0]+1j*ri[...,1]
    if np.any(np.sum(abs(coils)**2,axis=0)<1e-12) or np.max(abs(coils))>4: raise ValueError('bounded coil sensitivity and no jointly invisible voxel required')
    return field,coils


def direct_point_acquisition(coordinates,shape,offsets_s,field_hz,coils,temporal,components):
    """Independent chunked voxel sum; no inverse operator is called."""
    v=int(np.prod(shape));m=len(coordinates)
    indices=np.indices(shape).reshape(len(shape),v)-np.array(shape)[:,None]//2
    values=np.empty((len(coils),m),complex);sens=coils.reshape(len(coils),v);maps=components.reshape(len(components),v)
    for start in range(0,m,64):
        stop=min(m,start+64);rows=[]
        for j in range(start,stop):
            spatial_phase=np.exp(-2j*np.pi*np.sum(coordinates[j,:,None]*indices,axis=0))
            field_phase=np.exp(2j*np.pi*field_hz.ravel()*offsets_s[j])
            magnetization=np.sum(temporal[:,j,None]*maps,axis=0)*field_phase
            rows.append(np.sum(sens*magnetization*spatial_phase,axis=1))
        values[:,start:stop]=np.asarray(rows).T
    return values


def run_finite_adc_radial_tse(**p):
    sources=_checked_sources();labels=np.asarray(p['labels']);shape=labels.shape
    if labels.ndim not in (2,3) or shape[-2]!=shape[-1] or not 16<=shape[-1]<=64 or (labels.ndim==3 and not 2<=shape[0]<=8) or not np.isin(labels,[0,1]).all() or len(np.unique(labels))!=2:
        raise ValueError('bounded square 2D/3D two-class phantom required')
    integer_keys=['echoes','spokes','points','display_echo','inverse_max_iterations','control_iterations','coil_count','max_samples','max_work','max_memory_bytes']
    if any(type(p[k]) is not int or p[k]<=0 for k in integer_keys): raise ValueError('positive integer counts and budgets required')
    echoes=p['echoes'];spokes=p['spokes'];points=p['points'];nc=p['coil_count'];nz=shape[0] if labels.ndim==3 else 1
    if not 2<=echoes<=32 or spokes%echoes or not 2<=spokes<=4096 or not 16<=points<=512 or not 1<=p['display_echo']<=echoes or not 1<=nc<=4:
        raise ValueError('complete bounded echo trains, ADCs, coils and display echo required')
    if p['backend']!='exact': raise ValueError('finite ADC/B0/coil mode currently requires exact DFT reference; existing FINUFFT echo-center mode is separate')
    if p['refocusing_angle']!=180. or p['refocusing_end_angle']!=180.:
        raise ValueError('analytic near-echo finite ADC requires ideal hard 180-degree CPMG; variable-flip within-window coherence is not implemented')
    if p['echo_order'] not in {'forward','reverse'}: raise ValueError('forward/reverse echo ordering required')
    scalar_keys=['echo_spacing_s','tr_s','adc_duration_s','fov_m','prephaser_s','field_scale_hz','basis_field_scale','max_gradient_t_m','max_duration_s','inverse_tolerance','target_image_error','target_coefficient_error','target_min_contrast','target_max_rf_energy']
    if len(p['component_phase_rad'])!=2 or not np.isfinite([*[p[k] for k in scalar_keys],*p['component_phase_rad']]).all(): raise ValueError('finite physical timing/maps/phases and targets required')
    if any(p[k]<=0 for k in ['echo_spacing_s','tr_s','adc_duration_s','fov_m','prephaser_s','max_gradient_t_m','max_duration_s','target_image_error','target_coefficient_error','target_max_rf_energy']) or p['target_min_contrast']<0 or not 0<p['inverse_tolerance']<1:
        raise ValueError('positive physical timing, resource and validation targets required')
    if p['adc_duration_s']+2*p['prephaser_s']>p['echo_spacing_s']:
        raise ValueError('ADC prephaser/readout/rewinder overlaps the ideal refocusing RF')
    m=nz*spokes*points;v=labels.size;count=nc*m;trains=nz*spokes//echoes
    retained=int(256*count+(256+64*echoes)*v+128*m+2048*trains*echoes)
    operator_memory=p['max_memory_bytes']-retained
    operation=int(nc*2*(m*v+2*m+v));setup=int(8*m*v)
    operator_estimate=int(32*m*v+128*m*nc+128*2*v+64*nc*v+32*2*m+64*min(m,128)*v)
    control_reserve=setup+(2*p['control_iterations']+3)*operation
    acquisition_work=int(16*m*v+4*nc*m*v)
    if count>p['max_samples'] or trains*p['tr_s']>p['max_duration_s'] or operator_memory<operator_estimate or acquisition_work+control_reserve+setup+2*operation>=p['max_work']:
        raise ValueError('complete finite ADC/reference/control sample, duration, work or memory preflight failed')
    n=shape[-1];gradient=n/(GAMMA_BAR_HZ_T*p['fov_m']*p['adc_duration_s']);pre=n/(2*GAMMA_BAR_HZ_T*p['fov_m']*p['prephaser_s'])
    kz=(np.arange(nz)-nz//2)/nz if labels.ndim==3 else np.array([0.])
    gz=-kz*nz/(GAMMA_BAR_HZ_T*p['fov_m']*p['prephaser_s'])
    peak=max(gradient,float(np.sqrt(pre*pre+gz*gz).max()))
    if peak>p['max_gradient_t_m']: raise ValueError('ideal finite readout/prephaser gradient exceeds the declared amplitude limit')
    args=dict(echoes=echoes,echo_spacing_s=p['echo_spacing_s'],tr_s=p['tr_s'],refocusing_angle=180.,refocusing_end_angle=180.,max_work=min(p['max_work'],10000000),experiment=p['experiment'])
    graph,sequence,truth,physical,prep,work,experiment_input=prepare_tse_echo_train(t2_s=p['t2_s'],**args)
    bt2=list(p['t2_s']) if p['basis_t2_s'] is None else list(p['basis_t2_s'])
    if bt2==list(p['t2_s']): basis=truth;basis_physical=physical
    else:
        _,_,basis,basis_physical,_,extra,_=prepare_tse_echo_train(t2_s=bt2,**args);work+=extra
    duration=trains*p['tr_s']+max(prep)
    if duration>p['max_duration_s'] or work+acquisition_work+control_reserve+setup+2*operation>p['max_work']: raise ValueError('prepared finite-ADC workflow exceeds duration/work allowance')
    offset=(np.arange(points)+.5-points/2)*p['adc_duration_s']/points
    radius=offset/p['adc_duration_s'];theta=np.arange(spokes)*np.pi*(3-np.sqrt(5))
    xy=np.column_stack([(np.cos(theta)[:,None]*radius).ravel(),(np.sin(theta)[:,None]*radius).ravel()])
    e=np.arange(spokes)%echoes
    if p['echo_order']=='reverse': e=echoes-1-e
    sample_echo=np.tile(np.repeat(e,points),nz);tau=np.tile(offset,nz*spokes)
    coord=np.tile(xy[:,::-1],(nz,1))
    if labels.ndim==3: coord=np.column_stack([np.repeat(kz,spokes*points),coord])
    field,coils=authored_maps(shape,p['field_scale_hz'],nc,p['field_hz'],p['coils_ri'])
    tw=truth[:,sample_echo]*np.exp(-tau[None,:]/np.asarray(p['t2_s'])[:,None])
    bw=basis[:,sample_echo]*np.exp(-tau[None,:]/np.asarray(bt2)[:,None])
    u,s,vh=np.linalg.svd(bw,full_matrices=False)
    if s[-1]<=s[0]*1e-10: raise ValueError('finite ADC temporal basis is rank deficient')
    masks=np.array([labels==i for i in range(2)])*np.exp(1j*np.asarray(p['component_phase_rad'])).reshape((2,)+(1,)*labels.ndim)
    samples=direct_point_acquisition(coord,shape,tau,field,coils,tw,masks);work+=acquisition_work
    def solve(weights,fieldmap,limit,reserve):
        nonlocal work
        result,diag=readout_cgls(coord,samples,shape,weights,tau,fieldmap,coils,max_iterations=limit,tolerance=p['inverse_tolerance'],
            max_work=p['max_work']-work-reserve,max_memory_bytes=operator_memory)
        work+=diag['estimated_work'];return result,diag
    coefficients,solver=solve(vh,field*p['basis_field_scale'],p['inverse_max_iterations'],control_reserve)
    components=((u/s[None,:])@coefficients.reshape(2,-1)).reshape(masks.shape)
    reconstructed=(basis.T@components.reshape(2,-1)).reshape((echoes,*shape));references=(truth.T@masks.reshape(2,-1)).reshape((echoes,*shape))
    # Same actual multicoil samples and receive maps; explicitly omit only
    # within-ADC B0/T2 evolution in this mismatch control.
    cu,cs,cvh=np.linalg.svd(basis[:,sample_echo],full_matrices=False)
    static_coeff,static_solver=solve(cvh,np.zeros(shape),p['control_iterations'],0)
    static_components=((cu/cs[None,:])@static_coeff.reshape(2,-1)).reshape(masks.shape)
    control=(basis[:,p['display_echo']-1]@static_components.reshape(2,-1)).reshape(shape)
    image=reconstructed[p['display_echo']-1];reference=references[p['display_echo']-1];quality=image_quality(reference,image,p['target_image_error'])
    coefficient_error=float(np.linalg.norm(components-masks)/np.linalg.norm(masks));contrast=float(abs(np.mean(abs(image[labels==0]))-np.mean(abs(image[labels==1]))))
    rf_energy=float(trains*sum((a.value/180.)**2 for a in sequence.channel('rf_amp')))
    passed=bool(quality['passed'] and coefficient_error<=p['target_coefficient_error'] and solver['converged'] and contrast>=p['target_min_contrast'] and rf_energy<=p['target_max_rf_energy'])
    timeline=[];sample_times=np.zeros(m)
    for zindex in sorted(range(nz),key=lambda z:(abs(z-nz//2),z)):
        for first in range(0,spokes,echoes):
            start=len(timeline)*p['tr_s'];entries=[]
            for spoke in sorted(range(first,first+echoes),key=lambda q:e[q]):
                center=start+(e[spoke]+1)*p['echo_spacing_s'];indices=zindex*spokes*points+spoke*points+np.arange(points)
                sample_times[indices]=center+offset
                direction=np.array([np.cos(theta[spoke]),np.sin(theta[spoke])])
                entries.append(dict(spoke=spoke,echo=int(e[spoke]+1),adc_start_s=center-p['adc_duration_s']/2,adc_end_s=center+p['adc_duration_s']/2,
                    samples=points,dwell_s=p['adc_duration_s']/points,sample_indices=indices.tolist(),
                    prephaser_start_s=center-p['adc_duration_s']/2-p['prephaser_s'],rewinder_end_s=center+p['adc_duration_s']/2+p['prephaser_s'],
                    prephaser_gradient_t_m=[*(pre*direction),float(gz[zindex])],readout_gradient_t_m=[*(-gradient*direction),0.],
                    rewinder_gradient_t_m=[*(pre*direction),float(-gz[zindex])]))
            timeline.append(dict(train=len(timeline),kz_index=zindex,excitation_s=start,tr_end_s=start+p['tr_s'],
                refocusing_s=[start+a.time for a in sequence.channel('rf_amp') if a.time>0],spokes=entries))
    inputs=dict(p,labels=labels.tolist(),t2_s=list(p['t2_s']),basis_t2_s=bt2,component_phase_rad=list(p['component_phase_rad']))
    if p['experiment'] is None: inputs.pop('experiment')
    else: inputs['experiment']=experiment_input
    for key in ['field_hz','coils_ri']:
        if inputs[key] is None: inputs.pop(key)
    if _checked_sources()!=sources: raise ValueError('source changed during finite ADC acquisition/inversion')
    return dict(clinical_question='Can a known-field multicoil finite-ADC radial TSE inverse preserve unscaled complex tissue contrast while the frozen-readout model fails?',
        design=inputs,experiment=graph.model_dump(mode='json'),image=image,reference=reference,tissue_echo_weights=truth,basis_echo_weights=basis,
        reconstructed_components=components,reference_components=masks,reconstructed_echoes=reconstructed,reference_echoes=references,
        coefficients=coefficients,temporal_basis=vh,physical_to_basis=s[:,None]*u.conj().T,
        timeline=timeline,coordinates=xy,kz_cycles_per_voxel=kz,samples=samples,echo_for_sample=sample_echo,
        readout=dict(coordinates_array_order=coord,offsets_s=tau,sample_times_s=sample_times,field_hz=field,coil_sensitivities=coils,
            temporal_sample_weights=tw,basis_temporal_weights=bw,adc_duration_s=p['adc_duration_s'],dwell_s=p['adc_duration_s']/points,
            peak_gradient_t_m=peak,coils=nc,field_origin='authored map; no measured calibration',receiver_phase_rad=np.pi/2,
            convention='point ADC at gate midpoints; k=-gamma_bar*gradient integral, array-axis coordinates in cycles/voxel; receiver i*(Mx+iMy)'),
        static_control=dict(image=control,quality=image_quality(reference,control,p['target_image_error']),solver=static_solver,
            model='same receive maps and data, frozen B0/T2 within ADC; two unrestricted component images'),
        solvers=[solver],quality=quality,objective_loss=rf_energy,
        validation=dict(passed=passed,max_image_error=quality['nrmse'],target_image_error=p['target_image_error'],coefficient_error=coefficient_error,
            target_coefficient_error=p['target_coefficient_error'],data_residual=solver['relative_data_residual'],target_data_residual=p['inverse_tolerance'],
            roi_contrast=contrast,target_min_contrast=p['target_min_contrast'],rf_energy_relative=rf_energy,target_max_rf_energy=p['target_max_rf_energy'],
            total_duration_s=duration,max_duration_s=p['max_duration_s']),
        scope='teaching/research known-field/known-coil finite point-ADC exact DFT reference; periodic echo-center EPG plus analytic free Bloch around ideal 180-degree CPMG; authored maps/T1/PD/T2, ideal balanced rectangular gradients; no finite-RF/spatial-coherence evolution, noise calibration, motion, measured field/coil calibration, fast NUFFT claim or clinical/scanner certification; B/C parked',
        provenance=dict(version='finite-adc-radial-v1',replay=inputs,input_hash=_hash(inputs),sources=sources,runtime=runtime_manifest(),physical=physical,basis_physical=basis_physical,
            estimated_work=work,estimated_peak_memory_bytes=retained+operator_estimate,estimated_samples=count,preparation_duration_s=max(prep),acquisition_duration_s=trains*p['tr_s'],
            timeline_hash=_hash(timeline),sample_hash=_hash([samples.real.tolist(),samples.imag.tolist()]),basis_hash=_hash(bw.tolist()),basis_singular_values=s.tolist(),
            field_hash=_hash(field.tolist()),coil_hash=_hash([coils.real.tolist(),coils.imag.tolist()]),
            chassis='ExperimentGraph supplies periodic EPG echo centers only; finite ADC/gradient schedule is the explicit research timeline, not scanner execution',
            acquisition='independent direct complex point-ADC voxel sum with analytic within-echo T2 and B0 evolution',
            normalization='lossless complete temporal SVD; no mode truncation, coil/RSS normalization, fitted gain, spatial support or regularization'))
