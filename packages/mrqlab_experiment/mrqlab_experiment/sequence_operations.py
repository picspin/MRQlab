"""Bounded operation orchestration for a static teaching voxel grid.

Sequential hard RF, rectangular gradient holds and delays precede an ideal
Cartesian snapshot. This is not a waveform compiler or scanner execution path.
"""
import math
from typing import Annotated, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from mrqlab_physics.ops.rf import rotate_cartesian
from .lab_study import fingerprint
from .linked_readout import complex_values, create_linked_readout, validate_linked_edits


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class Operation(Strict):
    id: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_]{0,31}$')


class HardRF(Operation):
    kind: Literal['hard_rf']
    flip_deg: float = Field(ge=0, le=180)
    phase_deg: float = Field(ge=-180, le=180)


class GradientHold(Operation):
    kind: Literal['gradient_hold']
    axis: Literal['x', 'y']
    amplitude_mt_m: float = Field(ge=-40, le=40)
    duration_s: float = Field(ge=1e-6, le=.1)


class Delay(Operation):
    kind: Literal['delay']
    duration_s: float = Field(ge=1e-6, le=1.)


class Tissue(Strict):
    id: str = Field(min_length=1, max_length=128)
    proton_density: float = Field(gt=0, le=2)
    t1_s: float = Field(ge=.01, le=10)
    t2_s: float = Field(ge=.001, le=2)


class OperationSequence(Strict):
    operations: list[Annotated[HardRF | GradientHold | Delay, Field(discriminator='kind')]] = Field(min_length=1, max_length=32)
    labels: list[list[int]] = Field(min_length=2, max_length=16)
    tissues: list[Tissue] = Field(min_length=1, max_length=8)
    fov_m: float = Field(default=.22, ge=.01, le=1.)

    @model_validator(mode='after')
    def bounded_sequence(self):
        if len({op.id for op in self.operations}) != len(self.operations):
            raise ValueError('unique stable operation IDs required')
        if len({t.id for t in self.tissues}) != len(self.tissues):
            raise ValueError('unique tissue IDs required')
        width = len(self.labels[0])
        if not 2 <= width <= 16 or any(len(row) != width for row in self.labels):
            raise ValueError('rectangular 2..16 voxel grid required')
        if any(type(v) is not int or not 0 <= v < len(self.tissues) for row in self.labels for v in row):
            raise ValueError('integer labels must bind to declared tissues')
        if math.fsum(getattr(op, 'duration_s', 0.) for op in self.operations) > 2.:
            raise ValueError('total preparation duration exceeds two seconds')
        return self


def operation_controls(sequence):
    controls = []
    for op in sequence.operations:
        domains = ({'flip_deg': ('deg', 0., 180.), 'phase_deg': ('deg', -180., 180.)} if isinstance(op, HardRF)
                   else {'amplitude_mt_m': ('mT/m', -40., 40.), 'duration_s': ('s', 1e-6, .1)} if isinstance(op, GradientHold)
                   else {'duration_s': ('s', 1e-6, 1.)})
        for name, (unit, low, high) in domains.items():
            controls.append(dict(field=f'operations.{op.id}.{name}', value=getattr(op, name),
                                 unit=unit, kind='number', min=low, max=high))
    return controls


def apply_operation_edits(parameters, updates, *, pair):
    sequence = OperationSequence.model_validate(parameters)
    if pair['provenance']['inputs_sha256'] != fingerprint(sequence.model_dump(mode='json')):
        raise ValueError('operation pair input pin differs from retained sequence')
    # Capabilities are adapter-owned; a rehashed pair cannot introduce a path.
    if pair['provenance']['adapter'] != 'static-voxel-operations-1' or pair['controls'] != operation_controls(sequence):
        raise ValueError('operation capabilities differ from retained sequence')
    checked = validate_linked_edits(pair, updates)
    result = sequence.model_dump(mode='json')
    by_id = {op['id']: op for op in result['operations']}
    for edit in checked:
        _, identity, name = edit.field.split('.')
        by_id[identity][name] = edit.value
    # Recheck coupled limits after the entire atomic batch; no parent mutation.
    return OperationSequence.model_validate(result).model_dump(mode='json')


def run_operation_sequence(parameters):
    sequence = OperationSequence.model_validate(parameters)
    replay = sequence.model_dump(mode='json')
    labels = np.asarray(sequence.labels)
    shape = labels.shape
    indices = np.indices(shape).reshape(2, -1).T
    xy = ((indices - np.asarray(shape)//2) / np.asarray(shape))[:, ::-1] * sequence.fov_m
    flat = labels.ravel()
    pd = np.asarray([t.proton_density for t in sequence.tissues])[flat]
    t1 = np.asarray([t.t1_s for t in sequence.tissues])[flat]
    t2 = np.asarray([t.t2_s for t in sequence.tissues])[flat]
    state = np.zeros((labels.size, 3)); state[:, 2] = pd
    clock = 0.; trace = []; durations = []
    for op in sequence.operations:
        start = clock
        if isinstance(op, HardRF):
            state = rotate_cartesian(state, np.deg2rad(op.flip_deg), np.deg2rad(op.phase_deg))
        else:
            dt = op.duration_s
            phase = (2*np.pi*GAMMA_BAR_HZ_T*1e-3*op.amplitude_mt_m*xy[:, 'xy'.index(op.axis)]*dt
                     if isinstance(op, GradientHold) else 0.)
            transverse = (state[:, 0]+1j*state[:, 1])*np.exp(-dt/t2+1j*phase)
            state[:, 0] = transverse.real; state[:, 1] = transverse.imag
            state[:, 2] = pd+(state[:, 2]-pd)*np.exp(-dt/t1)
            durations.append(dt)
            clock = math.fsum(durations)
        trace.append(dict(operation=op.model_dump(mode='json'), start_s=start, end_s=clock,
                          magnetization=state.tolist()))
    image = (state[:, 0]+1j*state[:, 1]).reshape(shape)
    kspace = np.fft.fftshift(np.fft.fftn(np.fft.ifftshift(image)))
    from .study_records import _checked_sources, runtime_manifest
    pair = create_linked_readout(
        image=dict(id='operation_image', shape=list(shape), axes=['y', 'x'], index_unit='voxel', flatten_order='C',
                   value_unit='a.u.', values=complex_values(image), display='magnitude preview; complete complex snapshot retained'),
        signal_vector=dict(id='snapshot_kspace', axis='acquisition_sample', value_unit='a.u.', complex_convention='real + i*imag',
                           values=complex_values(kspace), grid_indices=indices.tolist(), grid_index_axes=['y', 'x'],
                           normalized_coordinates=((indices-np.asarray(shape)//2)/np.asarray(shape)).tolist(),
                           coordinate_unit='cycles/voxel', sample_times_s=[clock]*labels.size, time_unit='s',
                           timing_model='simultaneous ideal Cartesian snapshot after preparation; no physical ADC trajectory',
                           extensions=dict(operation_trace=trace, fov_m=sequence.fov_m)),
        structure=dict(shape=list(shape), label_grid=sequence.labels, label_to_tissue_id=[t.id for t in sequence.tissues],
                       origin='authored synthetic static voxel grid'),
        controls=operation_controls(sequence),
        links=[dict(source='snapshot_kspace', target='operation_image', transform='centered_inverse_dft', normalization='1/product(shape); no fitted gain')],
        provenance=dict(adapter='static-voxel-operations-1', source_sha256=_checked_sources()['sha256'], runtime=runtime_manifest(),
                        inputs_sha256=fingerprint(replay), origin='authored synthetic inputs',
                        source_refs=[dict(tissue_id=t.id, source_ref='authored:tissue:'+t.id, origin='synthetic', state=t.model_dump(mode='json')) for t in sequence.tissues]),
        scope='teaching/research static Bloch preparation and ideal Fourier snapshot; no scanner validation; first Milestone B slice')
    return dict(linked_readout=pair, operation_trace=trace, final_magnetization=state.tolist(), duration_s=clock,
                provenance=dict(replay=replay),
                validation=dict(passed=True, scope='bounded execution and linked transform only; no image quality or clinical target'))


def operation_sequence_example():
    return dict(context=dict(study_id='synthetic-operation-sequence', research_question='How do ordered RF rotations and gradient holds alter a static voxel snapshot?',
                             target_rationale='Check operation state evolution and complete linked Fourier data, without a clinical target.'),
                execution=dict(type='operation_sequence', parameters=dict(
                    operations=[dict(id='excite', kind='hard_rf', flip_deg=90., phase_deg=0.),
                                dict(id='encode', kind='gradient_hold', axis='x', amplitude_mt_m=.02, duration_s=.001),
                                dict(id='wait', kind='delay', duration_s=.01)],
                    labels=[[0, 0, 1, 1]]*4,
                    tissues=[dict(id='a', proton_density=1., t1_s=1., t2_s=.1),
                             dict(id='b', proton_density=.8, t1_s=.8, t2_s=.08)])))
