"""Pulsatile rigid-pipe flow -> finite slice RF -> causal trigger interruptions.

Teaching/research experiment; not patient hemodynamics, scanner firmware or
clinical certification. Input R peaks are already detected trigger timestamps.
"""
from hashlib import sha256
from pathlib import Path
import numpy as np
from .flow_imaging import MovingBlochEnsemble, selective_sinc
from .pulsatile_flow import WomersleyPipe, pipe_reservoir
from .causal_gating import plan_prospective_readouts
from .spatial_imaging import _hash

SCOPE=('research/teaching periodic pressure-driven Newtonian flow in a straight rigid circular pipe; '
       'finite sinc RF/Gz and causal detected-trigger controller; fixed radial coordinates; '
       'no compliance, turbulence, diffusion, ECG detection, scanner execution or clinical certification; B/C parked')


def _receive(spins,weights,thickness,ring_ids=None):
    mask=abs(spins.positions())<=thickness/2
    if mask.sum()<3 or (ring_ids is not None and np.any(np.bincount(ring_ids[mask],minlength=ring_ids.max()+1)<3)):
        raise ValueError('receive slab/radial ring undersampled; increase axial_spins')
    selected=weights[mask]; selected=selected/selected.sum()
    return mask,selected


def _run_cycle(spins,gate,inv,exc,weights,thickness,ring_ids):
    """Evolve even an interrupted preparation. Never rewind/discard spin state."""
    cutoff=gate['cancelled_s'] if gate['cancelled_s'] is not None else gate['readout_end_s']
    energy=0.; hard_started=False; mz=None; incoming=None; signal=None; receive_count=None; stage='trigger_latency'
    def wait_until(at,**kwargs):
        dt=min(at,cutoff)-spins.time
        if dt>1e-14: spins.advance(dt,**kwargs)
    def pulse(rf):
        nonlocal energy
        for b1 in rf['b1_uT']:
            dt=min(rf['dt_s'],cutoff-spins.time)
            if dt<=1e-14: break
            spins.advance(dt,b1_uT=complex(b1),gz_t_m=rf['gz_t_m'])
            energy+=float(b1*b1*dt)
    wait_until(gate['preparation_s'])
    if spins.time<cutoff-1e-14:
        hard_started=True; spins.hard_rf(180.); stage='selective_reinversion'; pulse(inv)
    if spins.time<cutoff-1e-14:
        stage='inversion_recovery'; wait_until(gate['readout_s'])
    if spins.time<cutoff-1e-14:
        mask,w=_receive(spins,weights,thickness,ring_ids)
        mz=float(np.sum(spins.state[mask,2]*w)); receive_count=int(mask.sum())
        incoming=float(np.sum((abs(spins.positions(gate['preparation_s'])[mask])>thickness/2)*w))
        stage='excitation'; pulse(exc)
    if spins.time<cutoff-1e-14:
        stage='rephaser'; wait_until(gate['readout_end_s'],gz_t_m=-exc['gz_t_m'])
    if gate['accepted']:
        mask,w=_receive(spins,weights,thickness,ring_ids)
        signal=complex(np.sum((spins.state[mask,0]+1j*spins.state[mask,1])*w))
        stage='completed'
    return dict(mean_mz=mz,signal=None if signal is None else [signal.real,signal.imag],
        geometric_incoming_fraction=incoming,receive_spins=receive_count,
        stage=stage,end_s=spins.time,preparation_started=hard_started,
        finite_rf_energy_uT2_s=energy,state_hash=_hash(spins.state.tolist()),
        positions_hash=_hash(spins.positions().tolist()))


def run_pulsatile_dir(*, r_peaks_s=(0.,1.2,2.4), observation_end_s=3.6,
                      inversion_time_s=.9, trigger_latency_s=.003, initial_rr_s=1.2,
                      rr_range_s=(.5,1.5), radius_m=.002, density_kg_m3=1060.,
                      viscosity_pa_s=.0035, mean_gradient_pa_m=100.,
                      oscillating_gradient_pa_m=200., frequency_hz=1., phase_rad=0.,
                      thickness_m=.005, radial_rings=8, axial_spins=401, rf_steps=128,
                      off_resonance_hz=0., blood_target_max=.1, wall_target_min=.7,
                      max_interrupted_fraction=0., max_work=10000000, max_duration_s=30.):
    """Execute scheduled RF even if a future trigger will interrupt its cycle.

    The explicit observation horizon is not an RR prediction. Last-trigger
    readout can complete without any following R peak. Targets require at least
    one completed readout and the declared bound on interrupted preparations.
    """
    numeric=[inversion_time_s,observation_end_s,thickness_m,off_resonance_hz,
             blood_target_max,wall_target_min,max_interrupted_fraction,max_duration_s]
    if not np.isfinite(numeric).all() or inversion_time_s<=.008 or thickness_m<=0 or not 0<blood_target_max<1 or not 0<wall_target_min<=1 or not 0<=max_interrupted_fraction<=1:
        raise ValueError('invalid timing, geometry or target')
    if observation_end_s>max_duration_s: raise ValueError('observation duration budget exceeded')
    for value,lo,hi in [(radial_rings,2,64),(axial_spins,33,10001),(rf_steps,16,8192),(max_work,1,10**12)]:
        if type(value) is not int or not lo<=value<=hi: raise ValueError('bounded integer quadrature/work required')
    gates=plan_prospective_readouts(r_peaks_s,delay_s=inversion_time_s,observation_end_s=observation_end_s,
        initial_rr_s=initial_rr_s,latency_s=trigger_latency_s,rr_range_s=rr_range_s)
    scheduled=[g for g in gates if g['scheduled']]
    total_spins=axial_spins*(radial_rings+1)
    planned_work=(len(scheduled)*(2*rf_steps+5)+1)*total_spins
    if planned_work>max_work: raise ValueError('pulsatile Bloch preflight work budget exceeded')
    pipe=WomersleyPipe(radius_m=radius_m,density_kg_m3=density_kg_m3,viscosity_pa_s=viscosity_pa_s,
        mean_gradient_pa_m=mean_gradient_pa_m,oscillating_gradient_pa_m=oscillating_gradient_pa_m,
        frequency_hz=frequency_hz,phase_rad=phase_rad)
    z,motion,weights,radii=pipe_reservoir(pipe,end_s=observation_end_s,thickness_m=thickness_m,
        radial_rings=radial_rings,axial_spins=axial_spins)
    blood=MovingBlochEnsemble(z,0.,motion=motion,off_hz=off_resonance_hz,max_work=max_work)
    wall=MovingBlochEnsemble(np.linspace(-2*thickness_m,2*thickness_m,axial_spins),0.,
        t1_s=1.,t2_s=.08,off_hz=off_resonance_hz,max_work=max_work)
    inv=selective_sinc(180.,thickness_m=thickness_m,steps=rf_steps)
    exc=selective_sinc(90.,thickness_m=thickness_m,duration_s=.004,steps=rf_steps)
    executions=[]; readouts=[]; total_work=0
    ring_ids=np.repeat(np.arange(radial_rings),axial_spins)
    for gate in scheduled:
        record=dict(gate=gate,tissues={})
        for name,spins,w,rings in [('blood',blood,weights,ring_ids),('wall',wall,np.ones(axial_spins),None)]:
            before=spins.work; spins.max_work=before+max_work-total_work
            record['tissues'][name]=_run_cycle(spins,gate,inv,exc,w,thickness_m,rings)
            total_work+=spins.work-before
        executions.append(record)
        if gate['accepted']:
            velocity=pipe.velocity(radii[::axial_spins],gate['readout_s'])
            record['flow']=dict(volume_flow_m3_s=pipe.volume_flow_m3_s(gate['readout_s']),
                ring_radius_m=radii[::axial_spins].tolist(),ring_velocity_m_s=velocity.tolist())
            readouts.append(record)
    # Explicitly account for the observed waiting interval after the final pulse.
    for spins in [blood,wall]:
        before=spins.work; spins.max_work=before+max_work-total_work
        dt=observation_end_s-spins.time
        if dt>1e-14: spins.advance(dt)
        total_work+=spins.work-before
    interrupted=sum(not g['accepted'] for g in scheduled)
    fraction=interrupted/len(scheduled) if scheduled else 0.
    validation=dict(completed_readouts=len(readouts),scheduled_preparations=len(scheduled),
        interrupted_preparations=interrupted,interrupted_fraction=fraction,
        max_interrupted_fraction=max_interrupted_fraction,blood_target_max=blood_target_max,wall_target_min=wall_target_min,passed=False)
    if readouts:
        bm=np.array([r['tissues']['blood']['mean_mz'] for r in readouts]); wm=np.array([r['tissues']['wall']['mean_mz'] for r in readouts])
        validation.update(max_abs_blood_mz=float(abs(bm).max()),min_abs_wall_mz=float(abs(wm).min()))
        validation['passed']=bool(abs(bm).max()<=blood_target_max and abs(wm).min()>=wall_target_min and fraction<=max_interrupted_fraction)
        loss=float(np.mean(abs(bm)/np.maximum(abs(wm),1e-12)))+fraction
    else:
        loss=2.+fraction  # explicit no-readout design penalty; never a fabricated measurement
    inputs=dict(r_peaks_s=list(r_peaks_s),observation_end_s=observation_end_s,inversion_time_s=inversion_time_s,
        trigger_latency_s=trigger_latency_s,initial_rr_s=initial_rr_s,rr_range_s=list(rr_range_s),
        **pipe.parameters,thickness_m=thickness_m,radial_rings=radial_rings,axial_spins=axial_spins,rf_steps=rf_steps,
        off_resonance_hz=off_resonance_hz,blood_target_max=blood_target_max,wall_target_min=wall_target_min,
        max_interrupted_fraction=max_interrupted_fraction,max_work=max_work,max_duration_s=max_duration_s)
    return dict(clinical_question='How do pressure-driven pulsatile shear flow and causally interrupted finite slice preparations change DIR suppression?',
        design=inputs,gates=gates,executions=executions,readouts=readouts,validation=validation,objective_loss=loss,
        objective='mean completed blood/wall |Mz| ratio plus interrupted fraction; no-readout penalty 2 plus fraction',scope=SCOPE,
        provenance=dict(version='pulsatile-causal-dir-v1',replay=inputs,input_hash=_hash(inputs),
            source_hash=_hash({p.name:sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('pulsatile_flow.py'),Path(__file__).with_name('flow_imaging.py'),Path(__file__).with_name('causal_gating.py')]}),
            estimated_work=total_work,planned_work=planned_work,duration_s=observation_end_s,womersley_alpha=float(pipe.alpha),
            reynolds_upper_bound=pipe.reynolds_bound,total_blood_spins=len(z),total_wall_spins=axial_spins,
            actual_finite_rf_energy_uT2_s=sum(r['tissues']['blood']['finite_rf_energy_uT2_s'] for r in executions),
            actual_hard_rf_count=sum(r['tissues']['blood']['preparation_started'] for r in executions),
            waveform_hash=_hash([inv['b1_uT'].tolist(),inv['gz_t_m'],exc['b1_uT'].tolist(),exc['gz_t_m']]),
            reservoir=dict(initial_position_hash=_hash(z.tolist()),quadrature_weight_hash=_hash(weights.tolist()),
                boundary='finite no-wrap reservoir bounding all motion; area/axial volume weights; each receive ring checked'),
            final_state_hashes={name:_hash(spins.state.tolist()) for name,spins in [('blood',blood),('wall',wall)]}))
