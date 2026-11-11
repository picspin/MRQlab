"""Bounded sampled-waveform Bloch research simulation, with point ADC.

Samples are piecewise constant; RK4 integrates concurrent RF, gradients,
static off-resonance and relaxation. ADC is instantaneous at dwell midpoints,
not a finite aperture. No motion, diffusion, exchange or scanner execution.
"""
from decimal import Decimal
from math import ceil
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from .clinical_catalog import RESEARCH_3T
from .executable_sequence import LogicalSequenceIR
from .sequence_lowering import lower_sequence


class _Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class VoxelTissue(_Strict):
    id: str = Field(min_length=1, max_length=128)
    proton_density: float = Field(gt=0, le=2)
    t1_s: float = Field(ge=.01, le=10)
    t2_s: float = Field(ge=.001, le=2)
    b0_hz: float = Field(default=0, ge=-2000, le=2000)
    b1_scale: float = Field(default=1, ge=0, le=2)


class SignalTarget(_Strict):
    sample_index: int = Field(ge=0, strict=True)
    metric: Literal['magnitude', 'real', 'imag']
    operator: Literal['ge', 'le']
    value: float
    unit: Literal['a.u.'] = 'a.u.'


class WaveformBlochPlan(_Strict):
    sequence: LogicalSequenceIR
    labels: list[list[StrictInt]] = Field(min_length=2, max_length=16)
    tissues: list[VoxelTissue] = Field(min_length=1, max_length=8)
    fov_m: float = Field(default=.22, ge=.01, le=1)
    z_m: float = Field(default=0, ge=-.5, le=.5)
    max_step_s: float = Field(default=10e-6, ge=.1e-6, le=100e-6)
    substeps_per_interval: int = Field(default=1, ge=1, le=8, strict=True)
    max_work: int = Field(default=2_000_000, ge=1, le=2_000_000, strict=True)
    target: SignalTarget | None = None

    @model_validator(mode='before')
    @classmethod
    def reject_boolean_input(cls, value):
        def contains_bool(item):
            if isinstance(item, dict): return any(contains_bool(v) for v in item.values())
            if isinstance(item, (list, tuple)): return any(contains_bool(v) for v in item)
            return isinstance(item, bool)
        if contains_bool(value):
            raise ValueError('boolean values are not valid numeric waveform inputs')
        return value

    @model_validator(mode='after')
    def bounded(self):
        width = len(self.labels[0])
        if not 2 <= width <= 16 or any(len(row) != width for row in self.labels):
            raise ValueError('rectangular 2..16 voxel grid required')
        if len({t.id for t in self.tissues}) != len(self.tissues):
            raise ValueError('unique tissue IDs required')
        if any(type(v) is not int or not 0 <= v < len(self.tissues) for row in self.labels for v in row):
            raise ValueError('integer labels must bind to declared tissues')
        if len(self.sequence.blocks) > 32 or self.sequence.duration_s > .2:
            raise ValueError('at most 32 blocks and .2 seconds are supported')
        samples = sum((len(b.rf.samples_ut) if b.rf else 0) +
                      sum(len(g.samples_mt_m) for g in b.gradients) +
                      (b.adc.sample_count if b.adc else 0) for b in self.sequence.blocks)
        if samples > 4096:
            raise ValueError('waveform and ADC sample budget exceeded')
        for b in self.sequence.blocks:
            if b.rf and any(abs(value) > 1000 for value in b.rf.samples_ut):
                raise ValueError('RF sample exceeds the bounded 1000 uT research input domain')
            if b.rf and any(abs(value) > 1e6 for value in b.rf.phase_rad):
                raise ValueError('RF phase exceeds the bounded research input domain')
            if b.rf and b.rf.carrier_offset_hz != 0:
                raise ValueError('RF carrier offset is not supported in the common rotating frame')
            if b.adc and (b.adc.frequency_offset_hz != 0 or b.adc.phase_offset_rad != 0):
                raise ValueError('ADC receiver offsets are not supported')
        if not any(b.adc for b in self.sequence.blocks):
            raise ValueError('at least one ADC window is required')
        return self


def run_waveform_bloch(parameters, *, _preflight_only=False):
    plan = WaveformBlochPlan.model_validate(parameters)
    sequence = lower_sequence(plan.sequence, RESEARCH_3T)
    labels = np.asarray(plan.labels, dtype=int)
    shape = labels.shape
    indices = np.indices(shape).reshape(2, -1).T
    x = (indices[:, 1] - shape[1]//2) * plan.fov_m / shape[1]
    y = (indices[:, 0] - shape[0]//2) * plan.fov_m / shape[0]
    coords = np.column_stack((x, y, np.full(labels.size, plan.z_m)))
    tissue = [plan.tissues[i] for i in labels.ravel()]
    pd = np.array([t.proton_density for t in tissue])
    r1 = 1 / np.array([t.t1_s for t in tissue])
    r2 = 1 / np.array([t.t2_s for t in tissue])
    b0 = np.array([t.b0_hz for t in tissue])
    b1 = np.array([t.b1_scale for t in tissue])

    # A time point contains channel updates and zero or more point ADCs. Decimal
    # holds raster boundaries exactly before conversion to floating-point dt.
    events = {Decimal(0): [], Decimal(str(sequence.duration_s)): []}
    adc_count = 0
    for block in sequence.blocks:
        start = Decimal(str(block.start_s))
        if block.rf:
            raster = Decimal(str(block.rf.raster_s))
            for i, (amplitude, phase) in enumerate(zip(block.rf.samples_ut, block.rf.phase_rad)):
                events.setdefault(start+i*raster, []).append(('rf', amplitude, phase))
            events.setdefault(start+len(block.rf.samples_ut)*raster, []).append(('rf', 0., 0.))
        for gradient in block.gradients:
            raster = Decimal(str(gradient.raster_s))
            for i, amplitude in enumerate(gradient.samples_mt_m):
                events.setdefault(start+i*raster, []).append((gradient.axis, amplitude))
            events.setdefault(start+len(gradient.samples_mt_m)*raster, []).append((gradient.axis, 0.))
        if block.adc:
            delay, dwell = Decimal(str(block.adc.delay_s)), Decimal(str(block.adc.dwell_s))
            for i in range(block.adc.sample_count):
                at = start + delay + (Decimal(i)+Decimal('.5'))*dwell
                events.setdefault(at, []).append(('adc', block.id, i))
                adc_count += 1

    times = sorted(events)
    if plan.target is not None and plan.target.sample_index >= adc_count:
        raise ValueError('target sample index is outside the complete ADC acquisition')
    # Conservative preflight based on maxima independently of pulse phase or
    # gradient sign. No adaptive unbounded work or silent input coarsening.
    max_rf = max((abs(a) for b in sequence.blocks if b.rf for a in b.rf.samples_ut), default=0.) * 1e-6 * float(max(b1))
    max_g = [max((abs(a) for b in sequence.blocks for g in b.gradients if g.axis == axis for a in g.samples_mt_m), default=0.) * 1e-3 for axis in ('gx','gy','gz')]
    max_position = np.max(np.abs(coords), axis=0)
    max_hz = float(max(np.abs(b0))) + GAMMA_BAR_HZ_T * (max_rf + float(np.dot(max_g, max_position)))
    dt_limit = min(plan.max_step_s, .2 / (2*np.pi*max_hz + max(float(max(r1)), float(max(r2)))))
    steps = [max(1, ceil(float(b-a)/dt_limit))*plan.substeps_per_interval for a,b in zip(times, times[1:])]
    work = int(sum(steps)*labels.size)
    if work > plan.max_work:
        raise ValueError(f'complete waveform work {work} exceeds max_work {plan.max_work}; no time steps were coarsened')
    if _preflight_only:
        return dict(voxel_steps=work, max_work=plan.max_work, max_step_s=plan.max_step_s,
                    substeps_per_interval=plan.substeps_per_interval, intervals=len(steps))

    state = np.zeros((labels.size, 3)); state[:, 2] = pd
    rf = (0., 0.); gradient = np.zeros(3); k = np.zeros(3)
    output = []

    def derivative(m, omega):
        d = np.cross(omega, m)
        d[:, 0] -= r2*m[:, 0]; d[:, 1] -= r2*m[:, 1]
        d[:, 2] += r1*(pd-m[:, 2])
        return d

    for i, at in enumerate(times):
        # Channel end events precede starts at the same boundary, so adjacent
        # blocks switch directly even if block IDs sort in the opposite order.
        actions = events[at]
        for action in sorted((a for a in actions if a[0] != 'adc'), key=lambda a: (a[0], a[1] != 0.)):
            if action[0] == 'rf': rf = (action[1], action[2])
            else: gradient[('gx','gy','gz').index(action[0])] = action[1]
        for action in (a for a in actions if a[0] == 'adc'):
            signal = np.sum(state[:,0] + 1j*state[:,1])
            output.append(dict(block_id=action[1], sample_index=action[2], time_s=float(at),
                               real=float(signal.real), imag=float(signal.imag), k_cycles_m=k.tolist()))
        if i == len(steps): break
        dt = float(times[i+1]-at); h = dt/steps[i]
        angle = 2*np.pi*GAMMA_BAR_HZ_T*rf[0]*1e-6*b1
        omega = np.column_stack((angle*np.cos(rf[1]), angle*np.sin(rf[1]),
            2*np.pi*(b0 + GAMMA_BAR_HZ_T*(coords @ gradient)*1e-3)))
        for _ in range(steps[i]):
            a = derivative(state, omega); b = derivative(state+h*a/2, omega)
            c = derivative(state+h*b/2, omega); d = derivative(state+h*c, omega)
            state += h*(a+2*b+2*c+d)/6
        k += GAMMA_BAR_HZ_T*gradient*1e-3*dt
    if plan.target is None:
        validation = dict(passed=False, scope='execution only; no imaging or clinical target supplied')
    else:
        sample = output[plan.target.sample_index]
        value = abs(complex(sample['real'], sample['imag'])) if plan.target.metric == 'magnitude' else sample[plan.target.metric]
        passed = value >= plan.target.value if plan.target.operator == 'ge' else value <= plan.target.value
        validation = dict(passed=bool(passed), measured=float(value), target=plan.target.model_dump(mode='json'),
                          scope='authored single point-signal target only; no image or clinical validation')
    return dict(model='sample_hold_rk4_point_adc_v1', samples=output, sample_count=adc_count,
        final_magnetization=state.tolist(), voxel_shape=list(shape), voxel_positions_m=coords.tolist(),
        executed_sequence=sequence.model_dump(mode='json'),
        work=dict(voxel_steps=work, max_work=plan.max_work, max_step_s=plan.max_step_s,
                  substeps_per_interval=plan.substeps_per_interval, intervals=len(steps)),
        validation=validation,
        provenance=dict(replay=plan.model_dump(mode='json'), profile=f'{RESEARCH_3T.id}@{RESEARCH_3T.version}',
            signal_convention='sum(Mx + i My), instantaneous dwell midpoint',
            trajectory_convention='gamma_bar integral of G from sequence start, cycles/m; not necessarily encoding coordinates after RF',
            scope='authored static 2D voxel plane, finite RF/gradient holds and T1/T2/B0/B1; teaching/research only'))


def estimate_waveform_work(parameters):
    """Run the same validation and work preflight without integrating spins."""
    return run_waveform_bloch(parameters, _preflight_only=True)
