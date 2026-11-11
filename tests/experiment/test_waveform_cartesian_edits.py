import copy
import json

import pytest
from fastapi.testclient import TestClient

from mrqlab_api.main import app
from mrqlab_api import scientific_records as records
from mrqlab_experiment.lab_study import fingerprint
from mrqlab_experiment.waveform_cartesian import apply_waveform_cartesian_edits, run_waveform_cartesian
from test_waveform_cartesian import parameters


def root_plan():
    return dict(context=dict(study_id='editable-waveform',research_question='How does finite RF alter tissue contrast?',
                             target_rationale='Compare two synthetic tissue regions.'),
                execution=dict(type='waveform_cartesian',parameters=parameters()))


def child_plan(parent,updates,embed=True):
    execution=dict(type='edited_waveform_cartesian',parent_record_sha256=parent['record_sha256'],updates=updates)
    if embed: execution['parent_record']=parent
    return dict(context=json.loads(parent['request_json'])['context'],execution=execution)


@pytest.fixture(scope='module')
def parent():
    return records.create_scientific_record(root_plan())


def rf_edits(view,value=.1):
    return [dict(field=f'rf.samples.{i}.amplitude_ut',value=value,view=view) for i in range(3)]


def test_both_views_produce_same_image_signal_failed_target_and_replay(parent):
    original=copy.deepcopy(parent);runs=[]
    for view in ('image','signal_vector'):
        child=records.create_scientific_record(child_plan(parent,rf_edits(view)))
        payload=json.loads(child['payload_json']);runs.append(payload['run'])
        assert payload['parent_computationally_replayed'] is True
        assert payload['parameters_before_sha256']!=payload['parameters_after_sha256']
        assert child['summary']['model_reported_passed'] is False
        assert records.replay_scientific_record(child)['computational_replay_performed']
        assert [s['stage'] for s in child['stages']][1:3]==['parent_image_signal_record','typed_parameter_edits']
    assert parent==original
    assert runs[0]['result_hash']==runs[1]['result_hash']
    old=json.loads(parent['payload_json'])['result'];new=runs[0]['result']
    assert old['image']['magnitude']!=new['image']['magnitude']
    assert old['linked_readout']['signal_vector']['values']!=new['linked_readout']['signal_vector']['values']
    assert old['linked_readout']['structure']==new['linked_readout']['structure']
    assert old['encoding']==new['encoding']


def test_tissue_edit_is_bound_to_named_tissue_and_preserves_geometry(parent):
    p=json.loads(parent['payload_json']);original=p['replay_request']['parameters'];pair=p['result']['linked_readout']
    edited=apply_waveform_cartesian_edits(original,[dict(field='tissue.t2_s',tissue_id='b',value=.05,view='image')],pair=pair)
    assert edited['waveform']['tissues'][1]['t2_s']==.05
    assert edited['waveform']['tissues'][0]==original['waveform']['tissues'][0]
    assert edited['grid_indices']==original['grid_indices']
    with pytest.raises(ValueError,match='unsupported or unbound'):
        apply_waveform_cartesian_edits(original,[dict(field='tissue.t2_s',tissue_id='missing',value=.05)],pair=pair)


def test_duplicate_out_of_range_forged_controls_and_unbound_gradient_fail(parent):
    p=json.loads(parent['payload_json']);original=p['replay_request']['parameters'];pair=p['result']['linked_readout']
    with pytest.raises(ValueError,match='duplicate'):
        apply_waveform_cartesian_edits(original,[dict(field='rf.samples.0.amplitude_ut',value=10.,view='image'),
                                                  dict(field='rf.samples.0.amplitude_ut',value=11.,view='signal_vector')],pair=pair)
    with pytest.raises(ValueError,match='out-of-range'):
        apply_waveform_cartesian_edits(original,[dict(field='rf.samples.0.amplitude_ut',value=1001.)],pair=pair)
    with pytest.raises(ValueError,match='unsupported or unbound'):
        apply_waveform_cartesian_edits(original,[dict(field='gradient.gx',value=0.)],pair=pair)
    with pytest.raises(ValueError,match='unsupported or unbound'):
        apply_waveform_cartesian_edits(original,[dict(field='image_target.value',value=0.)],pair=pair)
    forged=copy.deepcopy(pair);forged['controls'][0]['max']=9999.
    forged['pair_sha256']=fingerprint({k:v for k,v in forged.items() if k!='pair_sha256'})
    with pytest.raises(ValueError,match='capabilities differ'):
        apply_waveform_cartesian_edits(original,[dict(field='rf.samples.0.amplitude_ut',value=10.)],pair=forged)


def test_three_generation_limit_and_no_cross_adapter_lineage(parent):
    cursor=parent
    for value in (14.,13.,12.):
        cursor=records.create_scientific_record(child_plan(cursor,[dict(field='rf.samples.0.amplitude_ut',value=value)]))
    with pytest.raises(ValueError,match='three waveform Cartesian edit generations'):
        records.create_scientific_record(child_plan(cursor,[dict(field='rf.samples.0.amplitude_ut',value=11.)]))
    cross=child_plan(cursor,[dict(field='rf.samples.0.amplitude_ut',value=11.)])
    cross['execution']['type']='edited_operations'
    with pytest.raises(ValueError,match='mixed edit chains'):
        records.create_scientific_record(cross)


def test_long_rf_is_readable_without_exposing_partial_sample_controls():
    p=parameters();rf=p['waveform']['sequence']['blocks'][0]['rf']
    rf.update(samples_ut=[15.]*33,phase_rad=[0.]*33,raster_s=1e-6)
    pair=run_waveform_cartesian(p)['linked_readout']
    assert not any(c['field'].startswith('rf.samples.') for c in pair['controls'])
    assert any(c['field']=='tissue.t2_s' for c in pair['controls'])


def test_api_store_parent_child_and_reject_invalid_atomic_edit(tmp_path,monkeypatch):
    monkeypatch.setattr(records,'default_store_path',lambda:tmp_path/'records.sqlite3')
    client=TestClient(app);root=client.post('/research/records',json=root_plan())
    assert root.status_code==200,root.text
    parent=root.json()['record']
    invalid=client.post('/research/records',json=child_plan(parent,rf_edits('image',0.),embed=False))
    assert invalid.status_code==422 and 'exactly one nonzero RF block' in invalid.text
    assert client.get('/research/records').json()['total']==1
    child=client.post('/research/records',json=child_plan(parent,rf_edits('image'),embed=False))
    assert child.status_code==200,child.text
    saved=child.json()['record']
    assert saved['summary']['parent_record_sha256']==parent['record_sha256']
    assert client.get('/research/records').json()['total']==2
    replay=client.post('/research/records/'+saved['record_sha256']+'/replay')
    assert replay.status_code==200 and replay.json()['computational_replay_performed']
