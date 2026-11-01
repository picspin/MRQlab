"""Bounded agentic inference carried by the existing scientific replay chain."""
import copy
import json
import pytest
from fastapi.testclient import TestClient
from mrqlab_api.main import app
from mrqlab_api import scientific_records as records
from mrqlab_experiment.agentic_inference import verify_agentic_inference
from mrqlab_experiment.lab_study import fingerprint
from mrqlab_experiment.tse_control import contrast_tse_example


@pytest.fixture(scope='module')
def parent(): return records.create_scientific_record(contrast_tse_example())


def plan(parent,reference=None):
    execution=dict(type='agentic_inference',parent_record_sha256=parent['record_sha256'],parent_record=parent)
    if reference is not None: execution['reference_tissue_id']=reference
    return dict(context=json.loads(parent['request_json'])['context'],execution=execution)


@pytest.fixture(scope='module')
def child(parent): return records.create_scientific_record(plan(parent))


def test_child_recomputes_from_the_complete_parent_pair_and_records_seven_stages(parent,child):
    before=copy.deepcopy(parent);payload=json.loads(child['payload_json']);inference=payload['inference']
    summary=child['summary'];pair=json.loads(parent['payload_json'])['result']['linked_readout']
    assert summary['mode']=='agentic_inference' and summary['kind']=='agentic_inference'
    assert summary['model_reported_passed'] is True and summary['candidate_count']==1
    assert summary['parent_record_sha256']==parent['record_sha256']
    assert summary['parent_pair_sha256']==pair['pair_sha256']
    assert summary['inference_sha256']==fingerprint(inference)
    assert payload['parent_computationally_replayed'] is True
    assert payload['parent_pair_sha256']==pair['pair_sha256']
    assert [node['stage'] for node in child['stages']]==['question','parent_image_signal_record','agentic_signal_inference',
        'design_and_inputs','source_and_runtime','computed_execution','reported_validation']
    assert inference['source']['pair_sha256']==pair['pair_sha256']
    assert inference['source']['source_sha256']==pair['provenance']['source_sha256']
    assert inference['source']['runtime']==pair['provenance']['runtime']
    assert inference['reference']==dict(tissue_id='white_matter',definition='first declared tissue')
    assert inference['proportions']['acquisition']['available'] is True
    assert len(inference['ingestion']['echo_bins'])==4
    view=payload['view']
    assert view['validation']['passed'] is True
    assert len(view['images'])==len(inference['modalities'])==5
    assert all(image['width']==16 and image['height']==16 and len(image['values'])==256 for image in view['images'])
    assert [curve['label'] for curve in view['curves']]==['white_matter','gray_matter']
    assert all(len(curve['x'])==len(curve['y'])==4 for curve in view['curves'])
    assert view['metrics']['Complete complex samples read']==256
    assert verify_agentic_inference(inference)['integrity_passed']
    assert records.verify_scientific_record(child)['computational_replay_performed'] is False
    replay=records.replay_scientific_record(child)
    assert replay['computational_replay_performed'] and replay['record_sha256']==child['record_sha256']
    assert parent==before


def test_explicit_reference_changes_the_gauge_and_unknown_reference_is_rejected_before_saving(parent,tmp_path,monkeypatch):
    inference=json.loads(records.create_scientific_record(plan(parent,'gray_matter'))['payload_json'])['inference']
    assert inference['reference']==dict(tissue_id='gray_matter',definition='explicit request')
    acquisition=inference['proportions']['acquisition']
    assert acquisition['contrast_vs_reference']['gray_matter']==[0.,0.,0.,0.]
    assert acquisition['apparent_relative_contrast_decay_s']['gray_matter'] is None
    assert acquisition['relative_contrast_strength']['gray_matter']==0.
    assert acquisition['contrast_vs_reference']['white_matter']!=[0.,0.,0.,0.]
    assert any(item['item']=='per_tissue_t2_map' for item in inference['unavailable'])
    monkeypatch.setattr(records,'default_store_path',lambda:tmp_path/'agentic.sqlite3')
    client=TestClient(app);records.ScientificStore().save(parent)
    rejected=client.post('/research/records',json=plan(parent,'not_a_tissue'))
    assert rejected.status_code==422 and 'reference tissue' in rejected.json()['detail']
    assert client.get('/research/records').json()['total']==1
    request=plan(parent,'gray_matter');request['execution'].pop('parent_record')
    accepted=client.post('/research/records',json=request)
    assert accepted.status_code==200,accepted.text
    body=accepted.json();assert body['record']['summary']['mode']=='agentic_inference'
    assert body['view']['validation']['passed'] is True
    assert client.get('/research/records').json()['total']==2
    assert client.get('/research/records/'+body['record']['record_sha256']).json()['record']==body['record']


def test_portable_child_import_keeps_the_embedded_parent_navigable(parent,child,tmp_path,monkeypatch):
    monkeypatch.setattr(records,'default_store_path',lambda:tmp_path/'ported.sqlite3')
    client=TestClient(app)
    imported=client.post('/research/records/import',json=child)
    assert imported.status_code==200,imported.text
    assert client.get('/research/records').json()['total']==2
    assert client.get('/research/records/'+parent['record_sha256']).json()['record']==parent
    assert client.get('/research/records/'+child['record_sha256']).json()['record']==child
    assert client.post('/research/records/'+child['record_sha256']+'/replay').json()['computational_replay_performed']


def test_integrity_only_accepts_a_self_consistent_forgery_but_replay_rejects_it(child):
    payload=json.loads(child['payload_json']);inference=payload['inference']
    inference['proportions']['acquisition']['relative_contrast_strength']['gray_matter']+=1e-3
    inference['inference_sha256']=fingerprint({k:v for k,v in inference.items() if k!='inference_sha256'})
    payload_json=records._dump(payload);payload_sha=records._sha(payload_json)
    request=json.loads(child['request_json'])
    summary=records._summary(request,payload,child['api_source_hash'])
    environment={k:child[k] for k in ['sources','api_source_hash','runtime']}
    body=dict(schema_version=records.SCHEMA,request_json=child['request_json'],request_sha256=child['request_sha256'],
        payload_json=payload_json,payload_sha256=payload_sha,sources=child['sources'],
        api_source_hash=child['api_source_hash'],runtime=child['runtime'],summary=summary,
        stages=records._stages(request,child['request_sha256'],payload_sha,summary,environment))
    forged={**body,'record_sha256':fingerprint(body)}
    assert records.verify_scientific_record(forged)['computational_replay_performed'] is False
    with pytest.raises(ValueError,match='full scientific computational replay differs'):
        records.replay_scientific_record(forged)
