"""Revalidate a lab T2 study and stress a waveform image search at its corners."""
import json
from itertools import product

from pydantic import BaseModel, ConfigDict, Field

from .lab_study import LabStudy, fingerprint, run_lab_study
from .study_records import _checked_sources, runtime_manifest, verify_study_record
from .waveform_image_search import WaveformImageSearch, search_waveform_image
from .linked_readout import verify_linked_readout
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T


class MeasuredWaveformStudy(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
    search: WaveformImageSearch
    max_parent_work: int=Field(default=1_000_000_000,ge=1,le=5_000_000_000,strict=True)


def build_measured_waveform_example(parent_study):
    """Explicit synthetic 2x2 design bound to a lab study's tissue IDs."""
    parent=LabStudy.model_validate(parent_study);ids=parent.tissue_order;fov=.22
    amplitude=1/(fov*GAMMA_BAR_HZ_T*1e-3*21*1e-5)
    gx=[0.]*130;gy=[0.]*130
    for start,sign in [(2,1),(35,-1),(65,1),(95,-1)]: gx[start:start+21]=[sign*amplitude]*21
    for start,sign in [(2,1),(65,-1)]: gy[start:start+21]=[sign*amplitude]*21
    blocks=[dict(id='rf',start_s=0.,rf=dict(samples_ut=[15.,15.,15.],phase_rad=[0.,0.,0.],raster_s=1e-5)),
            dict(id='encoding',start_s=.0002,gradients=[dict(axis='gx',samples_mt_m=gx,raster_s=1e-5),
                                                        dict(axis='gy',samples_mt_m=gy,raster_s=1e-5)])]
    for index,center in enumerate([.0005,.0008,.0011,.0014]):
        blocks.append(dict(id=f'adc{index}',start_s=center-1e-6,adc=dict(delay_s=0.,dwell_s=2e-6,sample_count=1)))
    base=dict(waveform=dict(sequence=dict(id='synthetic-cartesian',duration_s=.0016,blocks=blocks),
        labels=[[0,1],[1,0]],tissues=[dict(id=ids[0],proton_density=1.,t1_s=1.,t2_s=.08),
                                      dict(id=ids[1],proton_density=.6,t1_s=.7,t2_s=.03)],
        fov_m=fov,max_step_s=1e-6,max_work=100000),
        grid_indices=[[0,0],[0,1],[1,0],[1,1]],trajectory_tolerance_cycles_m=1e-7,
        image_target=dict(target_tissue_id=ids[0],reference_tissue_id=ids[1],operator='ge',value=.01))
    search=dict(base=base,rf_block_id='rf',scales=[.1,.5,1.],
        scenarios=[dict(id='nominal',b0_delta_hz=0.,b1_scale_factor=1.),
                   dict(id='shifted',b0_delta_hz=20.,b1_scale_factor=.8)],
        signal_refinement_tolerance=1e-6,image_refinement_tolerance=1e-6,max_total_work=1_000_000)
    return MeasuredWaveformStudy.model_validate(dict(search=search,max_parent_work=parent.budget.max_total_work)).model_dump(mode='json')


def lab_t2_binding(parent_record,dataset,fit,stress_id,used_t2):
    return dict(parameter='t2_s',used_value_s=used_t2,nominal_value_s=fit['t2_s'],
                stress_interval_s=fit['t2_interval_s'],stress_id=stress_id,
                parent_lab_record_sha256=parent_record['record_sha256'],parent_calibration_sha256=fingerprint(fit),
                measurement_origin=dataset.origin,measurement_source_ref=dataset.source_ref,
                raw_file_sha256=dataset.raw_file_sha256)


def attach_lab_bindings(result,parent_record,dataset,by_id,stress):
    """Bind T2 provenance without presenting authored T1/PD as measured."""
    for candidate in result['candidates']:
        for scenario in candidate['scenarios']:
            for key in ('coarse','refined'):
                pair=scenario[key]['linked_readout'];provenance=pair['provenance']
                provenance['origin']='mixed: authored synthetic model and lab-derived T2'
                for ref in provenance['source_refs']:
                    tissue_id=ref['tissue_id'];fit=by_id[tissue_id]
                    used=ref['state']['t2_s']
                    ref['origin']='mixed'
                    ref['t2_binding']=lab_t2_binding(parent_record,dataset,fit,stress['id'],used)
                    ref['other_parameters_origin']='authored synthetic priors; no lab receiver gain transferred'
                pair['pair_sha256']=fingerprint({k:v for k,v in pair.items() if k!='pair_sha256'})
                verify_linked_readout(pair)


def run_measured_waveform_study(parent_record, parameters):
    spec=MeasuredWaveformStudy.model_validate(parameters)
    verify_study_record(parent_record)
    sources=_checked_sources();runtime=runtime_manifest()
    if parent_record['sources']!=sources or parent_record['runtime']!=runtime:
        raise ValueError('lab parent source/runtime differs; replay requires its original environment')
    parent_spec=LabStudy.model_validate(json.loads(parent_record['request_json']))
    if parent_spec.budget.max_total_work>spec.max_parent_work:
        raise ValueError('cannot reserve parent lab-study work within max_parent_work')
    ids=[t.id for t in spec.search.base.waveform.tissues]
    if len(ids)!=2 or set(ids)!=set(parent_spec.tissue_order):
        raise ValueError('waveform tissue IDs must exactly match the two lab-study tissue IDs')
    # Recompute the entire numerical parent, not just its integrity hash.
    current=run_lab_study(parent_spec)
    if fingerprint(current)!=parent_record['result_sha256']:
        raise ValueError('lab parent numerical revalidation differs from its retained result')
    fits=current['calibration'];by_id={f['tissue_id']:f for f in fits}
    if set(by_id)!=set(ids): raise ValueError('lab calibration tissue bindings differ')
    calibrated=current['validation']['calibration_and_holdout_passed']
    within_parent_work=current['provenance']['estimated_work']<=spec.max_parent_work
    dataset=parent_spec.dataset
    bindings=[];stresses=[];preflights=[];runs=[];reasons=[];total=0
    if calibrated and within_parent_work:
        for tissue in ids:
            fit=by_id[tissue]
            bindings.append(dict(tissue_id=tissue,parameter='t2_s',value=fit['t2_s'],unit='s',
                standard_uncertainty_s=fit['t2_std_s'],stress_interval_s=fit['t2_interval_s'],
                parent_calibration_sha256=fingerprint(fit)))
        nominal=[by_id[t]['t2_s'] for t in ids]
        stresses=[dict(id='nominal',t2_s=nominal)]
        stresses += [dict(id=f'corner_{i}',t2_s=list(corner)) for i,corner in enumerate(product(*(by_id[t]['t2_interval_s'] for t in ids)))]
        for stress in stresses:
            search=spec.search.model_dump(mode='json')
            for tissue,value in zip(search['base']['waveform']['tissues'],stress['t2_s']): tissue['t2_s']=value
            try:
                estimate=search_waveform_image(search,_preflight_only=True)
                preflights.append(dict(id=stress['id'],search=search,work=estimate['total_voxel_steps'],error=None))
                total+=estimate['total_voxel_steps']
            except ValueError as exc:
                preflights.append(dict(id=stress['id'],search=search,work=0,error=str(exc)))
                reasons.append(f"{stress['id']}: {exc}")
        if total>spec.search.max_total_work:
            reasons.append(f'complete uncertainty-grid work {total} exceeds shared max_total_work {spec.search.max_total_work}')
        if not reasons:
            for preflight in preflights:
                result=search_waveform_image(preflight['search'])
                if result['work']['total_voxel_steps']!=preflight['work']:
                    raise ValueError('uncertainty-grid work changed after complete preflight')
                stress=next(x for x in stresses if x['id']==preflight['id'])
                attach_lab_bindings(result,parent_record,dataset,by_id,stress)
                runs.append(dict(id=preflight['id'],search=preflight['search'],result=result))
    elif not calibrated:
        reasons.append('parent calibration or independent holdout failed; no calibrated waveform candidate executed')
    else:
        reasons.append('parent lab revalidation exceeded max_parent_work; no waveform candidate executed')
    completed=bool(calibrated and within_parent_work and not reasons and len(runs)==len(stresses))
    candidates=[]
    for index,scale in enumerate(spec.search.scales):
        item=dict(index=index,scale=scale,executed=completed,eligible=False,reasons=[])
        if completed:
            points=[r['result']['candidates'][index] for r in runs]
            item['executed']=all(p['executable'] for p in points)
            item['stress_outcomes']=[dict(id=r['id'],executable=p['executable'],eligible=p['eligible'],reasons=p['reasons']) for r,p in zip(runs,points)]
            item['eligible']=all(p['eligible'] for p in points)
            energies=[p['rf_energy_proxy_ut2_s'] for p in points if p['executable']]
            if energies:
                if any(e!=energies[0] for e in energies): raise ValueError('RF energy differs across T2 stress scenarios')
                item['rf_energy_proxy_ut2_s']=energies[0]
            if not item['eligible']: item['reasons'].append('one or more T2/B0/B1 or refinement scenarios failed')
        else:
            item['stress_outcomes']=[];item['reasons']=list(reasons)
        candidates.append(item)
    eligible=[p for p in candidates if p['eligible']]
    best=min(eligible,key=lambda p:(p['rf_energy_proxy_ut2_s'],p['index'])) if eligible else None
    if _checked_sources()!=sources or runtime_manifest()!=runtime:
        raise ValueError('source/runtime changed during lab-derived waveform study')
    return dict(model='measured_t2_waveform_image_search_v1',
        parent_record_sha256=parent_record['record_sha256'],parent_result_sha256=parent_record['result_sha256'],
        parent_revalidation=dict(passed=True,calibration_and_holdout_passed=calibrated,
                                 parent_search_complete=current['validation']['complete_budgeted_search'],
                                 reserved_work=parent_spec.budget.max_total_work,estimated_work=current['provenance']['estimated_work'],
                                 within_max_parent_work=within_parent_work),
        measurement=dict(origin=dataset.origin,source_ref=dataset.source_ref,raw_file_sha256=dataset.raw_file_sha256,
                         dataset_sha256=current['provenance']['dataset_sha256']),
        bindings=bindings,stress_scenarios=stresses,preflights=preflights,stress_runs=runs,candidates=candidates,
        selected_index=best['index'] if best else None,
        validation=dict(passed=best is not None,calibration_and_holdout_passed=calibrated,complete_grid=completed,reasons=reasons),
        work=dict(total_voxel_steps=total if completed else 0,preflight_voxel_steps=total,
                  max_total_voxel_steps=spec.search.max_total_work,max_parent_work=spec.max_parent_work),
        provenance=dict(replay=spec.model_dump(mode='json'),
            assumptions=['only T2 is fitted; T1, proton density, B0 and B1 remain authored',
                         'lab signal amplitude is a nuisance and is not used as image gain',
                         'rectangular T2 intervals and finite B0/B1 cases are stress tests, not a joint confidence bound'],
            scope='source-declared measurements and synthetic static voxel model; teaching/research only'))
