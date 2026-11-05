import copy
import json
import numpy as np
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from mrqlab_api.main import app
from mrqlab_api import scientific_records as module
from mrqlab_api.scientific_records import create_scientific_record,verify_scientific_record,replay_scientific_record
from mrqlab_experiment.tse_control import contrast_tse_example,TSEEdit,apply_tse_edits
from mrqlab_experiment.linked_readout import verify_linked_readout
from mrqlab_experiment.lab_study import fingerprint


@pytest.fixture(scope='module')
def parent(): return create_scientific_record(contrast_tse_example())


def child_plan(parent,updates):
    return dict(context=json.loads(parent['request_json'])['context'],execution=dict(type='edited_tse',parent_record_sha256=parent['record_sha256'],parent_record=parent,updates=updates))


def test_semantic_edits_replay_parent_keep_immutable_structure_and_recompute_both_views(parent):
    untouched=copy.deepcopy(parent);before=json.loads(parent['payload_json'])
    updates=[dict(field='tissue.concentration_mmol_l',tissue_id='gray_matter',value=.5),dict(field='rf.refocusing_start_deg',value=160.)]
    record=create_scientific_record(child_plan(parent,updates));payload=json.loads(record['payload_json']);after=payload['run']
    assert parent==untouched and payload['parent_computationally_replayed']
    assert record['summary']['parent_record_sha256']==parent['record_sha256']
    assert record['summary']['input_origins']==['authored_model_inputs','synthetic']
    first=before['result']['linked_readout'];second=after['result']['linked_readout']
    assert first['structure']==second['structure'] and first['pair_sha256']!=second['pair_sha256']
    assert first['image']['values']!=second['image']['values'] and first['signal_vector']['values']!=second['signal_vector']['values']
    assert before['result_hash']!=after['result_hash'] and verify_linked_readout(second)['transform_passed']
    binding=after['result']['provenance']['physical'][1]['contrast_relaxation_bindings'][0]
    assert binding['exposure']['concentration_mmol_l']==.5
    assert replay_scientific_record(record)['computational_replay_performed']
    assert [s['stage'] for s in record['stages']][1:3]==['parent_image_signal_record','typed_parameter_edits']


def test_tse_search_preserves_exposure_origin_for_all_computed_candidates():
    plan=contrast_tse_example();plan['execution'].update(type='search',candidates=[{},dict(refocusing_angle=160.)])
    record=create_scientific_record(plan)
    assert record['summary']['input_origins']==['authored_model_inputs','synthetic']
    assert replay_scientific_record(record)['computational_replay_performed']


@pytest.mark.parametrize('update',[
    dict(field='gradient.amplitude',value=10.),dict(field='rf.refocusing_start_deg',value=True),
    dict(field='rf.refocusing_start_deg',value='180'),dict(field='encoding.order',value='random'),
    dict(field='tissue.concentration_mmol_l',value=.2),dict(field='timing.tr_s',tissue_id='gray_matter',value=.2)])
def test_typed_control_contract_rejects_unimplemented_or_ambiguous_fields(update):
    with pytest.raises(ValueError): TSEEdit.model_validate(update)


def test_duplicate_and_unbound_tissue_edits_are_not_silent_noops(parent):
    parameters=json.loads(parent['payload_json'])['replay_request']['parameters']
    update=dict(field='timing.tr_s',value=.8)
    with pytest.raises(ValueError,match='duplicate'): apply_tse_edits(parameters,[update,update])
    with pytest.raises(ValueError,match='existing explicit'): apply_tse_edits(parameters,[dict(field='tissue.concentration_mmol_l',tissue_id='unknown',value=.1)])


def test_concentration_domain_and_rf_timing_validation_apply_before_child_save(parent):
    for update in [dict(field='tissue.concentration_mmol_l',tissue_id='gray_matter',value=2.),dict(field='rf.refocusing_start_deg',value=200.),dict(field='timing.tr_s',value=.001)]:
        with pytest.raises((ValueError,HTTPException)): create_scientific_record(child_plan(parent,[update]))


def test_parent_identity_and_source_are_enforced(parent):
    request=child_plan(parent,[dict(field='timing.tr_s',value=.6)]);request['execution']['parent_record_sha256']='0'*64
    with pytest.raises(ValueError,match='identity'): create_scientific_record(request)
    changed=copy.deepcopy(parent);changed['payload_json']=changed['payload_json'].replace('synthetic','measured',1)
    with pytest.raises(ValueError,match='integrity'): create_scientific_record(child_plan(changed,[dict(field='timing.tr_s',value=.6)]))


def test_checksum_consistent_forged_parent_target_is_recomputed_before_derivation(parent):
    bad=copy.deepcopy(parent);payload=json.loads(bad['payload_json']);payload['view']['validation']['passed']=True
    bad['payload_json']=module._dump(payload);bad['payload_sha256']=module._sha(bad['payload_json'])
    request=json.loads(bad['request_json']);bad['summary']=module._summary(request,payload,bad['api_source_hash'])
    bad['stages']=module._stages(request,bad['request_sha256'],bad['payload_sha256'],bad['summary'],{k:bad[k] for k in ['sources','api_source_hash','runtime']})
    bad['record_sha256']=fingerprint({k:v for k,v in bad.items() if k!='record_sha256'})
    assert verify_scientific_record(bad)['integrity_passed']
    with pytest.raises(ValueError,match='computational replay differs'):
        create_scientific_record(child_plan(bad,[dict(field='timing.tr_s',value=.6)]))


def test_single_echo_has_no_unused_terminal_refocuser_control():
    from mrqlab_experiment.tse_imaging import run_tse_imaging
    pair=run_tse_imaging(np.indices((8,8))[0]%2,echoes=1)['linked_readout']
    assert not any(c['field']=='rf.refocusing_end_deg' for c in pair['controls'])
    with pytest.raises(ValueError,match='single-echo'):
        apply_tse_edits({'echoes':1},[dict(field='rf.refocusing_end_deg',value=130.)])


def test_bounded_edit_generations_prevent_unbounded_replay(parent):
    for i in range(3): parent=create_scientific_record(child_plan(parent,[dict(field='timing.tr_s',value=.5+.05*i)]))
    with pytest.raises(ValueError,match='three TSE edit generations'):
        create_scientific_record(child_plan(parent,[dict(field='timing.tr_s',value=.7)]))


def test_http_stored_parent_portable_child_and_actual_replay(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'default_store_path',lambda:tmp_path/'records.sqlite3');client=TestClient(app)
    request=client.get('/research/contrast-study/example').json()
    parent=client.post('/research/records',json=request)
    assert parent.status_code==200,parent.text
    identity=parent.json()['record']['record_sha256']
    plan=dict(context=request['context'],execution=dict(type='edited_tse',parent_record_sha256=identity,updates=[dict(field='tissue.concentration_mmol_l',tissue_id='gray_matter',value=.4)]))
    edited=client.post('/research/records',json=plan)
    assert edited.status_code==200,edited.text
    record=edited.json()['record'];payload=json.loads(record['payload_json'])
    assert payload['parent_record_sha256']==identity and edited.json()['view']['images']
    assert json.loads(record['request_json'])['execution']['parent_record']==parent.json()['record']
    assert verify_scientific_record(record)['integrity_passed']
    replay=client.post('/research/records/'+record['record_sha256']+'/replay')
    assert replay.status_code==200 and replay.json()['computational_replay_performed']
    exported=client.get('/research/records/'+record['record_sha256']+'/export').json()
    assert client.post('/research/records/import',json=exported).json()['record']==record
