import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from mrqlab_api.main import app
from mrqlab_api import scientific_records as module
from mrqlab_api.scientific_records import (
    ScientificPlan, ScientificStore, create_scientific_record,
    verify_scientific_record, replay_scientific_record,
    write_portable, read_portable,
)
from mrqlab_experiment.lab_study import build_lab_study_example, fingerprint


def plan(kind='tse',parameters=None):
    return dict(context=dict(study_id='shared-pilot',research_question='How does this pulse design change the declared signal?',
        target_rationale='Use the existing independent teaching-model targets.',
        background_references=[dict(source_ref='local:authored-note',origin='authored',note='Context only; no measured calibration claim.')]),
        execution=dict(type='run',kind=kind,parameters=parameters or {}))


@pytest.fixture(scope='module')
def record(): return create_scientific_record(plan())


@pytest.fixture
def local_store(tmp_path,monkeypatch):
    path=tmp_path/'records.sqlite3';monkeypatch.setattr(module,'default_store_path',lambda:path)
    return ScientificStore(path)


@pytest.mark.parametrize('kind',['tse','noncartesian','flow','pulsatile_flow','flow_epi','cest','cest_solomon','cest_memory','mrs','mrs_press','radial_tse'])
def test_all_research_chains_have_common_stages_and_exact_computational_replay(kind):
    record=create_scientific_record(plan(kind))
    assert verify_scientific_record(record)['integrity_passed']
    assert not verify_scientific_record(record)['computational_replay_performed']
    assert record['summary']['kind']==kind
    assert [s['stage'] for s in record['stages']]==['question','design_and_inputs','source_and_runtime','computed_execution','reported_validation']
    assert not record['summary']['background_references_applied']
    assert replay_scientific_record(record)['computational_replay_performed']


def test_measured_tse_retains_calibration_holdout_units_origins_and_replay():
    study=build_lab_study_example().model_dump(mode='json')
    request=plan();request['execution']=dict(type='measured_tse',study=study)
    record=create_scientific_record(request);payload=json.loads(record['payload_json'])
    assert record['summary']['input_origins']==['synthetic']
    assert all(p['executable'] for p in record['summary']['candidates'])
    assert len(payload['record']['result']['provenance']['stages'])==6
    assert payload['record']['request']['dataset']['measurements']==study['dataset']['measurements']
    assert replay_scientific_record(record)['computational_replay_performed']
    for row in study['dataset']['measurements']:
        if row['split']=='holdout': row['signal_a_u']+=.1
    failed=create_scientific_record(request)
    assert not failed['summary']['model_reported_passed'] and failed['summary']['selected_index'] is None
    assert not any(p['executable'] for p in failed['summary']['candidates'])


def test_search_retains_every_invalid_and_target_failed_candidate_and_selection():
    request=plan('mrs');request['execution'].update(type='search',candidates=[{'echo_s':.001},{'echo_s':.03}])
    record=create_scientific_record(request);points=record['summary']['candidates']
    assert not points[0]['executable'] and points[1]['executable']
    assert record['summary']['selected_index']==1
    assert replay_scientific_record(record)['computational_replay_performed']
    request=plan('tse');request['execution'].update(type='search',candidates=[{}])
    failed=create_scientific_record(request)
    assert not failed['summary']['model_reported_passed']
    assert failed['summary']['candidates'][0]['executable']


def test_browser_numeric_roundtrip_lossless_payload_and_idempotent_storage(record,local_store):
    request=plan();request['execution'].update(type='search',candidates=[{'refocusing_angle':180.}])
    record=create_scientific_record(request)
    raw=json.dumps(record)
    output=subprocess.run(['node','-e','let s="";process.stdin.on("data",c=>s+=c);process.stdin.on("end",()=>process.stdout.write(JSON.stringify(JSON.parse(s))))'],input=raw,text=True,capture_output=True,check=True).stdout
    browser=json.loads(output)
    assert type(browser['summary']['candidates'][0]['parameters']['refocusing_angle']) is int
    assert browser['payload_json']==record['payload_json'] and browser['request_json']==record['request_json']
    assert verify_scientific_record(browser)['integrity_passed']
    identity=local_store.save(record)
    assert local_store.save(browser)==identity and local_store.list()['total']==1
    assert replay_scientific_record(browser)['computational_replay_performed']


def test_atomic_concurrent_append_and_no_overwrite(record,local_store):
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids=list(pool.map(lambda _:local_store.save(record),range(8)))
    assert len(set(ids))==1 and local_store.list()['total']==1
    loaded=ScientificStore(local_store.path).get(ids[0]);assert loaded==record
    changed=copy.deepcopy(record);changed['summary']['model_reported_passed']=True
    with pytest.raises(ValueError,match='integrity'): local_store.save(changed)
    assert local_store.get(ids[0])==record


def test_payload_hash_and_stage_tampering_and_forged_scientific_pass(record):
    bad=copy.deepcopy(record);bad['payload_json']+=' '
    bad['record_sha256']=fingerprint({k:v for k,v in bad.items() if k!='record_sha256'})
    with pytest.raises(ValueError,match='payload hash'): verify_scientific_record(bad)
    bad=copy.deepcopy(record);bad['stages'][2]['parents']=[]
    bad['record_sha256']=fingerprint({k:v for k,v in bad.items() if k!='record_sha256'})
    with pytest.raises(ValueError,match='dependency'): verify_scientific_record(bad)
    # Self-consistent checksums do not prove physics. A forged reported pass can
    # be integrity-consistent, but actual numerical replay must reject it.
    bad=copy.deepcopy(record);payload=json.loads(bad['payload_json']);payload['view']['validation']['passed']=True
    bad['payload_json']=module._dump(payload);bad['payload_sha256']=module._sha(bad['payload_json'])
    request=json.loads(bad['request_json']);bad['summary']=module._summary(request,payload,bad['api_source_hash'])
    env={k:bad[k] for k in ['sources','api_source_hash','runtime']}
    bad['stages']=module._stages(request,bad['request_sha256'],bad['payload_sha256'],bad['summary'],env)
    bad['record_sha256']=fingerprint({k:v for k,v in bad.items() if k!='record_sha256'})
    assert verify_scientific_record(bad)['integrity_passed']
    with pytest.raises(ValueError,match='computational replay differs'): replay_scientific_record(bad)


def test_source_or_runtime_mismatch_and_expected_execution_hash_fail_closed(record,monkeypatch):
    monkeypatch.setattr(module,'runtime_manifest',lambda:{'changed':True})
    with pytest.raises(ValueError,match='runtime differs'): replay_scientific_record(record)
    monkeypatch.undo()
    monkeypatch.setattr(module,'_checked_sources',lambda:{'sha256':'0'*64,'files':{}})
    with pytest.raises(ValueError,match='source/dependency'): replay_scientific_record(record)
    monkeypatch.undo()
    request=plan();request['expected_execution_hash']='0'*64
    with pytest.raises(ValueError,match='expected run'): create_scientific_record(request)


def test_database_corruption_is_not_silently_returned_as_valid(record,local_store):
    identity=local_store.save(record)
    with sqlite3.connect(local_store.path) as conn:
        conn.execute('UPDATE records SET record_json=? WHERE id=?',('{}',identity))
    assert not local_store.list()['records'][0]['integrity_checked']
    with pytest.raises(ValueError): local_store.get(identity)
    with pytest.raises(ValueError): local_store.save(record)


def test_portable_file_create_only_and_duplicate_json_rejection(record,tmp_path):
    path=tmp_path/'record.json';write_portable(record,path)
    assert read_portable(path)==record
    with pytest.raises(FileExistsError): write_portable(record,path)
    bad=tmp_path/'duplicate.json';bad.write_text('{"context":1,"context":2}')
    with pytest.raises(ValueError,match='duplicate'): read_portable(bad)
    bad.write_text('{"value":NaN}')
    with pytest.raises(ValueError,match='nonfinite'): read_portable(bad)


def test_local_api_persistence_import_export_replay_and_strict_paths(record,local_store):
    client=TestClient(app)
    response=client.post('/research/records',json=plan())
    assert response.status_code==200,response.text
    data=response.json();identity=data['record']['record_sha256']
    assert data['verification']['integrity_passed'] and not data['verification']['computational_replay_performed']
    assert client.get('/research/records').json()['total']==1
    assert client.get('/research/records',params={'study_id':'other'}).json()['total']==0
    assert client.get('/research/records/'+identity).json()['record']==data['record']
    exported=client.get('/research/records/'+identity+'/export')
    assert exported.status_code==200 and 'attachment' in exported.headers['content-disposition']
    assert exported.json()==data['record']
    assert client.post('/research/records/import',json=exported.json()).status_code==200
    assert client.get('/research/records').json()['total']==1
    assert client.post('/research/records/'+identity+'/replay').json()['computational_replay_performed']
    assert client.get('/research/records/'+'0'*64).status_code==404
    assert client.get('/research/records/not-an-id').status_code==409
    invalid=plan();invalid['execution']['parameters']['unlock_milestone_b']=True
    assert client.post('/research/records',json=invalid).status_code==422
    assert client.get('/research/records').json()['total']==1


def test_background_measured_reference_cannot_silently_claim_calibration(local_store):
    request=plan();request['context']['background_references'][0]['usage']='calibration'
    with pytest.raises(ValueError): ScientificPlan.model_validate(request)
    assert local_store.list()['total']==0


def test_real_cli_new_process_persistence_replay_export_and_no_overwrite(tmp_path):
    request=tmp_path/'plan.json';request.write_text(json.dumps(plan()))
    store=tmp_path/'cli.sqlite3';record=tmp_path/'run.json';replayed=tmp_path/'replayed.json';exported=tmp_path/'export.json'
    command=[sys.executable,'-m','mrqlab_api.scientific_records','--store',str(store)]
    def run(args,ok=True):
        result=subprocess.run(command+list(map(str,args)),capture_output=True,text=True,timeout=30)
        assert (result.returncode==0)==ok,result.stderr
        return result
    run(['run',request,'--output',record]);identity=read_portable(record)['record_sha256']
    checked=run(['verify',record]);assert not json.loads(checked.stdout)['computational_replay_performed']
    run(['replay',record,'--output',replayed]);assert record.read_bytes()==replayed.read_bytes()
    run(['export',identity,'--output',exported]);assert exported.read_bytes()==record.read_bytes()
    assert json.loads(run(['list']).stdout)['total']==1
    run(['run',request,'--output',record],ok=False)
    assert read_portable(record)['record_sha256']==identity


def test_view_shape_tampering_is_rejected_before_rendering(record):
    bad=copy.deepcopy(record);payload=json.loads(bad['payload_json']);payload['view']['images'][0]['width']=999999
    bad['payload_json']=module._dump(payload);bad['payload_sha256']=module._sha(bad['payload_json'])
    bad['record_sha256']=fingerprint({k:v for k,v in bad.items() if k!='record_sha256'})
    with pytest.raises(ValueError,match='preview'): verify_scientific_record(bad)


def test_distinct_physics_records_persist_under_one_shared_question(local_store):
    for kind in ['tse','mrs']:
        local_store.save(create_scientific_record(plan(kind)))
    listing=local_store.list('shared-pilot')
    assert listing['total']==2 and {r['summary']['kind'] for r in listing['records']}=={'tse','mrs'}
    for row in listing['records']:
        loaded=local_store.get(row['record_sha256'])
        assert loaded['summary']['study_id']=='shared-pilot'
        assert replay_scientific_record(loaded)['computational_replay_performed']


def test_public_app_export_stays_compatible_without_cli_double_import():
    checked=subprocess.run([sys.executable,'-c','from mrqlab_api import app; from mrqlab_api.main import app as direct; assert app is direct'],capture_output=True,text=True,timeout=30)
    assert checked.returncode==0,checked.stderr
    checked=subprocess.run([sys.executable,'-m','mrqlab_api.scientific_records','--help'],capture_output=True,text=True,timeout=30)
    assert checked.returncode==0 and 'RuntimeWarning' not in checked.stderr


def test_derived_record_api_preserves_calibration_gate_and_parent_relation(local_store):
    client=TestClient(app);spec=build_lab_study_example().model_dump(mode='json')
    for row in spec['dataset']['measurements']:
        if row['split']=='holdout': row['signal_a_u']+=.1
    source=plan();source['execution']=dict(type='measured_tse',study=spec)
    saved=client.post('/research/records',json=source);assert saved.status_code==200,saved.text
    parent=saved.json()['record'];child=plan()
    child['execution']=dict(type='calibrated_radial_tse',parent_record_sha256=parent['record_sha256'],study={'candidates':[{}]})
    response=client.post('/research/records',json=child)
    assert response.status_code==200,response.text
    record=response.json()['record'];assert record['summary']['parent_record_sha256']==parent['record_sha256']
    assert not record['summary']['model_reported_passed'] and response.json()['view'] is None
    assert local_store.list()['total']==2
    assert client.post('/research/records/'+record['record_sha256']+'/replay').json()['computational_replay_performed']
    child['execution']['parent_record_sha256']='0'*64
    assert client.post('/research/records',json=child).status_code==404
    child['execution']['parent_record_sha256']=record['record_sha256']
    assert client.post('/research/records',json=child).status_code==422


def test_cli_import_preserves_integrity_without_claiming_computation(record,tmp_path):
    path=tmp_path/'record.json';write_portable(record,path);store=tmp_path/'imported.sqlite3'
    command=[sys.executable,'-m','mrqlab_api.scientific_records','--store',str(store),'import',str(path)]
    result=subprocess.run(command,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['computational_replay_performed'] is False
    assert ScientificStore(store).get(record['record_sha256'])==record
