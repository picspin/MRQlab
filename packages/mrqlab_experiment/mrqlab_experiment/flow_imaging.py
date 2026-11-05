"""Prescribed through-plane trajectories with finite selective RF and gating.

Research/teaching only. This is Lagrangian Bloch propagation, not CFD, scanner
execution, physiological validation or clinical image-quality certification.
"""
from pathlib import Path
from hashlib import sha256
import numpy as np
from mrqlab_physics.ops.rf import rotate_cartesian
from mrqlab_physics.ops.relax import relaxation_factors
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from .spatial_imaging import _hash

GAMMA = 2*np.pi*GAMMA_BAR_HZ_T
SCOPE = ('research/teaching prescribed constant through-plane velocities; finite sinc RF '
         'and simultaneous Gz; retrospective known-trigger gating; no CFD, pulsatile '
         'hemodynamics, scanner validation or clinical quality certification; B/C parked')


class MovingBlochEnsemble:
    """Each spin keeps state on a constant-velocity or analytic motion trajectory.

    No boundary reset, mixture fraction or modulo wrap. Non-RF intervals have
    exact constant-velocity phase integral; finite RF uses midpoint field
    rotation and symmetric relaxation splitting, converging as dt decreases.
    """
    def __init__(self, z0_m, velocity_m_s, *, t1_s=1.6, t2_s=.15, off_hz=0.,
                 max_work=10000000, motion=None):
        self.motion = motion
        self.z0 = np.array(z0_m, dtype=float, copy=True)
        self.velocity = np.broadcast_to(np.asarray(velocity_m_s, float), self.z0.shape).copy()
        if self.z0.ndim != 1 or not self.z0.size or not np.isfinite(self.z0).all() or not np.isfinite(self.velocity).all():
            raise ValueError('finite nonempty position/velocity vectors required')
        if not np.isfinite([t1_s, t2_s, off_hz]).all() or min(t1_s, t2_s) <= 0:
            raise ValueError('positive finite relaxation and finite off resonance required')
        if type(max_work) is not int or max_work < 1:
            raise ValueError('positive integer work budget required')
        self.t1 = t1_s; self.t2 = t2_s; self.off_hz = off_hz
        self.state = np.zeros((len(self.z0), 3)); self.state[:, 2] = 1.
        self.time = 0.; self.work = 0; self.max_work = max_work

    def positions(self, time_s=None):
        at = self.time if time_s is None else time_s
        return self.motion.positions(self.z0, at) if self.motion is not None else self.z0+self.velocity*at

    def hard_rf(self, degrees, phase_rad=0.):
        if not np.isfinite([degrees, phase_rad]).all(): raise ValueError('finite RF required')
        self._charge(); self.state = rotate_cartesian(self.state, np.deg2rad(degrees), phase_rad)

    def _charge(self):
        if self.work+len(self.z0) > self.max_work: raise ValueError('moving Bloch work budget exceeded')
        self.work += len(self.z0)

    def _relax(self, dt):
        e1, e2 = relaxation_factors(dt, self.t1, self.t2)
        self.state[:, :2] *= e2
        self.state[:, 2] = 1.+(self.state[:, 2]-1.)*e1

    def advance(self, dt_s, *, b1_uT=0j, gz_t_m=0.):
        if not np.isfinite([dt_s, b1_uT.real, b1_uT.imag, gz_t_m]).all() or dt_s <= 0:
            raise ValueError('positive finite interval and finite RF/gradient required')
        self._charge()
        phase = 2*np.pi*self.off_hz*dt_s+GAMMA*gz_t_m*self.positions(self.time+dt_s/2)*dt_s
        if b1_uT == 0:
            if self.motion is not None:
                phase = 2*np.pi*self.off_hz*dt_s+GAMMA*gz_t_m*self.motion.position_integral(self.z0,self.time,self.time+dt_s)
            transverse = (self.state[:, 0]+1j*self.state[:, 1])*np.exp(1j*phase)
            self.state[:, 0] = transverse.real; self.state[:, 1] = transverse.imag
            self._relax(dt_s)
        else:
            self._relax(dt_s/2)
            angle = np.column_stack((np.full(len(phase), GAMMA*b1_uT.real*1e-6*dt_s),
                np.full(len(phase), GAMMA*b1_uT.imag*1e-6*dt_s), phase))
            theta = np.linalg.norm(angle, axis=1)
            axis = np.divide(angle, theta[:, None], out=np.zeros_like(angle), where=theta[:, None] != 0)
            cosine = np.cos(theta)[:, None]; sine = np.sin(theta)[:, None]
            self.state = self.state*cosine+np.cross(axis, self.state)*sine+axis*np.sum(axis*self.state, axis=1)[:, None]*(1-cosine)
            self._relax(dt_s/2)
        self.time += dt_s


def selective_sinc(flip_degrees, *, thickness_m=.005, duration_s=.008, steps=128, time_bandwidth=4.):
    if not np.isfinite([flip_degrees, thickness_m, duration_s, time_bandwidth]).all() or min(thickness_m, duration_s, time_bandwidth) <= 0:
        raise ValueError('finite RF and positive slice parameters required')
    if type(steps) is not int or not 16 <= steps <= 1000000: raise ValueError('at least 16 RF steps required')
    dt = duration_s/steps
    shape = np.sinc(time_bandwidth*((np.arange(steps)+.5)/steps-.5))
    if abs(shape.sum()) < 1e-12: raise ValueError('RF waveform has zero area')
    b1 = shape*np.deg2rad(flip_degrees)/(GAMMA*1e-6*dt*shape.sum())
    gz = time_bandwidth/(GAMMA_BAR_HZ_T*thickness_m*duration_s)
    return dict(b1_uT=b1, gz_t_m=gz, dt_s=dt, duration_s=duration_s,
                rf_energy_uT2_s=float(np.sum(b1*b1)*dt))


def plan_gated_readouts(r_peaks_s, *, delay_s, window_s=.006, rr_range_s=(.5, 1.5)):
    """Retrospective acceptance using actual next R peak, never a predicted RR."""
    peaks = np.asarray(r_peaks_s, float)
    if peaks.ndim != 1 or not 2 <= len(peaks) <= 1000 or not np.isfinite(peaks).all() or peaks[0] < 0 or np.any(np.diff(peaks) <= 0):
        raise ValueError('strictly increasing finite R peaks required')
    if len(rr_range_s) != 2 or not np.isfinite([delay_s, window_s, *rr_range_s]).all() or min(delay_s, window_s, *rr_range_s) <= 0 or rr_range_s[0] > rr_range_s[1]:
        raise ValueError('positive delay/window and ordered RR interval required')
    events = []
    for i, r in enumerate(peaks):
        rr = float(peaks[i+1]-r) if i+1 < len(peaks) else None
        reason = 'no_following_trigger' if rr is None else 'rr_outside_range' if not rr_range_s[0] <= rr <= rr_range_s[1] else 'crosses_next_trigger' if delay_s+window_s > rr else None
        events.append(dict(trigger=i, preparation_s=float(r), readout_s=float(r+delay_s),
            readout_end_s=float(r+delay_s+window_s), rr_s=rr, accepted=reason is None, rejection=reason))
    return events


def run_flow_imaging(*, r_peaks_s=(0., 1.2, 2.4), inversion_time_s=.9,
                     blood_velocity_m_s=.025, thickness_m=.005, rf_steps=128,
                     spin_count=801, off_resonance_hz=0., rr_range_s=(.5, 1.5),
                     max_work=10000000, max_duration_s=30.,
                     blood_target_max=.1, wall_target_min=.7):
    """DIR design -> persistent moving spins -> accepted readouts -> targets/replay.

    Hard nonselective inversion followed by finite sinc selective reinversion;
    finite selective 90° excitation and half-area gradient rephasing at readout.
    Blood null target uses pre-excitation mean Mz; measured complex excitation
    signal is retained separately (RF profile and phase can change it).
    """
    numeric = [inversion_time_s, blood_velocity_m_s, thickness_m, off_resonance_hz,
               max_duration_s, blood_target_max, wall_target_min]
    if not np.isfinite(numeric).all() or inversion_time_s <= .008 or thickness_m <= 0 or max_duration_s <= 0 or not 0 < blood_target_max < 1 or not 0 < wall_target_min <= 1:
        raise ValueError('invalid flow design or target')
    if type(spin_count) is not int or not 33 <= spin_count <= 100001 or type(max_work) is not int or max_work <= 0:
        raise ValueError('bounded integer spin count/work required')
    gates = plan_gated_readouts(r_peaks_s, delay_s=inversion_time_s, rr_range_s=rr_range_s)
    accepted = [g for g in gates if g['accepted']]
    if not accepted: raise ValueError('no accepted cardiac cycles')
    if type(rf_steps) is not int or not 16 <= rf_steps <= 8192:
        raise ValueError('RF steps must be an integer from 16 to 8192')
    planned_work = 2*len(accepted)*(2*rf_steps+4)*spin_count
    if planned_work > max_work: raise ValueError('moving Bloch preflight work budget exceeded')
    end = accepted[-1]['readout_end_s']
    if end > max_duration_s: raise ValueError('gated duration budget exceeded')
    inv = selective_sinc(180., thickness_m=thickness_m, steps=rf_steps)
    exc = selective_sinc(90., thickness_m=thickness_m, duration_s=.004, steps=rf_steps)
    # Finite upstream reservoir covers all receive spins through the final readout.
    travel = blood_velocity_m_s*end; margin = 2*thickness_m
    blood_z = np.linspace(min(0., -travel)-margin, max(0., -travel)+margin, spin_count)
    wall_z = np.linspace(-margin, margin, spin_count)
    blood = MovingBlochEnsemble(blood_z, blood_velocity_m_s, max_work=max_work, off_hz=off_resonance_hz)
    wall = MovingBlochEnsemble(wall_z, 0., t1_s=1., t2_s=.08, max_work=max_work, off_hz=off_resonance_hz)
    records = []; total_work = 0
    for gate in accepted:
        record = dict(gate=gate, tissues={})
        for name, spins in [('blood', blood), ('wall', wall)]:
            before_work = spins.work
            # One shared budget across both tissues and all accepted cycles.
            spins.max_work = spins.work+(max_work-total_work)
            gap = gate['preparation_s']-spins.time
            if gap > 1e-12: spins.advance(gap)
            spins.hard_rf(180.)
            for b1 in inv['b1_uT']:
                spins.advance(inv['dt_s'], b1_uT=complex(b1), gz_t_m=inv['gz_t_m'])
            gap = gate['readout_s']-spins.time
            if gap <= 0: raise ValueError('selective preparation overlaps readout')
            spins.advance(gap)
            receive = abs(spins.positions()) <= thickness_m/2
            if receive.sum() < 3: raise ValueError('receive slab undersampled; increase spin_count')
            mz = float(spins.state[receive, 2].mean())
            incoming = abs(spins.positions(gate['preparation_s'])[receive]) > thickness_m/2
            for b1 in exc['b1_uT']:
                spins.advance(exc['dt_s'], b1_uT=complex(b1), gz_t_m=exc['gz_t_m'])
            spins.advance(.002, gz_t_m=-exc['gz_t_m'])  # cancel half of 4 ms excitation area
            receive_after = abs(spins.positions()) <= thickness_m/2
            if receive_after.sum() < 3: raise ValueError('receive slab undersampled after excitation')
            signal = complex(np.mean(spins.state[receive_after, 0]+1j*spins.state[receive_after, 1]))
            record['tissues'][name] = dict(mean_mz=mz, signal=[signal.real, signal.imag],
                receive_spins=int(receive.sum()), geometric_incoming_fraction=float(incoming.mean()),
                state_hash=_hash(spins.state.tolist()), positions_hash=_hash(spins.positions().tolist()))
            total_work += spins.work-before_work
        records.append(record)
    blood_mz = np.array([r['tissues']['blood']['mean_mz'] for r in records])
    wall_mz = np.array([r['tissues']['wall']['mean_mz'] for r in records])
    validation = dict(blood_target_max=blood_target_max, wall_target_min=wall_target_min,
        max_abs_blood_mz=float(abs(blood_mz).max()), min_abs_wall_mz=float(abs(wall_mz).min()))
    validation['passed'] = validation['max_abs_blood_mz'] <= blood_target_max and validation['min_abs_wall_mz'] >= wall_target_min
    inputs = dict(r_peaks_s=list(r_peaks_s), inversion_time_s=inversion_time_s,
        blood_velocity_m_s=blood_velocity_m_s, thickness_m=thickness_m, rf_steps=rf_steps,
        spin_count=spin_count, off_resonance_hz=off_resonance_hz, rr_range_s=list(rr_range_s),
        max_work=max_work, max_duration_s=max_duration_s,
        blood_target_max=blood_target_max, wall_target_min=wall_target_min)
    return dict(clinical_question='How do prescribed through-plane flow, finite slice reinversion and accepted cardiac timing affect DIR blood suppression?',
        design=inputs, gates=gates, readouts=records, validation=validation,
        objective_loss=float(np.mean(abs(blood_mz)/np.maximum(abs(wall_mz), 1e-12))), scope=SCOPE,
        provenance=dict(version='moving-dir-v1', replay=inputs, input_hash=_hash(inputs),
            source_hash=sha256(Path(__file__).read_bytes()).hexdigest(),
            estimated_work=total_work, planned_work=planned_work, duration_s=end,
            finite_rf_energy_uT2_s=len(accepted)*(inv['rf_energy_uT2_s']+exc['rf_energy_uT2_s']),
            hard_rf_energy_relative=len(accepted),
            waveform_hash=_hash([inv['b1_uT'].tolist(), inv['gz_t_m'], exc['b1_uT'].tolist(), exc['gz_t_m']]),
            boundary='persistent finite upstream ensemble; no reset or wrapping; uniform receive sensitivity in slab'))


def search_flow_timing(candidates_s, **kwargs):
    """Finite declared grid; every candidate executes the full moving-spin model."""
    candidates = list(candidates_s)
    if not candidates or len(candidates) > 64: raise ValueError('one to 64 timing candidates required')
    if 'inversion_time_s' in kwargs: raise ValueError('inversion time belongs in candidate grid')
    points = []
    for ti in candidates:
        try:
            result = run_flow_imaging(inversion_time_s=ti, **kwargs)
            points.append(dict(inversion_time_s=ti, feasible=True, result=result))
        except ValueError as exc:
            points.append(dict(inversion_time_s=ti, feasible=False, reason=str(exc)))
    feasible = [p for p in points if p['feasible']]
    return dict(candidates=points, best=min(feasible, key=lambda p:p['result']['objective_loss']) if feasible else None,
        objective='mean absolute pre-excitation blood Mz / wall Mz; research grid optimum only')
