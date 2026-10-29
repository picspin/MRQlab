"""Measurement-derived radial TSE design under a fixed reconstruction prior.

Revalidate the parent's numerical study from its original lossless measurements.
Use nominal calibrated T2 in the inverse for every sample uncertainty corner.
This is a rectangular stress test, not a clinical confidence bound or T2 mapper.
"""
from itertools import product
import json
import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from .lab_study import LabStudy, run_lab_study, fingerprint, json_safe
from .study_records import verify_study_record, _checked_sources
from .radial_tse import run_radial_tse


class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)


class RadialPulseCandidate(Strict):
    echoes: int=Field(default=4,ge=2,le=16)
    echo_spacing_s: float=Field(default=.008,ge=.006,le=.03)
    tr_s: float=Field(default=.4,ge=.05,le=2.)
    refocusing_angle: float=Field(default=180.,ge=1.,le=180.)
    refocusing_end_angle: float=Field(default=180.,ge=1.,le=180.)
    echo_order: Literal['forward','reverse']='forward'


class RadialNumerics(Strict):
    spokes: int=Field(default=96,ge=4,le=192)
    points: int=Field(default=32,ge=16,le=64)
    display_echo: int=Field(default=2,ge=1,le=16)
    backend: Literal['exact','finufft']='exact'
    inverse_max_iterations: int=Field(default=6000,ge=1,le=6000)
    inverse_tolerance: float=Field(default=1e-10,ge=1e-13,le=.1)
    nufft_eps: float=Field(default=1e-13,ge=1e-14,le=1e-3)
    control_iterations: int=Field(default=1000,ge=1,le=1000)


class DerivedTargets(Strict):
    image_nrmse: float=Field(default=1e-6,gt=0,le=1.)
    component_nrmse: float=Field(default=1e-6,gt=0,le=1.)
    min_magnitude_contrast: float=Field(default=.005,ge=0,le=1.)
    max_total_rf_energy: float=Field(default=200.,gt=0,le=1000.)
    max_prepared_duration_s: float=Field(default=100.,gt=0,le=100.)


class DerivedBudget(Strict):
    max_work_per_scenario: int=Field(default=20000000000,ge=1,le=50000000000)
    max_total_work: int=Field(default=250000000000,ge=1,le=800000000000)
    max_memory_bytes_per_scenario: int=Field(default=134217728,ge=1,le=134217728)
    max_samples_per_scenario: int=Field(default=24576,ge=1,le=24576)


class CalibratedRadialStudy(Strict):
    candidates: list[RadialPulseCandidate]=Field(default_factory=lambda:[RadialPulseCandidate(),
        RadialPulseCandidate(refocusing_angle=140.,refocusing_end_angle=110.)],min_length=1,max_length=3)
    numerics: RadialNumerics=Field(default_factory=RadialNumerics)
    targets: DerivedTargets=Field(default_factory=DerivedTargets)
    budget: DerivedBudget=Field(default_factory=DerivedBudget)


def run_calibrated_radial_study(parent_record: dict, request: CalibratedRadialStudy | dict):
    sources=_checked_sources();spec=CalibratedRadialStudy.model_validate(request)
    verify_study_record(parent_record)
    # Preserve numeric token types of the original ExperimentGraph request.
    parent_spec=LabStudy.model_validate(json.loads(parent_record['request_json']))
    budget=spec.budget;parent_reserve=parent_spec.budget.max_total_work
    if parent_reserve>budget.max_total_work:
        raise ValueError('cannot reserve complete parent numerical revalidation')
    current=run_lab_study(parent_spec)
    parent_same=fingerprint(current)==parent_record['result_sha256']
    calibrated=current['validation']['calibration_and_holdout_passed']
    applied=bool(parent_same and calibrated)
    fits=current['calibration'];order=parent_spec.tissue_order
    if [f['tissue_id'] for f in fits]!=order:
        raise ValueError('calibration tissue order does not bind labels 0/1')
    mean=[f['t2_s'] for f in fits]
    bindings=[dict(parameter='basis_t2_s',component=i,tissue_id=f['tissue_id'],value=f['t2_s'],unit='s',
        standard_uncertainty_s=f['t2_std_s'],stress_interval_s=f['t2_interval_s'],
        parent_calibration_sha256=fingerprint(f)) for i,f in enumerate(fits)] if applied else []
    scenarios=[dict(name='nominal',sample_t2_s=mean)] if applied else []
    if applied:
        scenarios += [dict(name=f'corner-{i}',sample_t2_s=list(t2)) for i,t2 in enumerate(product(*(f['t2_interval_s'] for f in fits)))]
    reserved=parent_reserve+len(spec.candidates)*len(scenarios)*budget.max_work_per_scenario
    complete_reserve=reserved<=budget.max_total_work
    work=current['provenance']['estimated_work'];points=[];preview=None;preview_index=None
    for index,design in enumerate(spec.candidates):
        entry=dict(index=index,design=design.model_dump(mode='json'),scenarios=[],executed=False,eligible=False,reasons=[])
        if not parent_same: entry['reasons'].append('parent numerical study changed; no calibrated prior applied')
        if not calibrated: entry['reasons'].append('calibration or independent holdout failed; no radial design executed')
        if not complete_reserve: entry['reasons'].append('cannot reserve the complete fixed-prior uncertainty grid; no radial inverse executed')
        if not applied or not complete_reserve:
            points.append(entry);continue
        for scenario in scenarios:
            cap=budget.max_work_per_scenario
            row=dict(**scenario,basis_t2_s=mean,executable=False,passed=False)
            try:
                # Crucial: only the sample T2 changes at stress corners. Refitting
                # the reconstruction basis to every corner would hide prior error.
                run=run_radial_tse(parent_spec.labels,**design.model_dump(),**spec.numerics.model_dump(),
                    t2_s=scenario['sample_t2_s'],basis_t2_s=mean,
                    experiment=current['calibrated_experiment'],
                    max_work=cap,max_memory_bytes=budget.max_memory_bytes_per_scenario,
                    max_samples=budget.max_samples_per_scenario,max_duration_s=spec.targets.max_prepared_duration_s,
                    target_image_error=spec.targets.image_nrmse,target_coefficient_error=spec.targets.component_nrmse,
                    target_min_contrast=spec.targets.min_magnitude_contrast,
                    target_max_rf_energy=spec.targets.max_total_rf_energy)
                cost=run['provenance']['estimated_work']
                ntrains=len(run['timeline']);prep_duration=run['provenance']['preparation_duration_s']
                prep_trains=int(round(prep_duration/design.tr_s))
                if abs(prep_trains*design.tr_s-prep_duration)>1e-8:
                    raise ValueError('periodic EPG preparation duration is not an integer train count')
                per_train=run['validation']['rf_energy_relative']/ntrains
                total_rf=(ntrains+prep_trains)*per_train
                checks=dict(image=run['quality']['passed'],
                    components=run['validation']['coefficient_error']<=spec.targets.component_nrmse,
                    data=run['solvers'][0]['converged'],
                    contrast=run['validation']['roi_contrast']>=spec.targets.min_magnitude_contrast,
                    total_rf=total_rf<=spec.targets.max_total_rf_energy,
                    duration=run['validation']['total_duration_s']<=spec.targets.max_prepared_duration_s)
                row.update(executable=True,passed=all(checks.values()),checks=checks,
                    total_rf_energy_relative=total_rf,preparation_trains=prep_trains,
                    estimated_work=cost,run_hash=fingerprint(json_safe(run)),run=json_safe(run))
                work+=cost
                if scenario['name']=='nominal' and preview is None: preview=run;preview_index=index
            except ValueError as exc:
                # The failed model may have consumed its declared cap; it is not
                # a budget-free failed attempt. Reserve was checked for every row.
                work+=cap;row.update(reason=str(exc),estimated_work=cap)
            entry['scenarios'].append(row)
        entry['executed']=all(r['executable'] for r in entry['scenarios'])
        entry['eligible']=entry['executed'] and all(r['passed'] for r in entry['scenarios'])
        if entry['executed']:
            entry['worst_image_nrmse']=max(r['run']['quality']['nrmse'] for r in entry['scenarios'])
            entry['worst_component_nrmse']=max(r['run']['validation']['coefficient_error'] for r in entry['scenarios'])
            entry['worst_total_rf_energy']=max(r['total_rf_energy_relative'] for r in entry['scenarios'])
        if not entry['eligible']: entry['reasons'].append('one or more fixed-prior stress scenarios fail the declared targets')
        points.append(entry)
    eligible=[p for p in points if p['eligible']]
    selected=min(eligible,key=lambda p:p['worst_total_rf_energy']) if eligible else None
    if selected is not None:
        preview=selected['scenarios'][0]['run'];preview_index=selected['index']
    stages=[]
    for name,value in [('parent_numerical_revalidation',dict(expected=parent_record['result_sha256'],actual=fingerprint(current),matches=parent_same)),
                       ('calibrated_parameter_bindings',bindings),('fixed_prior_uncertainty_search',points),
                       ('target_validation',dict(selected_index=selected['index'] if selected else None,complete_reserve=complete_reserve))]:
        body=dict(stage=name,value_sha256=fingerprint(value),parents=[stages[-1]['sha256']] if stages else [])
        stages.append({**body,'sha256':fingerprint(body)})
    if _checked_sources()!=sources: raise ValueError('source changed during derived study')
    return dict(parent_clinical_question=parent_spec.experiment.clinical_recipe.question.model_dump(mode='json'),
        input_origin=parent_spec.dataset.origin,source_ref=parent_spec.dataset.source_ref,
        parent_legacy_record_sha256=parent_record['record_sha256'],parent_sources=parent_record['sources'],
        parent_result_revalidation=dict(expected_sha256=parent_record['result_sha256'],actual_sha256=fingerprint(current),matches=parent_same,
            full_parent_record_replay=False,scope='current numerical revalidation from original measurements, not relabeling the old source/runtime record'),
        parameter_bindings=bindings,fixed_basis_t2_s=mean if applied else None,
        t1_pd_priors=[dict(tissue_id=t.id,t1_s=t.t1,proton_density=t.proton_density,origin='authored_parent_prior') for t in parent_spec.experiment.tissue],
        candidates=points,selected_index=selected['index'] if selected else None,
        preview_simulation=json_safe(preview) if preview is not None else None,preview_candidate_index=preview_index,
        targets=spec.targets.model_dump(mode='json'),request=spec.model_dump(mode='json'),
        validation=dict(calibration_and_holdout_passed=calibrated,parent_result_revalidated=parent_same,
            calibrated_parameters_applied=applied,complete_budgeted_search=bool(applied and complete_reserve),selected_design_passed=selected is not None),
        provenance=dict(stages=stages,estimated_work=work,reserved_work=reserved if complete_reserve else parent_reserve,
            planned_work=reserved,dataset_sha256=current['provenance']['dataset_sha256'],
            current_parent_result_sha256=fingerprint(current),
            selection='minimum worst preparation+acquisition RF proxy among candidates passing all fixed-prior nominal/corner targets'),
        scope='teaching/research measurement-derived T2 priors; T1/PD authored; local rectangular stress corners are not joint confidence or clinical bounds; no scanner validation/clinical quality certification; B/C parked')
