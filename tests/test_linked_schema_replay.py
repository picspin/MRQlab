"""Common typed edits through the existing bounded TSE scientific carrier."""
import copy
import json
import subprocess
import sys
import pytest
from fastapi.testclient import TestClient
from mrqlab_api.main import app
from mrqlab_api import scientific_records as records
from mrqlab_experiment.tse_control import contrast_tse_example
from mrqlab_experiment.lab_study import fingerprint


@pytest.fixture(scope='module')
def parent(): return records.create_scientific_record(contrast_tse_example())


def plan(parent,view):
    return dict(context=json.loads(parent['request_json'])['context'],execution=dict(type='edited_tse',parent_record_sha256=parent['record_sha256'],parent_record=parent,
        updates=[dict(field='rf.refocusing_start_deg',value=180.,view=view),dict(field='rf.refocusing_end_deg',value=180.,view=view),
                 dict(field='tissue.concentration_mmol_l',tissue_id='gray_matter',value=.5,view=view)]))


def test_either_view_recomputes_identical_complete_pair_and_pins(parent):
    before=copy.deepcopy(parent)
    children=[records.create_scientific_record(plan(parent,view)) for view in ['image','signal_vector']]
    runs=[json.loads(child['payload_json'])['run'] for child in children]
    assert children[0]['record_sha256']!=children[1]['record_sha256']  # edit origin retained
    assert runs[0]['result']['linked_readout']==runs[1]['result']['linked_readout']
    pair=runs[0]['result']['linked_readout']
    assert pair['provenance']['source_sha256']==parent['sources']['sha256']
    assert pair['provenance']['runtime']==parent['runtime']
    assert pair['provenance']['inputs_sha256']==fingerprint(runs[0]['replay_request']['parameters'])
    assert len(pair['image']['values']['real'])==len(pair['signal_vector']['values']['real'])==256
    assert pair['image']['values']!=json.loads(parent['payload_json'])['result']['linked_readout']['image']['values']
    assert not children[0]['summary']['model_reported_passed']
    for child in children: assert records.replay_scientific_record(child)['computational_replay_performed']
    assert parent==before


def test_full_parent_child_export_import_links_library_and_fresh_cli(parent,tmp_path,monkeypatch):
    monkeypatch.setattr(records,'default_store_path',lambda:tmp_path/'original.sqlite3')
    client=TestClient(app);records.ScientificStore().save(parent)
    request=plan(parent,'signal_vector');request['execution'].pop('parent_record')
    response=client.post('/research/records',json=request);assert response.status_code==200,response.text
    child=response.json()['record']; exported=[]
    for record in [parent,child]:
        result=client.get('/research/records/'+record['record_sha256']+'/export')
        assert result.status_code==200 and result.json()==record
        exported.append(result.json())
    monkeypatch.setattr(records,'default_store_path',lambda:tmp_path/'imported.sqlite3')
    # Import just the portable child: its immutable parent must remain navigable.
    imported=client.post('/research/records/import',json=exported[1])
    assert imported.status_code==200,imported.text
    assert client.get('/research/records/'+parent['record_sha256']).json()['record']==exported[0]
    assert client.get('/research/records').json()['total']==2
    for record in exported:
        assert client.post('/research/records/'+record['record_sha256']+'/replay').json()['computational_replay_performed']
        assert records.replay_scientific_record(record)['computational_replay_performed']
        path=tmp_path/(record['record_sha256']+'.json');records.write_portable(record,path)
        output=tmp_path/(record['record_sha256']+'-replayed.json')
        completed=subprocess.run([sys.executable,'-m','mrqlab_api.scientific_records','--store',str(tmp_path/'fresh-cli.sqlite3'),'replay',str(path),'--output',str(output)],text=True,capture_output=True,timeout=30)
        assert completed.returncode==0,completed.stderr
        assert output.read_bytes()==path.read_bytes()


def test_http_rejection_preserves_failure_and_saves_no_child(parent,tmp_path,monkeypatch):
    monkeypatch.setattr(records,'default_store_path',lambda:tmp_path/'rejected.sqlite3')
    client=TestClient(app);records.ScientificStore().save(parent)
    request=plan(parent,'image');request['execution']['updates']=[dict(field='gradient.waveform',value=10.,view='image')]
    response=client.post('/research/records',json=request)
    assert response.status_code==422 and 'physical gradient waveform edits unsupported' in response.json()['detail']
    assert client.get('/research/records').json()['total']==1
    assert records.ScientificStore().get(parent['record_sha256'])==parent
