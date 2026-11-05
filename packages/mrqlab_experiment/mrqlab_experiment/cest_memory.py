"""Joint CEST / Solomon relay / finite-history generalized semisolid MT.

Near-resonant finite RF uses a regular time-domain Green function, not a
substitute/clamp for the canonical singular absorption-rate model. Molecular
priors remain authored, and the Solomon part remains a minimal longitudinal pair.
"""
from dataclasses import asdict
import numpy as np
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from mrqlab_physics.ops.generalized_mt import memory_weights,integrate_generalized_mt,solver_budget
from mrqlab_physics.ops.dipolar_solomon import dipolar_pair_rates,add_solomon_pair
from mrqlab_physics.ops.cest_saturation import _matrix_exp
from .cest_solomon import relay_pool_system
from .cest_mt_noe import joint_generator
from .study_records import _checked_sources,runtime_manifest
from .spatial_imaging import _hash


def saturation_waveform(*,b1_uT=1.,pulse_s=.02,gap_s=.04,n_pulses=4,shape='hann',
                        phase_cycle_rad=(0.,),rf_bins=16,steps_per_bin=24):
    if (not np.isfinite([b1_uT,pulse_s,gap_s,*phase_cycle_rad]).all() or b1_uT<=0 or pulse_s<=0 or gap_s<0 or
            not 1<=len(phase_cycle_rad)<=8 or max(abs(p) for p in phase_cycle_rad)>4*np.pi):
        raise ValueError('positive finite RF/pulse, nonnegative gap and bounded phases required')
    for val,lo,hi in [(n_pulses,1,16),(rf_bins,4,64),(steps_per_bin,1,32)]:
        if type(val) is not int or not lo<=val<=hi: raise ValueError('bounded integer pulse/bin/time settings required')
    if shape not in {'rectangular','hann'}: raise ValueError('rectangular or sampled-Hann RF required')
    dt=pulse_s/(rf_bins*steps_per_bin);gap_steps=int(round(gap_s/dt)) if n_pulses>1 else 0
    if n_pulses>1 and abs(gap_steps*dt-gap_s)>1e-12:
        raise ValueError('pulse/gap boundaries must align with the declared uniform time grid; no timing rounding')
    count=n_pulses*rf_bins*steps_per_bin+(n_pulses-1)*gap_steps
    if count>4096: raise ValueError('coarse history exceeds 4096 cells before required 2x refinement')
    profile=np.ones(rf_bins) if shape=='rectangular' else np.sin(np.pi*(np.arange(rf_bins)+.5)/rf_bins)**2
    profile=profile/profile.max()  # authored RF peak, never fitted to a signal
    holds=[];events=[];at=0.
    for p in range(n_pulses):
        phase=phase_cycle_rad[p%len(phase_cycle_rad)]
        holds.extend(np.repeat(b1_uT*profile*np.exp(1j*phase),steps_per_bin))
        events.append(dict(pulse=p,start_s=at,end_s=at+pulse_s,phase_rad=phase));at+=pulse_s
        if p+1<n_pulses: holds.extend([0j]*gap_steps);at+=gap_s
    field=np.asarray(holds,complex)
    return field,dict(dt_s=dt,elapsed_s=len(field)*dt,steps=len(field),events=events,
        peak_b1_uT=float(abs(field).max()),rf_energy_uT2_s=float(np.sum(abs(field)**2)*dt),
        duty_cycle=n_pulses*pulse_s/(len(field)*dt),waveform_hash=_hash([field.real.tolist(),field.imag.tolist(),dt]),
        shape='piecewise-constant '+shape,phase_reference='fixed RF rotating frame; carrier and all pulse/gap coherence history retained')


def memory_generator(system,offset_hz,rates,*,cross=True,bound_fraction=.08,bound_to_water_hz=20.,bound_t2_s=12e-6):
    # No RF in the legacy joint generator means no lineshape rate is evaluated,
    # even at zero offset. RF matrices act on liquids; semisolid RF is Volterra.
    g=add_solomon_pair(joint_generator(system,offset_hz,0.,bound_fraction=bound_fraction,
        bound_to_water_hz=bound_to_water_hz,bound_t2_s=bound_t2_s),system,3,4,rates,cross_relaxation=cross)
    rx=np.zeros_like(g);ry=np.zeros_like(g)
    for k in range(system.count):
        i=3*k;rx[i+1,i+2]=1.;rx[i+2,i+1]=-1.;ry[i,i+2]=-1.;ry[i+2,i]=1.
    return g,rx,ry


def run_cest_memory(*,offsets_ppm=(-5.,-3.5,-2.,0.,2.,3.5,5.),b0_t=3.,b1_uT=1.,
                    pulse_s=.02,gap_s=.04,n_pulses=4,shape='hann',phase_cycle_rad=(0.,),rf_bins=16,steps_per_bin=24,
                    bound_fraction=.08,bound_to_water_hz=20.,bound_t2_s=12e-6,
                    lineshape='super_lorentzian',pair_fraction=.02,bridge_exchange_s1=1000.,
                    bridge_shift_ppm=1.,donor_shift_ppm=-3.5,distance_m=2.5e-10,tau_c_s=1e-8,
                    orientation_order=32,time_order=32,max_work=32000000000,max_memory_bytes=134217728,max_duration_s=300.,
                    target_min_amide_contrast=.005,target_min_relay_contrast=.005,
                    target_refinement_error=.0002,target_kernel_error=1e-6):
    sources=_checked_sources();offsets=np.asarray(offsets_ppm,float)
    if offsets.ndim!=1 or not 3<=len(offsets)<=16 or not np.isfinite(offsets).all() or len(np.unique(offsets))!=len(offsets):
        raise ValueError('3..16 distinct finite spectral offsets required')
    if any(np.count_nonzero(np.isclose(offsets,x,rtol=0,atol=1e-12))!=1 for x in [0.,3.5,donor_shift_ppm]) or np.isclose(donor_shift_ppm,3.5):
        raise ValueError('zero, amide +3.5 and distinct donor-resonant samples required')
    scalars=[bound_fraction,bound_to_water_hz,bound_t2_s,max_duration_s,target_min_amide_contrast,target_min_relay_contrast,target_refinement_error,target_kernel_error]
    if (not np.isfinite(scalars).all() or min(bound_fraction,bound_t2_s,max_duration_s,*scalars[4:])<=0 or bound_to_water_hz<0 or
            bound_to_water_hz*bound_t2_s>.01):
        raise ValueError('positive fractions/T2/targets and short-coherence bound exchange regime k*T2<=0.01 required')
    if lineshape not in {'super_lorentzian','gaussian','lorentzian'}: raise ValueError('supported time-domain lineshape required')
    for value in [max_work,max_memory_bytes]:
        if type(value) is not int or value<=0: raise ValueError('positive integer work/memory budget required')
    for order in [orientation_order,time_order]:
        if type(order) is not int or not 8<=order<=64: raise ValueError('coarse orientation/time quadrature order 8..64 required')
    field,wave=saturation_waveform(b1_uT=b1_uT,pulse_s=pulse_s,gap_s=gap_s,n_pulses=n_pulses,shape=shape,
        phase_cycle_rad=phase_cycle_rad,rf_bins=rf_bins,steps_per_bin=steps_per_bin)
    omega=2*np.pi*GAMMA_BAR_HZ_T*field*1e-6
    rates=dipolar_pair_rates(b0_t=b0_t,distance_m=distance_m,tau_c_s=tau_c_s,shifts_ppm=(bridge_shift_ppm,donor_shift_ppm))
    controls=dict(full=(True,True,True,True),no_cross=(False,True,True,True),no_bridge_exchange=(True,False,True,True),
        no_amide=(True,True,False,True),no_mt=(True,True,True,False))
    duration=(len(controls)*len(offsets)+1)*wave['elapsed_s']
    if duration>max_duration_s: raise ValueError('all-offset/control and unsaturated reference duration exceeds budget')
    n=len(field);d=17;unique=len(set(omega.tolist()))
    trace_indices=np.unique(np.r_[np.arange(0,n+1,max(1,int(np.ceil(n/256)))),
        np.flatnonzero(field[1:]!=field[:-1])+1,n]).astype(int)
    solver_plans=[solver_budget(n,d,unique),solver_budget(2*n,d,unique)]
    kernel_plan=sum(count*t*(2*o+16) for count,t,o in [(n,time_order,orientation_order),(2*n,2*time_order,2*orientation_order)])
    reference_work=d**3*100
    planned=len(offsets)*(kernel_plan+len(controls)*sum(p['planned_work'] for p in solver_plans))+reference_work
    retained=len(offsets)*len(controls)*(len(trace_indices)*4*8+4*d*8)
    peak=retained+max(p['estimated_peak_memory_bytes'] for p in solver_plans)+128*128*(2*time_order)*(2*orientation_order)
    if planned>max_work or peak>max_memory_bytes: raise ValueError('complete coarse/refined spectral-grid work or memory budget exceeded before integration')
    spectra={k:[] for k in controls};bound_spectra={k:[] for k in controls};trajectories={k:[] for k in controls}
    work=0;refinement=0.;kernel_error=0.;reference=None
    for ppm in offsets:
        hz=float(ppm*GAMMA_BAR_HZ_T*b0_t*1e-6);kernels=[]
        for factor in [1,2]:
            a,b,diag=memory_weights(factor*n,wave['dt_s']/factor,t2_s=bound_t2_s,offset_hz=hz,lineshape=lineshape,
                orientation_order=factor*orientation_order,time_order=factor*time_order,
                max_work=max_work-work,max_memory_bytes=max_memory_bytes-retained)
            work+=diag['estimated_work'];kernels.append((a,b))
        coarse=kernels[0][0]+kernels[0][1];fine=kernels[1][0]+kernels[1][1]
        kernel_error=max(kernel_error,float(np.max(abs(coarse-fine[::2]-fine[1::2]))/wave['dt_s']))
        for name,(cross,bridge,amide,mt) in controls.items():
            system=relay_pool_system(b0_t=b0_t,pair_fraction=pair_fraction,bridge_exchange_s1=bridge_exchange_s1 if bridge else 0.,
                bridge_shift_ppm=bridge_shift_ppm,donor_shift_ppm=donor_shift_ppm,amide_exchange=amide)
            initial=np.zeros(d);initial[2:15:3]=system.density;initial[-2]=bound_fraction;initial[-1]=1.
            g,rx,ry=memory_generator(system,hz,rates,cross=cross,bound_fraction=bound_fraction,
                bound_to_water_hz=bound_to_water_hz if mt else 0.,bound_t2_s=bound_t2_s)
            histories=[];diagnostics=[]
            for factor,(a,b) in zip([1,2],kernels):
                history,diag=integrate_generalized_mt(g,rx,ry,initial,np.repeat(omega,factor),wave['dt_s']/factor,a,b,
                    bound_index=d-2,max_work=max_work-work,max_memory_bytes=max_memory_bytes-retained)
                work+=diag['estimated_work'];histories.append(history);diagnostics.append(diag)
            c,f=histories;differences=np.column_stack([abs(c[:,2]-f[::2,2]),abs(c[:,-2]-f[::2,-2])/bound_fraction])
            at,channel=np.unravel_index(np.argmax(differences),differences.shape);error=float(differences[at,channel])
            refinement=max(refinement,error)
            spectra[name].append(float(f[-1,2]));bound_spectra[name].append(float(f[-1,-2]/bound_fraction))
            trajectories[name].append(dict(offset_ppm=float(ppm),refinement_error=error,
                coarse_water_z=c[trace_indices,2],refined_water_z=f[2*trace_indices,2],coarse_bound_z_fraction=c[trace_indices,-2]/bound_fraction,
                refined_bound_z_fraction=f[2*trace_indices,-2]/bound_fraction,final_state=f[-1],
                maximum_error_witness=dict(coarse_index=int(at),time_s=float(at*wave['dt_s']),channel='water' if channel==0 else 'bound_fraction',
                    coarse_value=float(c[at,2] if channel==0 else c[at,-2]/bound_fraction),
                    refined_value=float(f[2*at,2] if channel==0 else f[2*at,-2]/bound_fraction)),
                coarse_history_hash=_hash(c.tolist()),refined_history_hash=_hash(f.tolist()),
                generator_hash=_hash([g.tolist(),rx.tolist(),ry.tolist()]),diagnostics=diagnostics))
            if name=='full' and reference is None:
                reference=float((_matrix_exp(g,wave['elapsed_s'])@initial)[2]);work+=reference_work
    plus=int(np.flatnonzero(np.isclose(offsets,3.5,rtol=0,atol=1e-12))[0]);donor=int(np.flatnonzero(np.isclose(offsets,donor_shift_ppm,rtol=0,atol=1e-12))[0])
    zero=int(np.flatnonzero(np.isclose(offsets,0.,rtol=0,atol=1e-12))[0])
    metrics=dict(amide_exchange_contrast=float(spectra['no_amide'][plus]-spectra['full'][plus]),
        relayed_noe_contrast=float(spectra['no_cross'][donor]-spectra['full'][donor]),
        mt_contrast_at_zero=float(spectra['no_mt'][zero]-spectra['full'][zero]),
        mt_contrast_at_amide=float(spectra['no_mt'][plus]-spectra['full'][plus]),unsaturated_water=reference,
        max_normalized_trace_refinement_error=refinement,max_lag_kernel_error=kernel_error)
    validation=dict(target_min_amide_contrast=target_min_amide_contrast,target_min_relay_contrast=target_min_relay_contrast,
        target_memory_refinement_error=target_refinement_error,target_kernel_error=target_kernel_error,
        numerical_refinement_passed=bool(refinement<=target_refinement_error and kernel_error<=target_kernel_error and abs(reference-1.)<=1e-8))
    validation['passed']=bool(validation['numerical_refinement_passed'] and metrics['amide_exchange_contrast']>=target_min_amide_contrast and metrics['relayed_noe_contrast']>=target_min_relay_contrast)
    inputs=dict(offsets_ppm=offsets.tolist(),b0_t=b0_t,b1_uT=b1_uT,pulse_s=pulse_s,gap_s=gap_s,n_pulses=n_pulses,shape=shape,
        phase_cycle_rad=list(phase_cycle_rad),rf_bins=rf_bins,steps_per_bin=steps_per_bin,bound_fraction=bound_fraction,bound_to_water_hz=bound_to_water_hz,
        bound_t2_s=bound_t2_s,lineshape=lineshape,pair_fraction=pair_fraction,bridge_exchange_s1=bridge_exchange_s1,bridge_shift_ppm=bridge_shift_ppm,
        donor_shift_ppm=donor_shift_ppm,distance_m=distance_m,tau_c_s=tau_c_s,orientation_order=orientation_order,time_order=time_order,
        max_work=max_work,max_memory_bytes=max_memory_bytes,max_duration_s=max_duration_s,target_min_amide_contrast=target_min_amide_contrast,
        target_min_relay_contrast=target_min_relay_contrast,target_refinement_error=target_refinement_error,target_kernel_error=target_kernel_error)
    if _checked_sources()!=sources: raise ValueError('source changed during finite-memory CEST')
    return dict(clinical_question='How do finite shaped RF, semisolid coherence memory and signed Solomon relay alter CEST/MT targets near resonance?',
        design=inputs,offsets_ppm=offsets.tolist(),spectra=spectra,bound_spectra=bound_spectra,metrics=metrics,validation=validation,
        memory_diagnostics=dict(coarse_steps=n,refined_steps=2*n,rf_peak_uT=wave['peak_b1_uT'],
            numerical_refinement_passed=validation['numerical_refinement_passed'],normalized_trace_difference=refinement,
            lag_kernel_error=kernel_error,retained_history_s=wave['elapsed_s'],inter_pulse_reset=False),
        objective_loss=wave['rf_energy_uT2_s'],trajectories=trajectories,
        coarse_times_s=trace_indices*wave['dt_s'],refined_times_s=trace_indices*wave['dt_s'],
        scope='teaching/research homogeneous finite-history generalized Bloch semisolid + Cartesian liquids/longitudinal Solomon pair; authored molecular priors, not full molecular Redfield, measured calibration, spatial imaging or clinical/scanner certification; B/C parked',
        provenance=dict(version='generalized-memory-cest-v1',replay=inputs,input_hash=_hash(inputs),sources=sources,runtime=runtime_manifest(),
            waveform=wave,rf_holds_uT=field,dipolar_rates=rates,controls={k:list(v) for k,v in controls.items()},
            liquid_system=asdict(relay_pool_system(b0_t=b0_t,pair_fraction=pair_fraction,bridge_exchange_s1=bridge_exchange_s1,
                bridge_shift_ppm=bridge_shift_ppm,donor_shift_ppm=donor_shift_ppm)),estimated_work=work,planned_work=planned,
            estimated_peak_memory_bytes=peak,modeled_control_duration_s=duration,rf_energy_uT2_s=len(offsets)*len(controls)*wave['rf_energy_uT2_s'],
            trace_sampling=dict(coarse_indices=trace_indices.tolist(),total_coarse_nodes=n+1,total_refined_nodes=2*n+1,
                rule='about 256 uniform display nodes plus all RF changes; full-grid numerical comparison, maxima witnesses and full-state history hashes retained; replay recomputes every node'),
            history='entire offset experiment from equilibrium, including gaps and RF phase changes; no window cutoff or inter-pulse reset',
            semisolid='non-exponential Green-function RF convolution; common longitudinal reservoir; short transverse coherence, no coherent water-bound exchange',
            normalization='water equilibrium 1 and authored bound density; no fitted gain, offset clamp, replacement zero-frequency rate or sign clipping'))
