"""Quantum-relaxed homogeneous MRS with explicit finite RF / ADC / TR cycles.

This complements, but does not silently upgrade, the separate 3D PRESS chain.
No scalar T2 envelope, fitted signal gain, state renormalization or sign clipping.
"""
import numpy as np
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from mrqlab_physics.ops.quantum_relaxation import lindblad_generator,local_spin_bath,quantum_channel,periodic_density
from .mrs_basis import spin_hamiltonian,fit_full_basis
from .flow_imaging import selective_sinc
from .spatial_imaging import _hash
from .study_records import _checked_sources,runtime_manifest


def quantum_plan(count,rf_steps,points,dummy_scans):
    # Scaling/Taylor/squaring, channel composition, fixed point, full trajectory.
    size=(2**count)**2
    return dict(estimated_work=int((3*rf_steps*160+2048)*size**3+(4*points+dummy_scans+3*rf_steps)*size**2),
        estimated_peak_memory_bytes=int(16*(3*rf_steps+32)*size**2+64*(points+3*rf_steps+dummy_scans+16)*size))


def simulate_quantum_fid(offsets_hz,couplings_hz,*,t1_s,t2_s,echo_s=.03,repetition_s=.6,
                         dwell_s=.0005,points=256,rf_duration_s=.001,rf_steps=32,
                         excitation_degrees=90.,polarization=.01,preparation='periodic',dummy_scans=8,
                         coupling_model='isotropic',max_work=1000000000,max_memory_bytes=134217728):
    if type(points) is not int or not 16<=points<=1024 or type(rf_steps) is not int or not 16<=rf_steps<=256 or type(dummy_scans) is not int or not 0<=dummy_scans<=128:
        raise ValueError('bounded integer RF/FID/dummy-scan counts required')
    scalars=[echo_s,repetition_s,dwell_s,rf_duration_s,excitation_degrees,polarization]
    if not np.isfinite(scalars).all() or min(echo_s,repetition_s,dwell_s,rf_duration_s)<=0 or echo_s<=6*rf_duration_s or not 0<excitation_degrees<=180:
        raise ValueError('finite positive nonoverlapping RF/echo/TR design required')
    if preparation not in {'periodic','finite_dummies','equilibrium'}: raise ValueError('explicit periodic, finite_dummies or equilibrium preparation required')
    if any(type(v) is not int or v<=0 for v in [max_work,max_memory_bytes]): raise ValueError('positive integer resource budgets required')
    h,ops=spin_hamiltonian(offsets_hz,couplings_hz,coupling_model=coupling_model);d=len(h);size=d*d
    budget=quantum_plan(len(ops),rf_steps,points,dummy_scans)
    if budget['estimated_work']>max_work or budget['estimated_peak_memory_bytes']>max_memory_bytes:
        raise ValueError('quantum RF/TR work or memory budget exceeded before channel allocation')
    end_s=echo_s+rf_duration_s/2+points*dwell_s;recovery_s=repetition_s-end_s
    if recovery_s<0: raise ValueError('TR must include all finite pulses, echo delay and the entire ADC interval')
    bandwidth=2*(np.sum(abs(np.asarray(offsets_hz)))+np.sum(abs(np.asarray(couplings_hz)))/2)
    if bandwidth>=1/dwell_s: raise ValueError('spectral transitions exceed Nyquist')
    collapses,equilibrium,rates=local_spin_bath(ops,t1_s,t2_s,polarization=polarization)
    free=lindblad_generator(h,collapses)
    if np.max(abs(free@equilibrium.reshape(-1,order='F')))>1e-10:
        raise ValueError('authored bath product is not stationary for this Hamiltonian')
    x=sum(a[0] for a in ops);y=sum(a[1] for a in ops);z=sum(a[2] for a in ops)
    normalization=float(np.trace(z@equilibrium).real)
    rf=selective_sinc(90.,duration_s=rf_duration_s,thickness_m=.02,steps=rf_steps)
    events=[];at=0.;propagator=np.eye(size,dtype=complex);cache={}
    for start,flip,phase in [(0.,excitation_degrees,0.),(echo_s/4,180.,np.pi/2),(3*echo_s/4,180.,np.pi/2)]:
        if start>at:
            channel=quantum_channel(free,start-at);events.append((start-at,'free',channel));propagator=channel@propagator
        for b1 in rf['b1_uT']*flip/90:
            key=(float(b1),phase)
            if key not in cache:
                effective=h+2*np.pi*GAMMA_BAR_HZ_T*b1*1e-6*(np.cos(phase)*x+np.sin(phase)*y)
                cache[key]=quantum_channel(lindblad_generator(effective,collapses),rf['dt_s'])
            channel=cache[key];events.append((rf['dt_s'],'rf',channel));propagator=channel@propagator
        at=start+rf_duration_s
    echo_time=echo_s+rf_duration_s/2
    channel=quantum_channel(free,echo_time-at);events.append((echo_time-at,'free',channel));propagator=channel@propagator
    adc=quantum_channel(free,dwell_s);adc_full=quantum_channel(free,points*dwell_s)
    # Ideal independent-spin dephasing is a declared CPTP channel; it is not a
    # simulated spatial crusher and also removes zero-quantum off-diagonals.
    spoiler=np.diag(np.eye(d).reshape(-1,order='F'))
    recovery=quantum_channel(free,recovery_s);cycle=recovery@spoiler@adc_full@propagator
    steady,fixed=periodic_density(cycle,d)
    eq=equilibrium.reshape(-1,order='F');steady_vec=steady.reshape(-1,order='F')
    transient=[eq.copy()]
    for _ in range(dummy_scans): transient.append(cycle@transient[-1])
    start_state=steady_vec if preparation=='periodic' else transient[-1] if preparation=='finite_dummies' else eq
    state=start_state.copy();histories=[state.copy()];times=[0.];stages=['start'];at=0.
    for duration,kind,channel in events:
        state=channel@state;at+=duration;histories.append(state.copy());times.append(at);stages.append(kind)
    fid=[];equilibrium_fid=[];control=propagator@eq;detector=x+1j*y
    for i in range(points):
        fid.append(np.trace(state.reshape((d,d),order='F')@detector)/normalization)
        equilibrium_fid.append(np.trace(control.reshape((d,d),order='F')@detector)/normalization);control=adc@control
        state=adc@state;histories.append(state.copy());times.append(echo_time+(i+1)*dwell_s);stages.append('adc')
    state=spoiler@state;histories.append(state.copy());times.append(end_s);stages.append('ideal_dephase')
    state=recovery@state;histories.append(state.copy());times.append(repetition_s);stages.append('recovery')
    states=np.array(histories).reshape((-1,d,d),order='C').transpose(0,2,1)
    # The conversion above unpacks column-major vectors independently per node.
    traces=np.trace(states,axis1=1,axis2=2)
    hermiticity=float(np.max(abs(states-states.conj().transpose(0,2,1))))
    minimum=float(np.linalg.eigvalsh((states+states.conj().transpose(0,2,1))/2).min())
    trace_error=float(np.max(abs(traces-1)))
    periodic_error=float(np.max(abs(state-start_state)))
    trajectory=dict(times_s=times,stages=stages,
        longitudinal=[np.trace(r@z).real/normalization for r in states],
        transverse=[np.trace(r@detector)/normalization for r in states],
        state_hash=_hash([states.real.tolist(),states.imag.tolist()]),
        start_density=start_state.reshape((d,d),order='F'),echo_density=histories[len(events)].reshape((d,d),order='F'),
        end_density=state.reshape((d,d),order='F'),equilibrium_density=equilibrium,periodic_density=steady,
        dummy_start_longitudinal=[float(np.trace(v.reshape((d,d),order='F')@z).real/normalization) for v in transient],
        dummy_distance_to_periodic=[float(np.max(abs(v-steady_vec))) for v in transient])
    return np.asarray(fid),dict(**budget,relaxation_rates=rates,trajectory=trajectory,equilibrium_fid=np.asarray(equilibrium_fid),
        spin_specification=dict(offsets_hz=list(offsets_hz),couplings_hz=np.asarray(couplings_hz).tolist(),t1_s=list(t1_s),t2_s=list(t2_s),
            polarization=polarization,rf_steps=rf_steps,excitation_degrees=excitation_degrees,coupling_model=coupling_model),
        diagnostics=dict(**fixed,max_trace_error=trace_error,max_hermiticity_error=hermiticity,minimum_density_eigenvalue=minimum,
            cycle_return_error=periodic_error,preparation=preparation,physical_state_passed=bool(trace_error<=1e-10 and hermiticity<=1e-10 and minimum>=-1e-10)),
        timing=dict(echo_time_s=echo_time,adc_end_s=end_s,recovery_s=recovery_s,repetition_s=repetition_s,adc_points=points,adc_interval_s=points*dwell_s),
        cycle_hash=_hash([cycle.real.tolist(),cycle.imag.tolist()]),rf_hash=_hash(rf['b1_uT'].tolist()),
        normalization=dict(equilibrium_total_iz=normalization,convention='detect total Ix+iIy divided by authored equilibrium total Iz; no fitted gain'),
        relaxation='independent-spin thermal amplitude damping plus pure dephasing during every finite RF, free, ADC and recovery interval; no scalar envelope',
        spoiler='ideal complete dephasing in product Iz basis at ADC end; not spatial gradient/crusher simulation')


def run_mrs_quantum(*,echo_s=.03,repetition_s=.6,points=256,dwell_s=.0005,rf_duration_s=.001,rf_steps=32,refine_rf_steps=64,
                    excitation_degrees=90.,polarization=.01,preparation='periodic',dummy_scans=8,basis_mode='matched',
                    basis_t1_scale=1.,sample_t1_scale=1.,basis_j_hz=7.,sample_j_hz=7.,amounts=(.02,.008),
                    max_work=1500000000,max_memory_bytes=134217728,target_relative_amount_error=.05,
                    target_rf_error=.002,target_fit_residual=.02,target_state_error=1e-10,target_min_signal_fraction=.2):
    sources=_checked_sources();truth=np.asarray(amounts,float)
    if truth.shape!=(2,) or not np.isfinite(truth).all() or np.any(truth<=0) or basis_mode not in {'matched','equilibrium'}:
        raise ValueError('two positive teaching amounts and matched/equilibrium basis required')
    values=[basis_t1_scale,sample_t1_scale,basis_j_hz,sample_j_hz,target_relative_amount_error,target_rf_error,target_fit_residual,target_state_error,target_min_signal_fraction]
    if not np.isfinite(values).all() or min(*values[:2],*values[4:])<=0: raise ValueError('finite molecular priors and positive validation targets required')
    if type(refine_rf_steps) is not int or type(rf_steps) is not int or not 16<=rf_steps<refine_rf_steps<=256:
        raise ValueError('explicitly finer RF grid required')
    if any(type(v) is not int or v<=0 for v in [max_work,max_memory_bytes]): raise ValueError('positive integer complete-workflow budgets required')
    if type(points) is not int or type(dummy_scans) is not int: raise ValueError('integer FID and dummy counts required')
    settings=[([-213.3],[[0.]],[1.1],[.15]),([-300.,-270.],[[0.,basis_j_hz],[basis_j_hz,0.]],[.7,1.7],[.08,.18])]
    plans=[quantum_plan(len(freq),steps,points,dummy_scans) for freq,_,_,_ in settings for steps in [rf_steps,refine_rf_steps,refine_rf_steps,2*refine_rf_steps]]
    if 2*refine_rf_steps>256: raise ValueError('finest sample RF reference exceeds 256 steps')
    planned=sum(p['estimated_work'] for p in plans)+points*1024
    peak=sum(p['estimated_peak_memory_bytes'] for p in plans)
    if planned>max_work or peak>max_memory_bytes: raise ValueError('complete quantum MRS work or memory budget exceeded before simulation')
    records=[];basis=[];sample=[];rf_error=[];signal_fractions=[];work=points*1024
    for freq,j,t1,t2 in settings:
        columns=[]
        for role,steps in [('basis',rf_steps),('basis_rf_reference',refine_rf_steps),('sample',refine_rf_steps),('sample_rf_reference',2*refine_rf_steps)]:
            sample_role=role.startswith('sample');coupling=sample_j_hz if sample_role else basis_j_hz
            matrix=[[0.,coupling],[coupling,0.]] if len(freq)==2 else j
            fid,record=simulate_quantum_fid(freq,matrix,t1_s=np.array(t1)*(sample_t1_scale if sample_role else basis_t1_scale),t2_s=t2,
                echo_s=echo_s,repetition_s=repetition_s,points=points,dwell_s=dwell_s,rf_duration_s=rf_duration_s,rf_steps=steps,
                excitation_degrees=excitation_degrees,polarization=polarization,
                preparation='equilibrium' if not sample_role and basis_mode=='equilibrium' else preparation,dummy_scans=dummy_scans,
                max_work=max_work-work,max_memory_bytes=max_memory_bytes)
            record['role']=role;record['component']='singlet' if len(freq)==1 else 'synthetic_AB';records.append(record)
            work+=record['estimated_work'];columns.append(fid)
        basis.append(columns[0]);sample.append(columns[2])
        rf_error.extend([float(np.linalg.norm(columns[i]-columns[i+1])/np.linalg.norm(columns[i+1])) for i in [0,2]])
        signal_fractions.append(float(np.linalg.norm(columns[2])/np.linalg.norm(records[-2]['equilibrium_fid'])))
    basis=np.asarray(basis).T;signal=np.asarray(sample).T@truth
    fit=fit_full_basis(signal,basis,dwell_s=dwell_s,max_relative_residual=target_fit_residual)
    error=float(np.max(abs(np.asarray(fit['amounts'])/truth-1)))
    max_state=max(max(r['diagnostics']['max_trace_error'],r['diagnostics']['max_hermiticity_error'],max(0.,-r['diagnostics']['minimum_density_eigenvalue'])) for r in records)
    max_fixed=max(r['diagnostics']['fixed_point_residual'] for r in records)
    max_cycle=max([r['diagnostics']['cycle_return_error'] for r in records if r['diagnostics']['preparation']=='periodic'] or [0.])
    validation=dict(max_relative_amount_error=error,target=target_relative_amount_error,target_fit_residual=target_fit_residual,
        max_rf_error=max(rf_error),target_rf_error=target_rf_error,max_state_error=max_state,target_state_error=target_state_error,
        max_fixed_point_residual=max_fixed,max_periodic_return_error=max_cycle,min_signal_fraction=min(signal_fractions),target_min_signal_fraction=target_min_signal_fraction,
        numerical_refinement_passed=bool(max(rf_error)<=target_rf_error and max_state<=target_state_error and max_fixed<=target_state_error and max_cycle<=target_state_error))
    validation['passed']=bool(validation['numerical_refinement_passed'] and error<=target_relative_amount_error and fit['passed'] and min(signal_fractions)>=target_min_signal_fraction)
    inputs=dict(echo_s=echo_s,repetition_s=repetition_s,points=points,dwell_s=dwell_s,rf_duration_s=rf_duration_s,rf_steps=rf_steps,refine_rf_steps=refine_rf_steps,
        excitation_degrees=excitation_degrees,polarization=polarization,preparation=preparation,dummy_scans=dummy_scans,basis_mode=basis_mode,
        basis_t1_scale=basis_t1_scale,sample_t1_scale=sample_t1_scale,basis_j_hz=basis_j_hz,sample_j_hz=sample_j_hz,amounts=truth.tolist(),
        max_work=max_work,max_memory_bytes=max_memory_bytes,target_relative_amount_error=target_relative_amount_error,target_rf_error=target_rf_error,
        target_fit_residual=target_fit_residual,target_state_error=target_state_error,target_min_signal_fraction=target_min_signal_fraction)
    if _checked_sources()!=sources: raise ValueError('source changed during quantum MRS')
    return dict(clinical_question='How do finite RF, independent-spin quantum relaxation and repeated-TR saturation bias full complex spectral amounts?',
        design=inputs,names=['teaching_singlet','synthetic_AB'],signal=signal,basis=basis,fit=fit,teaching_truth=truth,validation=validation,
        objective_loss=float(repetition_s),rf_refinement_errors=rf_error,signal_fractions=signal_fractions,simulations=records,
        quantum_diagnostics=dict(preparation=preparation,basis_mode=basis_mode,numerical_refinement_passed=validation['numerical_refinement_passed'],
            timing=records[2]['timing'],minimum_density_eigenvalue=min(r['diagnostics']['minimum_density_eigenvalue'] for r in records),
            max_periodic_return_error=max_cycle,components=[dict(name=name,authored_amount=float(amount),recovered_amount=float(recovered),signal_fraction=float(fraction))
                for name,amount,recovered,fraction in zip(['teaching_singlet','synthetic_AB'],truth,fit['amounts'],signal_fractions)]),
        scope='teaching/research homogeneous spin-1/2 local Lindblad baths and exact repeated-TR channel; authored T1/T2/polarization/J, ideal independent dephasing; not molecular Redfield, spatial PRESS/crusher simulation, measured concentration calibration or clinical/scanner certification; B/C parked',
        provenance=dict(version='quantum-tr-mrs-v1',replay=inputs,input_hash=_hash(inputs),sources=sources,runtime=runtime_manifest(),
            estimated_work=work,planned_work=planned,estimated_peak_memory_bytes=peak,
            basis_hash=_hash([basis.real.tolist(),basis.imag.tolist()]),signal_hash=_hash([signal.real.tolist(),signal.imag.tolist()]),
            normalization='unit authored equilibrium total longitudinal polarization per spin system; amounts are signal weights, not molarity',
            acquisition='complete finite RF, free evolution, point ADC, ideal dephasing and physical recovery inside TR; periodic density solves full composed channel with trace constraint'))
