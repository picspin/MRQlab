import copy
import base64
import hashlib
import csv
import io
import pytest
from fastapi.testclient import TestClient
from mrqlab_api.main import app
from mrqlab_experiment.lab_study import fingerprint

client=TestClient(app)


def test_measured_study_api_runs_all_stages_and_replays_exact_record():
    spec=client.get('/research/lab-study/example').json()
    assert spec['dataset']['origin']=='synthetic'
    response=client.post('/research/lab-study/run',json=spec)
    assert response.status_code==200,response.text
    body=response.json();record=body['record']
    assert body['view']['images'] and body['view']['curves']
    assert record['result']['selected_index']==0
    assert len(record['result']['provenance']['stages'])==6
    replay=client.post('/research/lab-study/replay',json=record)
    assert replay.status_code==200,replay.text
    assert replay.json()==body
    altered=copy.deepcopy(record);altered['result']['selected_index']=2
    assert client.post('/research/lab-study/replay',json=altered).status_code==409


def test_failed_holdout_has_no_selected_preview_or_silent_fallback():
    spec=client.get('/research/lab-study/example').json()
    for row in spec['dataset']['measurements']:
        if row['split']=='holdout': row['signal_a_u']+=.1
    response=client.post('/research/lab-study/run',json=spec)
    assert response.status_code==200,response.text
    body=response.json()
    assert body['view'] is None and body['record']['result']['selected_index'] is None
    assert not body['record']['result']['validation']['calibration_and_holdout_passed']


def test_measurement_csv_import_strict_units_origin_and_raw_hash():
    spec=client.get('/research/lab-study/example').json();rows=spec['dataset']['measurements']
    text=io.StringIO();writer=csv.DictWriter(text,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    raw=b'\xef\xbb\xbf'+text.getvalue().encode()
    req=dict(csv_base64=base64.b64encode(raw).decode(),source_ref='local:phantom-echoes.csv',origin='measured')
    response=client.post('/research/lab-study/import-echoes',json=req)
    assert response.status_code==200,response.text
    assert response.json()['origin']=='measured' and response.json()['raw_file_sha256']==hashlib.sha256(raw).hexdigest()
    req['csv_base64']=base64.b64encode(raw.replace(b'echo_time_s',b'echo_time_ms')).decode()
    assert client.post('/research/lab-study/import-echoes',json=req).status_code==422


@pytest.mark.parametrize('field,value',[('labels',[[0,1]]*17),('candidates',[{}]*9),('tissue_order',['white_matter','unknown'])])
def test_invalid_measured_study_is_rejected(field,value):
    spec=client.get('/research/lab-study/example').json();spec[field]=value
    assert client.post('/research/lab-study/run',json=spec).status_code==422
