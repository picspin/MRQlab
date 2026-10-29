import copy
import json
import numpy as np
import pytest
from mrqlab_experiment.calibrated_radial import CalibratedRadialStudy,run_calibrated_radial_study
from mrqlab_experiment.lab_study import build_lab_study_example,fingerprint
from mrqlab_experiment.study_records import create_study_record
from mrqlab_api.scientific_records import (ScientificStore,create_scientific_record,replay_scientific_record,
    verify_scientific_record,read_portable,write_portable)


@pytest.fixture(scope='module')
def parent(): return create_study_record(build_lab_study_example())


@pytest.fixture(scope='module')
def derived(parent): return run_calibrated_radial_study(parent,{'candidates':[{}]})


def test_nominal_pass_is_not_robust_uncertainty_pass_and_targets_are_not_relaxed(derived):
    r=derived
    assert r['validation']['parent_result_revalidated'] and r['validation']['calibration_and_holdout_passed']
    assert r['validation']['calibrated_parameters_applied'] and r['validation']['complete_budgeted_search']
    assert not r['validation']['selected_design_passed'] and r['selected_index'] is None
    rows=r['candidates'][0]['scenarios'];assert len(rows)==5 and rows[0]['name']=='nominal'
    assert rows[0]['passed'] and all(not p['passed'] for p in rows[1:])
    assert r['targets']['component_nrmse']==1e-6 and r['targets']['image_nrmse']==1e-6
    assert r['candidates'][0]['worst_component_nrmse']>.01


def test_seconds_tissue_binding_and_fixed_basis_across_all_sample_corners(parent,derived):
    fits=parent['result']['calibration'];bindings=derived['parameter_bindings']
    assert [b['tissue_id'] for b in bindings]==parent['request']['tissue_order']
    assert [b['value'] for b in bindings]==[f['t2_s'] for f in fits]
    assert all(b['unit']=='s' for b in bindings)
    nominal=derived['fixed_basis_t2_s'];rows=derived['candidates'][0]['scenarios']
    for row in rows:
        assert row['basis_t2_s']==nominal and row['run']['design']['basis_t2_s']==nominal
        assert row['run']['design']['t2_s']==row['sample_t2_s']
        assert np.asarray(row['run']['basis_echo_weights'])==pytest.approx(np.asarray(rows[0]['run']['basis_echo_weights']),abs=1e-14)
        assert not row['run']['solvers'][0]['gain_fit']
    assert any(p['sample_t2_s']!=nominal for p in rows[1:])
    # Independent ideal 180 CPMG decay ratio uses the sample T2, not the fixed fit prior.
    for row in rows:
        w=np.asarray(row['run']['tissue_echo_weights'])
        assert w[:,1]/w[:,0]==pytest.approx(np.exp(-.008/np.asarray(row['sample_t2_s'])),abs=1e-9)


def test_preparation_rf_and_work_are_counted(derived):
    assert derived['provenance']['estimated_work']<=derived['provenance']['reserved_work']<=250000000000
    for row in derived['candidates'][0]['scenarios']:
        assert row['total_rf_energy_relative']>row['run']['validation']['rf_energy_relative']
        assert row['preparation_trains']>0
    assert derived['parent_result_revalidation']['full_parent_record_replay'] is False


def test_failed_holdout_applies_no_prior_and_runs_no_inverse(monkeypatch):
    import mrqlab_experiment.calibrated_radial as module
    spec=build_lab_study_example().model_dump(mode='json')
    for row in spec['dataset']['measurements']:
        if row['split']=='holdout': row['signal_a_u']+=.1
    parent=create_study_record(spec)
    monkeypatch.setattr(module,'run_radial_tse',lambda *a,**kw:pytest.fail('failed holdout must not execute radial inverse'))
    r=run_calibrated_radial_study(parent,{'candidates':[{}]})
    assert not r['validation']['calibrated_parameters_applied'] and r['parameter_bindings']==[]
    assert r['preview_simulation'] is None and not r['candidates'][0]['executed']


def test_consistently_rehashed_but_changed_parent_numerics_are_not_used(parent,monkeypatch):
    import mrqlab_experiment.calibrated_radial as module
    forged=copy.deepcopy(parent);forged['result']['calibration'][0]['t2_s']*=1.2
    forged['result_sha256']=fingerprint(forged['result'])
    forged['record_sha256']=fingerprint({k:v for k,v in forged.items() if k!='record_sha256'})
    monkeypatch.setattr(module,'run_radial_tse',lambda *a,**kw:pytest.fail('changed parent numerics must not execute radial inverse'))
    r=run_calibrated_radial_study(forged,{'candidates':[{}]})
    assert not r['validation']['parent_result_revalidated'] and r['fixed_basis_t2_s'] is None
    assert not r['validation']['selected_design_passed'] and r['parameter_bindings']==[]


def test_complete_scenario_budget_reserved_before_first_inverse_and_parent_design_is_not_calibration_gate(parent,monkeypatch):
    import mrqlab_experiment.calibrated_radial as module
    request=build_lab_study_example().model_dump(mode='json');request['targets']['max_rf_energy_relative']=1.
    limited=create_study_record(request)
    assert limited['result']['validation']['calibration_and_holdout_passed'] and limited['result']['selected_index'] is None
    monkeypatch.setattr(module,'run_radial_tse',lambda *a,**kw:pytest.fail('incomplete reservation must not execute radial inverse'))
    r=run_calibrated_radial_study(limited,{'candidates':[{}],'budget':{'max_total_work':1000000000}})
    assert r['validation']['calibrated_parameters_applied'] and not r['validation']['complete_budgeted_search']
    assert r['candidates'][0]['scenarios']==[] and r['selected_index'] is None
    assert r['provenance']['estimated_work']<=r['provenance']['reserved_work']
    monkeypatch.setattr(module,'run_lab_study',lambda *a,**kw:pytest.fail('parent reservation must precede computation'))
    with pytest.raises(ValueError,match='reserve complete parent'):
        run_calibrated_radial_study(parent,{'budget':{'max_total_work':1}})


def test_partial_failure_never_double_charges_a_scenario(parent,monkeypatch):
    import mrqlab_experiment.calibrated_radial as module
    cap=1000
    monkeypatch.setattr(module,'run_radial_tse',lambda *a,**kw:{'provenance':{'estimated_work':cap//2,'preparation_duration_s':.1},'timeline':[{}]})
    r=run_calibrated_radial_study(parent,{'candidates':[{}],'budget':{'max_work_per_scenario':cap}})
    assert r['provenance']['estimated_work']==parent['result']['provenance']['estimated_work']+5*cap
    assert all(not s['executable'] and 'integer train' in s['reason'] for s in r['candidates'][0]['scenarios'])


@pytest.mark.parametrize('patch',[{'numerics':{'basis_t2_s':[.04,.12]}},{'candidates':[{'t2_s':[.04,.12]}]},
    {'budget':{'max_total_work':True}},{'targets':{'image_nrmse':0.}}])
def test_derived_fields_and_invalid_budgets_are_not_free_overrides(patch):
    with pytest.raises(ValueError): CalibratedRadialStudy.model_validate(patch)


def scientific_parent():
    return create_scientific_record(dict(context=dict(study_id='derived-measured-pilot',research_question='Calibrated pulse design?',target_rationale='Retain uncertainty and independent holdout.'),
        execution=dict(type='measured_tse',study=build_lab_study_example().model_dump(mode='json'))))


def test_portable_parent_child_records_replay_without_an_external_parent_store(tmp_path):
    parent=scientific_parent();source=ScientificStore(tmp_path/'source.sqlite3');source.save(parent)
    request=dict(context=dict(study_id='derived-measured-pilot',research_question='Can fixed priors preserve radial TSE components?',target_rationale='Retain strict image/component limits under measured uncertainty.'),
        execution=dict(type='calibrated_radial_tse',parent_record_sha256=parent['record_sha256'],study={'candidates':[{}]}))
    record=create_scientific_record(request,store=source)
    assert record['summary']['parent_record_sha256']==parent['record_sha256']
    assert not record['summary']['model_reported_passed'] and record['summary']['selected_index'] is None
    assert 'parent_measurement_record' in [s['stage'] for s in record['stages']]
    assert json.loads(record['request_json'])['execution']['parent_record']==parent
    path=tmp_path/'child.json';write_portable(record,path);portable=read_portable(path)
    destination=ScientificStore(tmp_path/'destination.sqlite3');destination.save(portable)
    assert destination.list()['total']==2 and destination.get(parent['record_sha256'])==parent
    assert verify_scientific_record(portable)['integrity_passed']
    assert replay_scientific_record(portable)['computational_replay_performed']
    wrong=copy.deepcopy(request);wrong['execution']['parent_record']=parent;wrong['execution']['parent_record_sha256']='0'*64
    with pytest.raises(ValueError,match='identity differs'): create_scientific_record(wrong)
