import base64
import copy
import json
import pytest
from fastapi.testclient import TestClient
from mrqlab_api.main import app
from mrqlab_api import scientific_records as records
from mrqlab_experiment.flow_study import build_flow_study_example

client=TestClient(app)


def plan():
    study=build_flow_study_example().model_dump(mode='json')
    study['numerics']=dict(radial_rings=4,axial_spins=201,rf_steps=32)
    study['candidates']=[dict(inversion_time_s=.9)]
    return dict(context=dict(study_id='flow-csv-test',research_question=study['research_question'],target_rationale=study['target_rationale']),
        execution=dict(type='measured_flow',study=study))


def test_csv_api_keeps_bytes_and_requires_explicit_origin():
    s=client.get('/research/flow-study/example').json();d=s['dataset']
    req=dict(csv_base64=d['raw_csv_base64'],source_ref='local:user-velocity.csv',origin='measured')
    r=client.post('/research/flow-study/import-csv',json=req)
    assert r.status_code==200,r.text
    assert r.json()['raw_csv_base64']==d['raw_csv_base64'] and r.json()['raw_file_sha256']==d['raw_file_sha256']
    assert r.json()['origin']=='measured'
    req.pop('origin');assert client.post('/research/flow-study/import-csv',json=req).status_code==422


@pytest.mark.parametrize('raw',[b'not CSV',b'\xff\x00',b''])
def test_csv_api_rejects_malformed_data(raw):
    r=client.post('/research/flow-study/import-csv',json=dict(csv_base64=base64.b64encode(raw).decode(),source_ref='x',origin='synthetic'))
    assert r.status_code==422


def test_shared_record_retains_raw_fit_all_corners_and_full_replay(tmp_path,monkeypatch):
    monkeypatch.setattr(records,'default_store_path',lambda:tmp_path/'records.sqlite3')
    response=client.post('/research/records',json=plan())
    assert response.status_code==200,response.text
    body=response.json();record=body['record'];identity=record['record_sha256'];payload=json.loads(record['payload_json'])
    assert record['summary']['input_origins']==['synthetic'] and not record['summary']['model_reported_passed']
    assert payload['flow_study']['calibration']['passed'] and body['view']['curves']
    assert len(payload['flow_study']['candidates'][0]['scenarios'])==9
    assert [s['stage'] for s in record['stages']]==['question','raw_velocity_measurements','source_and_runtime','conditional_pressure_calibration','design_and_inputs','computed_execution','reported_validation']
    assert not body['verification']['computational_replay_performed']
    exported=client.get(f'/research/records/{identity}/export')
    assert exported.status_code==200 and exported.json()==record
    imported=client.post('/research/records/import',json=exported.json())
    assert imported.status_code==200 and imported.json()==body
    replay=client.post(f'/research/records/{identity}/replay')
    assert replay.status_code==200,replay.text
    assert replay.json()['computational_replay_performed'] and replay.json()['record_sha256']==identity
    bad=copy.deepcopy(record);bad['payload_json']=bad['payload_json'].replace('conditional measured-velocity','invented measured-velocity')
    assert client.post('/research/records/import',json=bad).status_code==422


def test_archived_csv_change_is_rejected_before_execution():
    request=plan();request['execution']['study']['dataset']['measurements'][0]['velocity_m_s']+=.1
    r=client.post('/research/records',json=request)
    assert r.status_code==422 and 'archived CSV' in r.text
