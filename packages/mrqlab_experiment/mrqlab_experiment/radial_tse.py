"""Echo-resolved radial TSE with declared two-curve temporal priors.

Research/teaching only: ideal echo-center magnitude EPG, static complex spatial
coefficients, radial xy / Cartesian kz. No full physical readout or scanner claim.
"""
import numpy as np
from mrqlab_recon.spatial import radial_coordinates, radial_acquire, image_quality
from mrqlab_recon.noncartesian import radial_cgls, RadialFourierOperator
from mrqlab_recon.nufft import radial_nufft_cgls, RadialNUFFTOperator
from mrqlab_recon.echo_subspace import echo_subspace_cgls
from .tse_imaging import prepare_tse_echo_train
from .spatial_imaging import _hash
from .study_records import _checked_sources, runtime_manifest

SCOPE = ('teaching/research echo-center periodic magnitude EPG and known two-curve temporal basis; '
         'static complex coefficients, ideal radial xy / Cartesian kz; no within-ADC evolution, '
         'physical gradient waveform, slice profile, coils, motion, measured calibration or '
         'T2 estimation; no scanner validation or clinical quality certification; B/C parked')


def run_radial_tse(labels, *, echoes=4, spokes=96, points=32, echo_spacing_s=.008,
                   tr_s=.4, t2_s=(.04,.12), basis_t2_s=None,
                   refocusing_angle=180., refocusing_end_angle=180.,
                   echo_order='forward', display_echo=2, backend='exact',
                   inverse_max_iterations=6000, inverse_tolerance=1e-10, nufft_eps=1e-13,
                   control_iterations=1000, component_phase_rad=(0.,0.),
                   max_samples=24576, max_work=20000000000, max_memory_bytes=134217728,
                   max_duration_s=100., target_image_error=1e-6,
                   target_coefficient_error=1e-6, target_min_contrast=.005,
                   target_max_rf_energy=200., experiment=None,
                   readout_model='echo_center',adc_duration_s=.002,fov_m=.24,prephaser_s=.0005,
                   field_scale_hz=80.,coil_count=2,field_hz=None,coils_ri=None,basis_field_scale=1.,max_gradient_t_m=.08):
    if readout_model=='finite_adc':
        readout_inputs=locals().copy()
        from .radial_readout import run_finite_adc_radial_tse
        return run_finite_adc_radial_tse(**readout_inputs)
    if readout_model!='echo_center': raise ValueError('echo_center or finite_adc readout model required')
    if field_hz is not None or coils_ri is not None or adc_duration_s!=.002 or fov_m!=.24 or prephaser_s!=.0005 or field_scale_hz!=80. or coil_count!=2 or basis_field_scale!=1. or max_gradient_t_m!=.08:
        raise ValueError('finite ADC/field/coil overrides require readout_model=finite_adc')
    sources = _checked_sources()
    labels = np.asarray(labels)
    if (labels.ndim not in (2,3) or labels.shape[-1]!=labels.shape[-2] or
            not 16<=labels.shape[-1]<=128 or not np.isin(labels,[0,1]).all() or
            (labels.ndim==3 and not 2<=labels.shape[0]<=8) or
            len(np.unique(labels))!=2):
        raise ValueError('bounded square two-class 2D/3D labels containing both tissues required')
    for value in [echoes,spokes,points,inverse_max_iterations,control_iterations,max_samples,max_work,max_memory_bytes]:
        if type(value) is not int or value<=0: raise ValueError('positive integer counts and budgets required')
    if not 2<=echoes<=32 or spokes%echoes or not 2<=spokes<=4096 or not 16<=points<=512 or not 1<=display_echo<=echoes or type(display_echo) is not int:
        raise ValueError('complete echo trains, bounded samples and valid display echo required')
    if echo_order not in {'forward','reverse'} or backend not in {'exact','finufft'}:
        raise ValueError('invalid echo order/backend')
    scalars=[echo_spacing_s,tr_s,max_duration_s,target_image_error,target_coefficient_error,target_min_contrast,target_max_rf_energy,*component_phase_rad]
    if (len(component_phase_rad)!=2 or not np.isfinite(scalars).all() or
            min(echo_spacing_s,tr_s,max_duration_s,target_image_error,target_coefficient_error,target_max_rf_energy)<=0 or target_min_contrast<0):
        raise ValueError('finite phases, positive timing and declared targets required')
    if isinstance(inverse_tolerance,bool) or not np.isfinite(inverse_tolerance) or not 0<inverse_tolerance<1:
        raise ValueError('relative inverse tolerance between zero and one required')
    if isinstance(nufft_eps,bool) or not np.isfinite(nufft_eps) or not 1e-14<=nufft_eps<=1e-3:
        raise ValueError('bounded NUFFT precision required')
    if backend=='finufft' and nufft_eps>inverse_tolerance/10:
        raise ValueError('NUFFT eps must be at most one tenth of inverse tolerance')
    nz=labels.shape[0] if labels.ndim==3 else 1
    trains=nz*spokes//echoes; count=nz*spokes*points
    retained_memory=int(128*count+(256+64*echoes)*labels.size+512*trains*echoes)
    operator_memory=max_memory_bytes-retained_memory
    if operator_memory<=0:
        raise ValueError('acquisition buffer memory budget exceeded before trajectory allocation')
    if count>max_samples or trains*tr_s>max_duration_s:
        raise ValueError('acquisition sample/duration budget exceeded')
    # Validate exact geometry/timing through the same chassis as Cartesian TSE.
    args=dict(echoes=echoes,echo_spacing_s=echo_spacing_s,tr_s=tr_s,
        refocusing_angle=refocusing_angle,refocusing_end_angle=refocusing_end_angle,
        max_work=min(max_work,10000000),experiment=experiment)
    graph,sequence,truth_weights,physical,prep,epg_work,experiment_input=prepare_tse_echo_train(t2_s=t2_s,**args)
    if basis_t2_s is None: basis_t2_s=list(t2_s)
    if list(basis_t2_s)==list(t2_s):
        fit_weights=truth_weights;basis_physical=physical
    else:
        _,_,fit_weights,basis_physical,basis_prep,extra,_=prepare_tse_echo_train(t2_s=basis_t2_s,**args)
        epg_work+=extra
    duration=trains*tr_s+max(prep)
    if duration>max_duration_s or epg_work>=max_work:
        raise ValueError('prepared acquisition duration/work budget exceeded')
    # Lossless temporal SVD coordinates: W=U S Vh. Neither truncation nor a
    # truth-dependent scale is applied. Unknown mixed maps are S U^H c.
    u,s,vh=np.linalg.svd(fit_weights,full_matrices=False)
    if s[-1]<=s[0]*1e-10: raise ValueError('EPG temporal basis is rank deficient')
    echo_for_spoke=np.arange(spokes)%echoes
    if echo_order=='reverse': echo_for_spoke=echoes-1-echo_for_spoke
    echo_for_sample=np.repeat(echo_for_spoke,points)
    weights=vh[:,echo_for_sample]
    xy=radial_coordinates(labels.shape,spokes,points)
    # Reserve the complete static mismatch control before spending the joint
    # solve budget. A failed joint image remains available on work exhaustion.
    base_kwargs=dict(max_work=max_work-epg_work,max_memory_bytes=operator_memory)
    prototype=(RadialFourierOperator(xy,labels.shape,**base_kwargs) if backend=='exact' else
        RadialNUFFTOperator(xy,labels.shape,eps=nufft_eps,**base_kwargs))
    control_work=prototype.work+(2*control_iterations+3)*prototype.operation_work
    setup=prototype.work;operation=prototype.operation_work
    peak_memory=retained_memory+prototype.estimated_memory_bytes
    del prototype
    # Include the resource-estimation prototype's actual plan/basis construction.
    work=epg_work+setup
    phases=np.exp(1j*np.asarray(component_phase_rad)).reshape((2,)+(1,)*labels.ndim)
    masks=np.array([labels==i for i in range(2)])*phases
    if backend=='exact':
        acquisition_work=2*(len(xy)*labels.shape[-1]**2+operation)+2*count
        if work+acquisition_work+control_work>=max_work: raise ValueError('combined acquisition/control budget exceeded')
        samples=sum(radial_acquire(mask,spokes,points)[1]*truth_weights[k,echo_for_sample] for k,mask in enumerate(masks))
        work+=acquisition_work
        acquisition=dict(backend='independent direct Fourier acquisition')
    else:
        op=RadialNUFFTOperator(xy,labels.shape,eps=nufft_eps,max_work=max_work-work-control_work,max_memory_bytes=operator_memory)
        samples=sum(op.forward(mask)*truth_weights[k,echo_for_sample] for k,mask in enumerate(masks))
        work+=op.work;acquisition=op.diagnostics();del op
    coefficients,solver=echo_subspace_cgls(xy,samples,labels.shape,weights,backend=backend,
        max_iterations=inverse_max_iterations,tolerance=inverse_tolerance,eps=nufft_eps,
        max_work=max_work-work-control_work,max_memory_bytes=operator_memory)
    work+=solver['estimated_work']
    peak_memory=max(peak_memory,retained_memory+solver['estimated_memory_bytes'])
    inverse_transform=u/s[None,:]
    reconstructed_components=(inverse_transform@coefficients.reshape(2,-1)).reshape(masks.shape)
    reconstructed_echoes=(fit_weights.T@reconstructed_components.reshape(2,-1)).reshape((echoes,*labels.shape))
    true_echoes=(truth_weights.T@masks.reshape(2,-1)).reshape((echoes,*labels.shape))
    image=reconstructed_echoes[display_echo-1];reference=true_echoes[display_echo-1]
    if backend=='exact':
        static,static_solver=radial_cgls(xy,samples,labels.shape,max_iterations=control_iterations,
            tolerance=inverse_tolerance,max_work=max_work-work,max_memory_bytes=operator_memory)
    else:
        static,static_solver=radial_nufft_cgls(xy,samples,labels.shape,max_iterations=control_iterations,
            tolerance=inverse_tolerance,eps=nufft_eps,max_work=max_work-work,max_memory_bytes=operator_memory)
    work+=static_solver['estimated_work']
    peak_memory=max(peak_memory,retained_memory+static_solver['estimated_memory_bytes'])
    quality=image_quality(reference,image,target_image_error)
    coefficient_error=float(np.linalg.norm(reconstructed_components-masks)/np.linalg.norm(masks))
    contrast=float(abs(np.mean(abs(image[labels==0]))-np.mean(abs(image[labels==1]))))
    rf_energy=float(trains*sum((e.value/180.)**2 for e in sequence.channel('rf_amp')))
    passed=bool(quality['passed'] and coefficient_error<=target_coefficient_error and solver['converged'] and
                contrast>=target_min_contrast and rf_energy<=target_max_rf_energy)
    timeline=[]
    rf=sequence.channel('rf_amp')
    for z in sorted(range(nz),key=lambda value:(abs(value-nz//2),value)):
        for start in range(0,spokes,echoes):
            train=len(timeline);offset=train*tr_s
            # reverse order reassigns radial angles to chronological echo slots.
            indices=sorted(range(start,start+echoes),key=lambda spoke:echo_for_spoke[spoke])
            timeline.append(dict(train=train,kz_index=z,excitation_s=offset,tr_end_s=offset+tr_s,
                refocusing_s=[offset+e.time for e in rf if e.time>0],
                spokes=[dict(spoke=i,echo=int(echo_for_spoke[i]+1),echo_time_s=float((echo_for_spoke[i]+1)*echo_spacing_s),
                    adc_start_s=float(offset+(echo_for_spoke[i]+1)*echo_spacing_s),
                    adc_end_s=float(offset+(echo_for_spoke[i]+1)*echo_spacing_s+.002),samples=points,dwell_s=.002/points,
                    tissue_weights=truth_weights[:,echo_for_spoke[i]].tolist()) for i in indices]))
    inputs=dict(labels=labels.tolist(),readout_model='echo_center',echoes=echoes,spokes=spokes,points=points,echo_spacing_s=echo_spacing_s,
        tr_s=tr_s,t2_s=list(t2_s),basis_t2_s=list(basis_t2_s),refocusing_angle=refocusing_angle,
        refocusing_end_angle=refocusing_end_angle,echo_order=echo_order,display_echo=display_echo,backend=backend,
        inverse_max_iterations=inverse_max_iterations,inverse_tolerance=inverse_tolerance,nufft_eps=nufft_eps,
        control_iterations=control_iterations,component_phase_rad=list(component_phase_rad),max_samples=max_samples,
        max_work=max_work,max_memory_bytes=max_memory_bytes,max_duration_s=max_duration_s,
        target_image_error=target_image_error,target_coefficient_error=target_coefficient_error,
        target_min_contrast=target_min_contrast,target_max_rf_energy=target_max_rf_energy)
    if experiment is not None: inputs['experiment']=experiment_input
    if _checked_sources()!=sources: raise ValueError('source changed during execution')
    return dict(clinical_question=graph.clinical_recipe.question.research_question if experiment is not None and graph.clinical_recipe else 'Can an echo-aware radial TSE design preserve declared-echo tissue contrast and spatial detail within RF/time limits?',
        design=inputs,experiment=graph.model_dump(mode='json'),image=image,reference=reference,
        tissue_echo_weights=truth_weights,basis_echo_weights=fit_weights,
        reconstructed_components=reconstructed_components,reference_components=masks,
        reconstructed_echoes=reconstructed_echoes,reference_echoes=true_echoes,
        coefficients=coefficients,temporal_basis=vh,physical_to_basis=s[:,None]*u.conj().T,
        timeline=timeline,coordinates=xy,kz_cycles_per_voxel=(np.arange(nz)-nz//2)/nz,samples=samples,echo_for_sample=echo_for_sample,
        static_control=dict(image=static,quality=image_quality(reference,static,target_image_error),solver=static_solver),
        solvers=[solver],quality=quality,objective_loss=rf_energy,
        validation=dict(passed=passed,max_image_error=quality['nrmse'],target_image_error=target_image_error,
            coefficient_error=coefficient_error,target_coefficient_error=target_coefficient_error,
            data_residual=solver['relative_data_residual'],target_data_residual=inverse_tolerance,
            roi_contrast=contrast,target_min_contrast=target_min_contrast,rf_energy_relative=rf_energy,
            target_max_rf_energy=target_max_rf_energy,total_duration_s=duration,max_duration_s=max_duration_s),
        scope=SCOPE,provenance=dict(version='echo-radial-tse-v1',replay=inputs,input_hash=_hash(inputs),
            sources=sources,runtime=runtime_manifest(),
            physical=physical,basis_physical=basis_physical,acquisition=acquisition,
            estimated_work=work,estimated_peak_memory_bytes=peak_memory,estimated_samples=count,preparation_duration_s=max(prep),
            acquisition_duration_s=trains*tr_s,timeline_hash=_hash(timeline),
            sample_hash=_hash([samples.real.tolist(),samples.imag.tolist()]),
            basis_singular_values=s.tolist(),basis_hash=_hash(fit_weights.tolist()),
            reconstruction='unregularized CGLS of two mixed temporal-basis images; no spatial support or gain fit',
            normalization='lossless temporal SVD coordinate change; no truncated modes, per-image normalization or fitted gain'))
