import copy
import json

import pytest
from fastapi.testclient import TestClient

from mrqlab_api.main import app
from mrqlab_api import scientific_records as records
from mrqlab_experiment.lab_study import build_lab_study_example, fingerprint
from test_waveform_image_search import request as image_search_request


def parent_plan(failed=False):
    study=build_lab_study_example().model_dump(mode='json')
    study['candidates']=study['candidates'][:1]
    if failed:
        for row in study['dataset']['measurements']:
            if row['split']=='holdout': row['signal_a_u']+=.1
    return dict(context=dict(study_id='lab-calibration',research_question='Calibrate research T2 from CPMG echoes',
                             target_rationale='Independent holdout of two synthetic tissue surrogates.'),
                execution=dict(type='measured_tse',study=study))


def derived_plan(parent,budget=1_000_000):
    ids=json.loads(parent['request_json'])['execution']['study']['tissue_order']
    search=image_search_request();base=search['base'];search['scales']=[.1,.5,1.]
    search['max_total_work']=budget
    for tissue,identity in zip(base['waveform']['tissues'],ids): tissue['id']=identity
    base['image_target']['target_tissue_id']=ids[0];base['image_target']['reference_tissue_id']=ids[1]
    # These are deliberately different authored placeholder T2s. They must be
    # replaced by the verified calibration, while T1 and PD stay authored.
    base['waveform']['tissues'][0]['t2_s']=.02;base['waveform']['tissues'][1]['t2_s']=.03
    return dict(context=dict(study_id='measured-waveform',research_question='Which finite RF scale preserves reconstructed contrast under T2 uncertainty?',
                             target_rationale='Synthetic held-out CPMG calibration and declared image threshold.'),
                execution=dict(type='measured_waveform_image',parent_record_sha256=parent['record_sha256'],parent_record=parent,
                               study=dict(search=search,max_parent_work=1_000_000_000)))


@pytest.fixture(scope='module')
def parent(): return records.create_scientific_record(parent_plan())


def test_verified_calibration_drives_all_t2_corners_and_replays(parent):
    plan=derived_plan(parent);before=copy.deepcopy(plan);record=records.create_scientific_record(plan)
    assert plan==before
    result=json.loads(record['payload_json'])['derivation']
    assert result['measurement']['origin']=='synthetic'
    assert result['parent_revalidation']['passed'] and result['validation']['calibration_and_holdout_passed']
    assert [b['value'] for b in result['bindings']]==pytest.approx([.04,.12],abs=1e-9)
    assert len(result['stress_scenarios'])==5 and len(result['stress_runs'])==5
    assert [x['id'] for x in result['stress_runs']]==['nominal','corner_0','corner_1','corner_2','corner_3']
    assert result['validation']['complete_grid'] and result['selected_index']==1
    assert result['work']['total_voxel_steps']==sum(x['result']['work']['total_voxel_steps'] for x in result['stress_runs'])
    nominal=result['stress_runs'][0]['search']['base']['waveform']['tissues']
    original=plan['execution']['study']['search']['base']['waveform']['tissues']
    assert [t['t2_s'] for t in nominal]==pytest.approx([.04,.12],abs=1e-9)
    assert [(t['t1_s'],t['proton_density']) for t in nominal]==[(t['t1_s'],t['proton_density']) for t in original]
    pair=result['stress_runs'][1]['result']['candidates'][1]['scenarios'][0]['refined']['linked_readout']
    assert pair['provenance']['origin']=='mixed: authored synthetic model and lab-derived T2'
    refs=pair['provenance']['source_refs']
    assert all(r['t2_binding']['measurement_origin']=='synthetic' and r['t2_binding']['stress_id']=='corner_0' for r in refs)
    assert all('no lab receiver gain transferred' in r['other_parameters_origin'] for r in refs)
    assert record['summary']['input_origins']==['authored_model_inputs','synthetic']
    assert records.replay_scientific_record(record)['computational_replay_performed']
    assert [s['stage'] for s in record['stages']][:3]==['question','parent_measurement_record','design_and_inputs']
    # Rehashing a forged per-pair lab source still cannot evade parent binding.
    forged=json.loads(record['payload_json']);changed=forged['derivation']['stress_runs'][1]['result']['candidates'][1]['scenarios'][0]['refined']['linked_readout']
    changed['provenance']['source_refs'][0]['t2_binding']['measurement_origin']='measured'
    changed['pair_sha256']=fingerprint({k:v for k,v in changed.items() if k!='pair_sha256'})
    with pytest.raises(ValueError,match='pair T2 binding differs'):
        records._validate_measured_waveform(json.loads(record['request_json'])['execution'],forged,record['api_source_hash'])


def test_failed_holdout_never_applies_fit_or_executes_search():
    parent=records.create_scientific_record(parent_plan(failed=True))
    result=json.loads(records.create_scientific_record(derived_plan(parent))['payload_json'])['derivation']
    assert not result['validation']['calibration_and_holdout_passed']
    assert result['bindings']==[] and result['stress_runs']==[] and result['selected_index'] is None
    assert all(not candidate['executed'] for candidate in result['candidates'])
    assert 'independent holdout failed' in result['validation']['reasons'][0]


def test_declared_measurement_origin_remains_distinct_from_synthetic_geometry():
    # A synthetic numerical fixture is explicitly relabelled only to exercise
    # provenance propagation; this is not an actual measured dataset.
    plan=parent_plan();dataset=plan['execution']['study']['dataset']
    dataset['origin']='measured';dataset['source_ref']='test:declared-measurement-only'
    parent=records.create_scientific_record(plan);child=derived_plan(parent)
    child['execution']['study']['search']['scales']=[.5]
    child['execution']['study']['search']['scenarios']=child['execution']['study']['search']['scenarios'][:1]
    record=records.create_scientific_record(child);result=json.loads(record['payload_json'])['derivation']
    assert record['summary']['input_origins']==['authored_model_inputs','measured','synthetic']
    assert result['measurement']['source_ref']=='test:declared-measurement-only'
    refs=result['stress_runs'][0]['result']['candidates'][0]['scenarios'][0]['refined']['linked_readout']['provenance']['source_refs']
    assert all(r['t2_binding']['measurement_origin']=='measured' for r in refs)
    assert all(r['origin']=='mixed' for r in refs)


def test_total_corner_budget_prevents_all_image_integration(parent,monkeypatch):
    import mrqlab_experiment.measured_waveform_image as module
    original=module.search_waveform_image
    def preflight_only(search,*,_preflight_only=False):
        if not _preflight_only: raise AssertionError('image integration started')
        return original(search,_preflight_only=True)
    monkeypatch.setattr(module,'search_waveform_image',preflight_only)
    result=module.run_measured_waveform_study(json.loads(parent['payload_json'])['record'],
                                               derived_plan(parent,budget=130000)['execution']['study'])
    assert not result['validation']['complete_grid'] and result['selected_index'] is None
    assert result['stress_runs']==[] and result['work']['total_voxel_steps']==0
    assert result['work']['preflight_voxel_steps']>130000
    assert 'shared max_total_work' in result['validation']['reasons'][0]


def test_t2_corner_can_reject_a_nominally_passing_image_design(parent):
    plan=derived_plan(parent);search=plan['execution']['study']['search']
    search['scales']=[.5];search['base']['image_target']['value']=.01866
    result=json.loads(records.create_scientific_record(plan)['payload_json'])['derivation']
    assert result['stress_runs'][0]['result']['candidates'][0]['eligible']
    assert not result['stress_runs'][2]['result']['candidates'][0]['eligible']
    assert result['validation']['complete_grid'] and result['selected_index'] is None


def test_invalid_rf_candidate_is_not_misreported_as_executed(parent):
    plan=derived_plan(parent);search=plan['execution']['study']['search']
    search['scales']=[0.,.5];search['scenarios']=search['scenarios'][:1]
    record=records.create_scientific_record(plan)
    result=json.loads(record['payload_json'])['derivation']
    assert result['validation']['complete_grid'] and result['selected_index']==1
    assert not result['candidates'][0]['executed'] and not result['candidates'][0]['eligible']
    assert all(not outcome['executable'] for outcome in result['candidates'][0]['stress_outcomes'])
    assert record['summary']['candidates'][0]['executable'] is False


def test_wrong_tissues_and_parent_budget_are_rejected_before_lab_reexecution(parent,monkeypatch):
    import mrqlab_experiment.measured_waveform_image as module
    def forbidden(*args,**kwargs): raise AssertionError('lab recomputation started')
    monkeypatch.setattr(module,'run_lab_study',forbidden)
    legacy=json.loads(parent['payload_json'])['record'];plan=derived_plan(parent)['execution']['study']
    plan['max_parent_work']=1
    with pytest.raises(ValueError,match='reserve parent lab-study work'):
        module.run_measured_waveform_study(legacy,plan)
    plan=derived_plan(parent)['execution']['study'];plan['search']['base']['waveform']['tissues'][0]['id']='not_a_lab_tissue'
    plan['search']['base']['image_target']['target_tissue_id']='not_a_lab_tissue'
    with pytest.raises(ValueError,match='exactly match the two lab-study tissue IDs'):
        module.run_measured_waveform_study(legacy,plan)


def test_api_preserves_parent_origin_and_no_fallback(tmp_path,monkeypatch):
    monkeypatch.setattr(records,'default_store_path',lambda:tmp_path/'records.sqlite3')
    client=TestClient(app);root=client.post('/research/records',json=parent_plan())
    assert root.status_code==200,root.text
    parent=root.json()['record'];template=client.get('/research/records/'+parent['record_sha256']+'/waveform-example')
    assert template.status_code==200,template.text
    assert template.json()['parent']['origin']=='synthetic'
    assert template.json()['parent']['tissue_ids']==json.loads(parent['request_json'])['execution']['study']['tissue_order']
    plan=derived_plan(parent);plan['execution'].pop('parent_record');plan['execution']['study']=template.json()['study']
    child=client.post('/research/records',json=plan)
    assert child.status_code==200,child.text
    body=child.json();assert body['record']['summary']['parent_record_sha256']==parent['record_sha256']
    assert body['record']['summary']['selected_index']==1 and len(body['view']['images'])==1
    assert client.get('/research/records').json()['total']==2
    plan['execution']['study']['search']['base']['image_target']['value']=100.
    failed=client.post('/research/records',json=plan)
    assert failed.status_code==200,failed.text
    assert failed.json()['record']['summary']['selected_index'] is None
    assert failed.json()['view']['images']==[] and failed.json()['view']['curves']==[]
