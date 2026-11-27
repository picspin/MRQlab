"""Reconstruct complete Cartesian point-ADC data from a bounded waveform run.

The result is an inverse DFT of actual sequential samples, not the final spin
snapshot or a claim that all samples share one static object.
"""
from decimal import Decimal
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from mrqlab_recon.spatial import cartesian_reconstruct
from .clinical_catalog import RESEARCH_3T
from .sequence_lowering import lower_sequence
from .waveform_bloch import WaveformBlochPlan, run_waveform_bloch
from .lab_study import fingerprint
from .linked_readout import complex_values, create_linked_readout, validate_linked_edits
from .study_records import _checked_sources, runtime_manifest


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class ImageTarget(Strict):
    target_tissue_id: str = Field(min_length=1, max_length=128)
    reference_tissue_id: str = Field(min_length=1, max_length=128)
    operator: Literal['ge', 'le']
    value: float
    unit: Literal['a.u.'] = 'a.u.'


class CartesianWaveformPlan(Strict):
    waveform: WaveformBlochPlan
    # In acquisition order, [row ky, column kx] in the centered FFT grid.
    grid_indices: list[list[StrictInt]] = Field(min_length=4, max_length=256)
    trajectory_tolerance_cycles_m: float = Field(default=1e-6, gt=0, le=1e-3)
    image_target: ImageTarget | None = None

    @model_validator(mode='after')
    def valid_grid(self):
        height, width = len(self.waveform.labels), len(self.waveform.labels[0])
        expected = {(y,x) for y in range(height) for x in range(width)}
        if (any(len(index)!=2 for index in self.grid_indices) or len(self.grid_indices) != len(expected)
                or {tuple(index) for index in self.grid_indices} != expected):
            raise ValueError('complete unique Cartesian indices for the authored voxel grid are required')
        count = sum(b.adc.sample_count for b in self.waveform.sequence.blocks if b.adc)
        if count != len(expected):
            raise ValueError('complete Cartesian grid requires exactly one ADC sample per grid point')
        if self.image_target:
            ids = [t.id for t in self.waveform.tissues]
            t, r = self.image_target.target_tissue_id, self.image_target.reference_tissue_id
            if t == r or t not in ids or r not in ids:
                raise ValueError('two different declared target/reference tissues are required')
            present = set(v for row in self.waveform.labels for v in row)
            if ids.index(t) not in present or ids.index(r) not in present:
                raise ValueError('target and reference tissues must both occur in the label grid')
        return self


def _check_preparation(sequence):
    rf_blocks = [b for b in sequence.blocks if b.rf is not None]
    if len(rf_blocks) != 1 or not any(rf_blocks[0].rf.samples_ut):
        raise ValueError('Cartesian adapter requires exactly one nonzero RF block')
    rf = rf_blocks[0]
    rf_end = Decimal(str(rf.start_s)) + len(rf.rf.samples_ut)*Decimal(str(rf.rf.raster_s))
    for block in sequence.blocks:
        if block.adc and Decimal(str(block.start_s))+Decimal(str(block.adc.delay_s)) < rf_end:
            raise ValueError('all ADC samples must follow the single RF block')
        for gradient in block.gradients:
            start = Decimal(str(block.start_s)); raster = Decimal(str(gradient.raster_s))
            if any(amplitude != 0 and start+i*raster < rf_end for i,amplitude in enumerate(gradient.samples_mt_m)):
                raise ValueError('nonzero gradients before or during RF are unsupported by this Cartesian adapter')


def preflight_cartesian_trajectory(parameters):
    """Integrate declared gradient holds independently before spin evolution."""
    plan=CartesianWaveformPlan.model_validate(parameters)
    sequence=lower_sequence(plan.waveform.sequence,RESEARCH_3T)
    _check_preparation(sequence)
    gradient_holds=[];adc=[]
    for block in sequence.blocks:
        start=Decimal(str(block.start_s))
        for gradient in block.gradients:
            raster=Decimal(str(gradient.raster_s))
            for i,value in enumerate(gradient.samples_mt_m):
                if value:
                    begin=start+i*raster
                    gradient_holds.append((gradient.axis,begin,begin+raster,Decimal(str(value))))
        if block.adc:
            dwell=Decimal(str(block.adc.dwell_s));delay=Decimal(str(block.adc.delay_s))
            for index in range(block.adc.sample_count):
                adc.append((start+delay+(Decimal(index)+Decimal('.5'))*dwell,block.id,index))
    adc.sort()
    gamma=Decimal(str(GAMMA_BAR_HZ_T))*Decimal('0.001')
    observed=[]
    for at,_,_ in adc:
        k={axis:Decimal(0) for axis in ('gx','gy','gz')}
        for axis,begin,end,amplitude in gradient_holds:
            duration=max(Decimal(0),min(at,end)-begin)
            k[axis]+=amplitude*duration*gamma
        observed.append([float(k[axis]) for axis in ('gx','gy','gz')])
    shape=(len(plan.waveform.labels),len(plan.waveform.labels[0]));indices=np.asarray(plan.grid_indices,dtype=int)
    expected=np.column_stack((-(indices[:,1]-shape[1]//2)/plan.waveform.fov_m,
                              -(indices[:,0]-shape[0]//2)/plan.waveform.fov_m,np.zeros(len(indices))))
    max_error=float(np.max(np.abs(np.asarray(observed)-expected)))
    if max_error>plan.trajectory_tolerance_cycles_m:
        raise ValueError(f'ADC gradient moment differs from declared Cartesian grid: max error {max_error:.12g} cycles/m')
    return dict(adc=[dict(time_s=float(t),block_id=block,index=i) for t,block,i in adc],
                observed_k_cycles_m=observed,expected_k_cycles_m=expected.tolist(),max_error_cycles_m=max_error)


def waveform_cartesian_controls(plan):
    """Adapter-owned writable fields; indices refer to the retained RF samples."""
    controls=[]
    rf_blocks=[b for b in plan.waveform.sequence.blocks if b.rf is not None]
    if len(rf_blocks)==1 and len(rf_blocks[0].rf.samples_ut)<=32:
        rf=rf_blocks[0].rf
        for index,(amplitude,phase) in enumerate(zip(rf.samples_ut,rf.phase_rad)):
            controls.extend([
                dict(field=f'rf.samples.{index}.amplitude_ut',value=amplitude,unit='uT',kind='number',min=-1000.,max=1000.),
                dict(field=f'rf.samples.{index}.phase_rad',value=phase,unit='rad',kind='number',min=-1e6,max=1e6),
            ])
    domains={'proton_density':('a.u.',1e-12,2.),'t1_s':('s',.01,10.),'t2_s':('s',.001,2.),
             'b0_hz':('Hz',-2000.,2000.),'b1_scale':('relative',0.,2.)}
    for tissue in plan.waveform.tissues:
        for field,(unit,low,high) in domains.items():
            controls.append(dict(field=f'tissue.{field}',tissue_id=tissue.id,value=float(getattr(tissue,field)),
                                 unit=unit,kind='number',min=low,max=high))
    return controls


def apply_waveform_cartesian_edits(parameters, updates, *, pair):
    """Validate semantic edits against an immutable parent before rewriting inputs."""
    plan=CartesianWaveformPlan.model_validate(parameters)
    if pair['provenance']['inputs_sha256']!=fingerprint(plan.model_dump(mode='json')):
        raise ValueError('waveform Cartesian pair input pin differs from retained plan')
    if (pair['provenance']['adapter']!='waveform-cartesian-point-adc-1' or
            pair['controls']!=waveform_cartesian_controls(plan)):
        raise ValueError('waveform Cartesian capabilities differ from retained plan')
    checked=validate_linked_edits(pair,updates)
    result=plan.model_dump(mode='json')
    blocks=[b for b in result['waveform']['sequence']['blocks'] if b['rf'] is not None]
    tissues={t['id']:t for t in result['waveform']['tissues']}
    for edit in checked:
        parts=edit.field.split('.')
        if parts[0]=='rf':
            index=int(parts[2]);field='samples_ut' if parts[3]=='amplitude_ut' else 'phase_rad'
            blocks[0]['rf'][field][index]=edit.value
        else:
            tissues[edit.tissue_id][parts[1]]=edit.value
    return CartesianWaveformPlan.model_validate(result).model_dump(mode='json')


def run_waveform_cartesian(parameters):
    plan = CartesianWaveformPlan.model_validate(parameters)
    preflight=preflight_cartesian_trajectory(plan)
    result = run_waveform_bloch(plan.waveform)
    samples = result['samples']; shape = tuple(result['voxel_shape'])
    indices = np.asarray(plan.grid_indices, dtype=int)
    actual = np.asarray([s['k_cycles_m'] for s in samples])
    if ([dict(time_s=s['time_s'],block_id=s['block_id'],index=s['sample_index']) for s in samples] != preflight['adc'] or
            not np.allclose(actual,preflight['observed_k_cycles_m'],rtol=1e-12,atol=1e-12)):
        raise ValueError('simulated ADC timing or gradient moment differs from independent preflight')
    # Bloch uses +i gamma integral(G). A centered forward DFT uses -i k.x.
    expected = np.column_stack((-(indices[:,1]-shape[1]//2)/plan.waveform.fov_m,
                                -(indices[:,0]-shape[0]//2)/plan.waveform.fov_m,
                                np.zeros(len(indices))))
    errors = np.abs(actual-expected)
    max_error = float(np.max(errors))
    if max_error > plan.trajectory_tolerance_cycles_m:
        raise ValueError(f'ADC gradient moment differs from declared Cartesian grid: max error {max_error:.12g} cycles/m')
    values = np.asarray([complex(s['real'],s['imag']) for s in samples])
    image = cartesian_reconstruct(indices, values, shape)
    target_result = None
    if plan.image_target:
        labels = np.asarray(plan.waveform.labels)
        ids = [t.id for t in plan.waveform.tissues]
        t = ids.index(plan.image_target.target_tissue_id); r = ids.index(plan.image_target.reference_tissue_id)
        measured = float(np.mean(np.abs(image[labels == t])) - np.mean(np.abs(image[labels == r])))
        passed = measured >= plan.image_target.value if plan.image_target.operator == 'ge' else measured <= plan.image_target.value
        target_result = dict(passed=bool(passed), measured=measured, target=plan.image_target.model_dump(mode='json'))
    signal_pass = result['validation']['passed'] if plan.waveform.target is not None else True
    validation = dict(passed=bool(target_result and target_result['passed'] and signal_pass),
        image_target=target_result, signal_target=result['validation'] if plan.waveform.target else None,
        scope='authored reconstructed magnitude difference and optional point signal only; not clinical validation')
    source = _checked_sources(); runtime = runtime_manifest()
    linked = create_linked_readout(
        image=dict(id='sequential_adc_image',shape=list(shape),axes=['y','x'],index_unit='voxel',flatten_order='C',
                   value_unit='a.u.',values=complex_values(image),
                   display='reconstructed magnitude preview; full complex image retained'),
        signal_vector=dict(id='sequential_adc',axis='acquisition_sample',value_unit='a.u.',complex_convention='real + i*imag',
                           values=complex_values(values),grid_indices=indices.tolist(),grid_index_axes=['y','x'],
                           normalized_coordinates=((indices-np.asarray(shape)//2)/np.asarray(shape)).tolist(),
                           coordinate_unit='cycles/voxel',sample_times_s=[s['time_s'] for s in samples],time_unit='s',
                           timing_model='sequential instantaneous dwell midpoints, not a simultaneous static snapshot',
                           extensions=dict(observed_k_cycles_m=actual.tolist(),expected_k_cycles_m=expected.tolist(),
                                           max_trajectory_error_cycles_m=max_error)),
        structure=dict(shape=list(shape),label_grid=plan.waveform.labels,
                       label_to_tissue_id=[t.id for t in plan.waveform.tissues],origin='authored synthetic static voxel grid'),
        controls=waveform_cartesian_controls(plan),
        links=[dict(source='sequential_adc',target='sequential_adc_image',transform='centered_inverse_dft',normalization='1/product(shape); no fitted gain')],
        provenance=dict(adapter='waveform-cartesian-point-adc-1',source_sha256=source['sha256'],runtime=runtime,
                        inputs_sha256=fingerprint(plan.model_dump(mode='json')),origin='authored synthetic inputs',
                        source_refs=[dict(tissue_id=t.id,source_ref='authored:tissue:'+t.id,origin='synthetic',
                                          state=t.model_dump(mode='json')) for t in plan.waveform.tissues]),
        scope='teaching/research sequential ADC with temporal signal evolution; inverse DFT is not a static-object or clinical validation')
    return dict(model='sequential_point_adc_cartesian_v1', waveform=result,
        image=dict(shape=list(shape), axes=['y','x'], unit='a.u.', flatten_order='C',
                   real=image.real.ravel().tolist(), imag=image.imag.ravel().tolist(),
                   magnitude=np.abs(image).ravel().tolist()),
        encoding=dict(grid_indices=indices.tolist(), expected_k_cycles_m=expected.tolist(),
                      observed_k_cycles_m=actual.tolist(), max_error_cycles_m=max_error,
                      tolerance_cycles_m=plan.trajectory_tolerance_cycles_m,
                      sign='positive Bloch gradient moment mapped to negative DFT k',
                      reconstruction='centered inverse DFT of sequential point ADCs; 1/product(shape)'),
        validation=validation,linked_readout=linked,
        provenance=dict(replay=plan.model_dump(mode='json'),
            scope='single RF, no pre/during-RF gradient, complete static-grid point ADC; temporal T2/B0 effects remain in sampled data; teaching/research only'))
