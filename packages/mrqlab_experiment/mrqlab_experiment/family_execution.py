"""Explicit teaching execution for the new sequence designs, reusing backends.

No scanner claims: ideal RF, sparse 3D encodings, rectangular PGSE and ideal
PRESS slabs. Suppressed blood is an inflow boundary condition, not CFD.
"""
from dataclasses import replace
import numpy as np

from mrqlab_physics import SimResult, Phantom
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from mrqlab_physics.backends.bloch import BlochBackend
from mrqlab_physics.backends.epg import EPGBackend
from mrqlab_physics.backends.spectral import SpectralBackend
from mrqlab_physics.kernel.scheduler import schedule, preflight_schedule
from mrqlab_physics.kernel.runner import run_backend
from mrqlab_physics.ops.types import Relax, Shift, GradInterval, RfOp, AdcSample
from mrqlab_physics.ops.rf import rotate_cartesian
from mrqlab_sequence import build_sequence
from .gradient import DiffusionSpec, calculate_diffusion_b_value, generate_diffusion_waveform


class FamilyWorkError(ValueError):
    """A family simulation failed after consuming the attached work amount."""

    def __init__(self, message, estimated_work):
        super().__init__(message)
        self.estimated_work = int(estimated_work)


def ssfp_steady_state(t1, t2, tr, flip_angle, off_resonance_hz=0., density=1.):
    """Exact fixed point in the alternating-RF rotating frame at TE=TR/2.

    Solve the affine Bloch map rather than assume the short-TR approximation.
    RF phases alternate 0/pi, equivalent to pi phase advance per TR.
    """
    values=(t1,t2,tr,flip_angle,off_resonance_hz,density)
    if not np.isfinite(values).all() or min(t1,t2,tr)<=0 or not 0<flip_angle<180 or density<0:
        raise ValueError('invalid SSFP parameters')
    a=np.deg2rad(flip_angle)
    rotation=rotate_cartesian(np.eye(3),a,0).T
    theta=2*np.pi*off_resonance_hz*tr+np.pi
    z=np.array([[np.cos(theta),-np.sin(theta),0],[np.sin(theta),np.cos(theta),0],[0,0,1.]])
    e1,e2=np.exp(-tr/t1),np.exp(-tr/t2)
    pre=np.linalg.solve(np.eye(3)-z@np.diag([e2,e2,e1])@rotation,np.array([0.,0.,density*(1-e1)]))
    post=rotation@pre
    return complex(post[0]+1j*post[1])*np.exp(-tr/(2*t2))*np.exp(1j*np.pi*off_resonance_hz*tr)


def adc_map(b_values, signals):
    """Voxelwise log-linear ADC (mm²/s); b axis first, no noise-floor correction."""
    b=np.asarray(b_values,float); s=np.asarray(signals,float)
    if b.ndim!=1 or b.size<2 or s.ndim<1 or s.shape[0]!=b.size or not np.isfinite(b).all() or np.any(b<0) or np.ptp(b)==0:
        raise ValueError('ADC requires >=2 distinct finite nonnegative b values')
    if not np.isfinite(s).all() or np.any(s<=0):
        raise ValueError('ADC requires positive finite signals')
    centered=b-b.mean()
    return -np.tensordot(centered,np.log(s),axes=(0,0))/np.sum(centered**2)


def _spoil(backend):
    for _, member in backend.members:
        _spoil(member)
    backend.omega[:2]=0
    z=backend.omega[2,backend.zero]
    backend.omega[2]=0; backend.omega[2,backend.zero]=z


class _PartitionBackend:
    def __init__(self, backend, tr):
        self.backend=backend; self.tr=tr; self.partition=0
    def apply(self, op):
        part=int((op.t+1e-10)//self.tr)
        if part>self.partition:
            _spoil(self.backend); self.partition=part
        self.backend.apply(op)
    def observe(self): return self.backend.observe()
    def snapshot(self): return self.backend.snapshot()


def simulate_family(sequence, phantom, scanner, options):
    family=sequence.metadata['research_family']; m=sequence.metadata
    width=3*(2*options.epg_kmax+1)*len(phantom.resolved_isochromats()) if family=='TSE3D' else 3*len(phantom.resolved_isochromats())*max(1,len(phantom.pools))
    if family=='SSFP' and m['double_inversion']:
        width*=2
    plan=preflight_schedule(sequence, options, max_operators=options.max_work//width)
    if plan.operator_count*width>options.max_work:
        raise ValueError('family simulation exceeds max_work')
    assumptions=[]; extra={}; warm_ops=0
    if family=='TSE3D':
        backend=EPGBackend(phantom,options.epg_kmax)
        # Converge a spoiled repeated TSE train, reusing authored RF ramp.
        from mrqlab_sequence import SequenceIR, Channel
        one=SequenceIR(name='TSE steady preparation',duration=m['tr'],channels=[
            Channel(name=c.name,events=[e for e in c.events if e.time<m['tr']]) for c in sequence.channels],
            metadata={**m,'epg_dk_events':[e for e in m['epg_dk_events'] if e['time']<m['tr']]})
        ops=schedule(one,options)
        for iteration in range(256):
            previous=backend.omega.copy()
            run_backend(backend,ops,False); _spoil(backend); warm_ops+=len(ops)
            if (warm_ops+plan.operator_count)*width>options.max_work:
                # ``ops`` has already run for this iteration. Surface that
                # consumed preparation work to callers that keep an attempt
                # ledger instead of pretending a failed tissue was free.
                raise FamilyWorkError('TSE steady preparation exceeds max_work',warm_ops*width)
            if np.max(np.abs(backend.omega-previous))<1e-9:
                break
        else: raise ValueError('TSE steady preparation did not converge')
        backend=_PartitionBackend(backend,m['tr'])
        assumptions=['spoiled periodic TSE preparation','ideal hard CPMG pulses',m['flip_strategy'],'sparse ky train per kz; no 3D image reconstruction']
        extra['steady_preparation_trains']=iteration+1
        extra['preparation_duration_s']=(iteration+1)*m['tr']
        extra['preparation_rf_energy_relative']=(iteration+1)*sum((e.value/180)**2 for e in one.channel('rf_amp'))
    elif family=='SSFP':
        if m['double_inversion']:
            fraction=m['inflow_fraction'] if m.get('blood_compartment',False) else 0.
            spins=[]
            for spin in phantom.resolved_isochromats():
                spins.extend((replace(spin,weight=spin.weight*(1-fraction)),replace(spin,weight=spin.weight*fraction)))
            class InflowBackend(BlochBackend):
                def apply(self,op):
                    if isinstance(op,RfOp) and abs(op.t-.000001)<1e-12:
                        # Resident members see the local reinversion; incoming
                        # members were outside that slab at preparation time.
                        self.state[::2]=rotate_cartesian(self.state[::2],op.alpha_rad,op.phase_rad)
                    else:
                        super().apply(op)
            backend=InflowBackend(tuple(spins),scanner)
            assumptions += ['explicit nonselective and local inversion pulses',
                'resident and incoming members; incoming spins outside local slab at preparation',
                'fixed mixture at readout; no continuing replacement during train','short transient readout after preparation']
        else:
            backend=BlochBackend(phantom.resolved_isochromats(),scanner)
        assumptions += ['balanced SSFP; alternating RF phase; no spoiling']
    elif family=='EPSE':
        class PointEchoBackend(EPGBackend):
            def apply(self, op):
                if not isinstance(op, Shift):
                    super().apply(op)
        backend=PointEchoBackend(replace(phantom,diffusion_adc_mm2_s=None),0)
        spec=DiffusionSpec(g_max_mt_m=max(m['diffusion_gradient_mt_m'],1e-15),delta_small_ms=m['delta_s']*1000,delta_big_ms=m['separation_s']*1000)
        b=calculate_diffusion_b_value(spec) if m['diffusion_gradient_mt_m'] else 0.
        from mrqlab_recon.trajectories import generate_trajectory, TrajectorySpec
        extra.update(b_reference_s_mm2=b,diffusion_waveform=generate_diffusion_waveform(spec),
                     epi_trajectory=generate_trajectory(TrajectorySpec(matrix_size=m['epi_lines'],fill_order='epi')))
        # Integrate b from the actual authored gz intervals, in the toggling
        # frame of the refocuser. This is independent of the formula above.
        q=0.; b_integral=0.; sign=1.; b_samples=[]
        for op in schedule(sequence,options):
            if isinstance(op,RfOp) and abs(abs(op.alpha_rad)-np.pi)<1e-9:
                sign=-sign
            elif isinstance(op,GradInterval):
                a=sign*2*np.pi*GAMMA_BAR_HZ_T*op.gradient[2]*1e-3
                b_integral+=(q*q*op.dt+q*a*op.dt**2+a*a*op.dt**3/3)*1e-6
                q+=a*op.dt
            elif isinstance(op,AdcSample):
                b_samples.append(b_integral)
        extra['b_value_s_mm2']=float(b_samples[0])
        extra['b_samples_s_mm2']=b_samples
        assumptions=['isotropic Gaussian PGSE attenuation from rectangular diffusion lobes','EPI imaging gradients excluded from b; no eddy currents or distortion']
    else:
        half=m['voxel_size_m']/2
        spins=tuple(replace(spin,weight=spin.weight if all(abs(x)<=half for x in spin.position_m) else 0.) for spin in phantom.resolved_isochromats())
        if sum(s.weight for s in spins)<=0:
            raise ValueError('PRESS voxel contains no sample spins')
        backend=SpectralBackend(replace(phantom,isochromats=spins),scanner)
        assumptions=[m['localization'],'independent Lorentzian singlets; no exchange or J coupling']
    trace=run_backend(backend,schedule(sequence,options),False)
    signal=trace.signal
    if family=='PRESS':
        signal=signal*sum(pool.fraction for pool in phantom.pools)
    if family=='EPSE':
        signal=signal*np.exp(-np.asarray(extra['b_samples_s_mm2'])*(phantom.diffusion_adc_mm2_s or 0.))
    return SimResult(signal=signal,k_trajectory=trace.k_trajectory*(GAMMA_BAR_HZ_T*1e-3 if family=="EPSE" else 1.),
        meta=dict(engine=m['preferred_engine'],n_ops=plan.operator_count+warm_ops,
                  estimated_work=(plan.operator_count+warm_ops)*width,assumptions=assumptions,**extra))
