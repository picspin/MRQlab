"""Operation physics, descriptor edits and the portable scientific replay chain."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from fastapi.testclient import TestClient

from mrqlab_api.main import app
from mrqlab_api import scientific_records as records
from mrqlab_experiment.lab_study import fingerprint
from mrqlab_experiment.linked_readout import verify_linked_readout
from mrqlab_experiment.sequence_operations import (
    OperationSequence, apply_operation_edits, operation_sequence_example, run_operation_sequence,
)


def parameters():
    return operation_sequence_example()['execution']['parameters']


@pytest.fixture(scope='module')
def parent():
    return records.create_scientific_record(operation_sequence_example())


def child_plan(parent, updates):
    return dict(context=json.loads(parent['request_json'])['context'], execution=dict(
        type='edited_operations', parent_record_sha256=parent['record_sha256'], parent_record=parent, updates=updates))


def test_complete_snapshot_matches_independent_rodrigues_and_direct_dft():
    p=parameters()
    p['operations']=[dict(id='rf',kind='hard_rf',flip_deg=63.,phase_deg=29.),
                     dict(id='gx',kind='gradient_hold',axis='x',amplitude_mt_m=.07,duration_s=.002),
                     dict(id='gy',kind='gradient_hold',axis='y',amplitude_mt_m=-.03,duration_s=.003),
                     dict(id='wait',kind='delay',duration_s=.004)]
    # Odd non-square grids expose centering/axis mistakes.
    p['labels']=[[0,1,0,1,0],[1,0,1,0,1],[0,0,1,1,0]]
    result=run_operation_sequence(p);pair=result['linked_readout']
    shape=np.shape(p['labels']);expected=np.empty(shape,complex)
    alpha,phase=np.deg2rad([63.,29.])
    for y,x in np.ndindex(shape):
        t=p['tissues'][p['labels'][y][x]]
        # Rodrigues acting on equilibrium z, followed by exact free evolution.
        initial=t['proton_density']*np.sin(alpha)*(np.sin(phase)-1j*np.cos(phase))
        xpos=(x-shape[1]//2)/shape[1]*.22;ypos=(y-shape[0]//2)/shape[0]*.22
        angle=2*np.pi*42.57747892e6*1e-3*(.07*.002*xpos-.03*.003*ypos)
        expected[y,x]=initial*np.exp(-.009/t['t2_s']+1j*angle)
    actual=pair['image']['values'];image=np.asarray(actual['real'])+1j*np.asarray(actual['imag'])
    np.testing.assert_allclose(image,expected.ravel(),atol=1e-14,rtol=0)
    signal=pair['signal_vector']['values'];samples=np.asarray(signal['real'])+1j*np.asarray(signal['imag'])
    direct=[]
    for ky,kx in np.ndindex(shape):
        direct.append(sum(expected[y,x]*np.exp(-2j*np.pi*((ky-shape[0]//2)*(y-shape[0]//2)/shape[0]+(kx-shape[1]//2)*(x-shape[1]//2)/shape[1])) for y,x in np.ndindex(shape)))
    np.testing.assert_allclose(samples,direct,atol=1e-13,rtol=0)
    for y,x in np.ndindex(shape):
        t=p['tissues'][p['labels'][y][x]]
        z=t['proton_density']*(1+(np.cos(alpha)-1)*np.exp(-.009/t['t1_s']))
        assert result['final_magnetization'][y*shape[1]+x][2]==pytest.approx(z,abs=1e-14)
    assert verify_linked_readout(pair)['complex_sample_count']==15
    assert pair['signal_vector']['sample_times_s']==[.002+.003+.004]*15


def test_order_refocusing_and_intermediate_states_have_physical_effect():
    p=parameters();p['tissues']=[dict(id='a',proton_density=1.,t1_s=1.,t2_s=.1)];p['labels']=[[0]*4]*4
    rf=dict(id='rf',kind='hard_rf',flip_deg=90.,phase_deg=0.)
    g=dict(id='g1',kind='gradient_hold',axis='x',amplitude_mt_m=.1,duration_s=.005)
    refocus=dict(id='refocus',kind='hard_rf',flip_deg=180.,phase_deg=0.)
    p['operations']=[rf,g,refocus,{**g,'id':'g2'}]
    result=run_operation_sequence(p)
    state=np.asarray(result['final_magnetization'])
    np.testing.assert_allclose(state[:,0]+1j*state[:,1],1j*np.exp(-.01/.1),atol=1e-14)
    assert [op['start_s'] for op in result['operation_trace']]==[0.,0.,.005,.005]
    p['operations']=[g,rf]
    before=np.asarray(run_operation_sequence(p)['final_magnetization'])
    p['operations']=[rf,g]
    after=np.asarray(run_operation_sequence(p)['final_magnetization'])
    assert not np.allclose(before,after)


def test_both_views_apply_identical_atomic_edits_and_replay(parent):
    untouched=copy.deepcopy(parent);children=[]
    for view in ['image','signal_vector']:
        updates=[dict(field='operations.excite.flip_deg',value=67.,view=view),
                 dict(field='operations.encode.amplitude_mt_m',value=-.04,view=view)]
        child=records.create_scientific_record(child_plan(parent,updates));children.append(child)
        payload=json.loads(child['payload_json'])
        assert payload['parent_computationally_replayed']
        assert payload['parameters_before_sha256']!=payload['parameters_after_sha256']
        assert records.replay_scientific_record(child)['computational_replay_performed']
        assert [s['stage'] for s in child['stages']][1:3]==['parent_image_signal_record','typed_parameter_edits']
    a,b=[json.loads(c['payload_json'])['run'] for c in children]
    assert a['result_hash']==b['result_hash']
    original=json.loads(parent['payload_json'])['result']['linked_readout'];changed=a['result']['linked_readout']
    assert original['structure']==changed['structure']
    assert original['image']['values']!=changed['image']['values']
    assert original['signal_vector']['values']!=changed['signal_vector']['values']
    assert parent==untouched


@pytest.mark.parametrize('edit',[
    dict(field='operations.unknown.flip_deg',value=80.),
    dict(field='operations.encode.axis',value='y'),
    dict(field='operations.excite.flip_deg',value=True),
    dict(field='operations.excite.flip_deg',value='90'),
    dict(field='operations.excite.flip_deg',value=float('nan')),
    dict(field='operations.excite.flip_deg',value=181.),
    dict(field='operations.encode.amplitude_mt_m',value=41.),
    dict(field='operations.wait.duration_s',value=0.),
    dict(field='operations.excite.flip_deg',value=60.,tissue_id='a'),
    dict(field='operations.excite.flip_deg',value=60.,path='operations.0'),
])
def test_rejected_edits_do_not_mutate_parent(parent,edit):
    original=copy.deepcopy(parent)
    with pytest.raises(ValueError): records.create_scientific_record(child_plan(parent,[edit]))
    assert parent==original


def test_duplicate_cross_view_and_coupled_duration_rejected(parent):
    edit=dict(field='operations.excite.flip_deg',value=70.)
    with pytest.raises(ValueError,match='duplicate'):
        records.create_scientific_record(child_plan(parent,[{**edit,'view':'image'},{**edit,'view':'signal_vector'}]))
    p=parameters();p['operations']=[dict(id=f'd{i}',kind='delay',duration_s=.5) for i in range(3)]
    pair=run_operation_sequence(p)['linked_readout']
    with pytest.raises(ValueError,match='two seconds'):
        apply_operation_edits(p,[dict(field='operations.d0.duration_s',value=1.),dict(field='operations.d1.duration_s',value=1.)],pair=pair)
    assert p['operations'][0]['duration_s']==.5


def test_gradient_only_edit_retains_magnitude_and_changes_complete_complex_data(parent):
    child=records.create_scientific_record(child_plan(parent,[dict(field='operations.encode.amplitude_mt_m',value=-.05)]))
    before=json.loads(parent['payload_json'])['result']['linked_readout']
    after=json.loads(child['payload_json'])['run']['result']['linked_readout']
    def complex_image(pair):
        v=pair['image']['values'];return np.asarray(v['real'])+1j*np.asarray(v['imag'])
    np.testing.assert_allclose(abs(complex_image(before)),abs(complex_image(after)),atol=1e-14,rtol=0)
    assert before['image']['values']!=after['image']['values']
    assert before['signal_vector']['values']!=after['signal_vector']['values']


@pytest.mark.parametrize('field,value',[
    ('operations.excite.flip_deg',45.),('operations.excite.phase_deg',-90.),
    ('operations.encode.amplitude_mt_m',-.02),('operations.encode.duration_s',.003),
    ('operations.wait.duration_s',.02),
])
def test_each_advertised_control_changes_the_bound_operation(parent,field,value):
    p=json.loads(parent['payload_json'])['replay_request']['parameters']
    pair=json.loads(parent['payload_json'])['result']['linked_readout']
    updated=apply_operation_edits(p,[dict(field=field,value=value)],pair=pair)
    _,identity,name=field.split('.')
    assert next(op for op in updated['operations'] if op['id']==identity)[name]==value
    assert updated!=p


def test_rehashed_capabilities_cannot_bind_arbitrary_operation_fields(parent):
    p=json.loads(parent['payload_json'])['replay_request']['parameters']
    pair=json.loads(parent['payload_json'])['result']['linked_readout']
    pair['controls'][0]['field']='operations.excite.arbitrary'
    pair['pair_sha256']=fingerprint({k:v for k,v in pair.items() if k!='pair_sha256'})
    assert verify_linked_readout(pair)['integrity_passed']
    with pytest.raises(ValueError,match='capabilities differ'):
        apply_operation_edits(p,[dict(field='operations.excite.arbitrary',value=60.)],pair=pair)


def test_operation_pair_must_pin_the_exact_inputs(parent):
    p=json.loads(parent['payload_json'])['replay_request']['parameters']
    pair=json.loads(parent['payload_json'])['result']['linked_readout']
    p['tissues'][0]['t1_s']=2.
    with pytest.raises(ValueError,match='input pin differs'):
        apply_operation_edits(p,[dict(field='operations.excite.flip_deg',value=60.)],pair=pair)


def test_mixed_edit_lineage_is_rejected_before_recursive_parent_verification(parent,monkeypatch):
    bad=copy.deepcopy(parent)
    # A hostile imported lineage must not evade the same-adapter depth counter.
    request=json.loads(bad['request_json']);request['execution']['type']='edited_tse'
    bad['request_json']=json.dumps(request)
    plan=child_plan(bad,[dict(field='operations.excite.flip_deg',value=60.)])
    def unexpected_verification(_):
        raise AssertionError('mixed lineage recursed before the adapter/depth check')
    monkeypatch.setattr(records,'verify_scientific_record',unexpected_verification)
    with pytest.raises(ValueError,match='mixed edit chains'):
        records._edit_parent(plan['execution'])


def test_parent_identity_source_and_runtime_are_pinned(parent):
    plan=child_plan(parent,[dict(field='operations.excite.flip_deg',value=60.)])
    plan['execution']['parent_record_sha256']='0'*64
    with pytest.raises(ValueError,match='identity'): records.create_scientific_record(plan)
    for key,value in [('api_source_hash','0'*64),('runtime',{'python':'unavailable'})]:
        bad=copy.deepcopy(parent);bad[key]=value
        bad['record_sha256']=fingerprint({k:v for k,v in bad.items() if k!='record_sha256'})
        with pytest.raises(ValueError):
            records.create_scientific_record(child_plan(bad,[dict(field='operations.excite.flip_deg',value=60.)]))


@pytest.mark.parametrize('change', ['duplicate_id','unknown_kind','boolean_label','ragged','unbound','too_many','duration','extra'])
def test_sequence_contract_rejects_invalid_or_excessive_work(change):
    p=parameters()
    if change=='duplicate_id': p['operations'][1]['id']='excite'
    elif change=='unknown_kind': p['operations'][0]['kind']='finite_rf'
    elif change=='boolean_label': p['labels'][0][0]=True
    elif change=='ragged': p['labels'][0]=[0,1]
    elif change=='unbound': p['labels'][0][0]=2
    elif change=='too_many': p['operations']=[dict(id=f'r{i}',kind='hard_rf',flip_deg=90.,phase_deg=0.) for i in range(33)]
    elif change=='duration': p['operations']=[dict(id=f'd{i}',kind='delay',duration_s=1.) for i in range(3)]
    else: p['operations'][0]['scanner_command']='run'
    with pytest.raises(ValueError): OperationSequence.model_validate(p)


def test_bounded_generations_and_adapter_separation(parent):
    cursor=parent
    for i in range(3): cursor=records.create_scientific_record(child_plan(cursor,[dict(field='operations.excite.flip_deg',value=80.+i)]))
    with pytest.raises(ValueError,match='three operation edit generations'):
        records.create_scientific_record(child_plan(cursor,[dict(field='operations.excite.flip_deg',value=70.)]))
    plan=child_plan(parent,[dict(field='rf.refocusing_start_deg',value=160.)]);plan['execution']['type']='edited_tse'
    with pytest.raises(ValueError,match='TSE'): records.create_scientific_record(plan)


def test_checksum_consistent_forged_parent_is_computationally_rejected(parent):
    bad=copy.deepcopy(parent);payload=json.loads(bad['payload_json']);payload['view']['validation']['passed']=False
    bad['payload_json']=records._dump(payload);bad['payload_sha256']=records._sha(bad['payload_json'])
    request=json.loads(bad['request_json']);bad['summary']=records._summary(request,payload,bad['api_source_hash'])
    bad['stages']=records._stages(request,bad['request_sha256'],bad['payload_sha256'],bad['summary'],{k:bad[k] for k in ['sources','api_source_hash','runtime']})
    bad['record_sha256']=fingerprint({k:v for k,v in bad.items() if k!='record_sha256'})
    assert records.verify_scientific_record(bad)['integrity_passed']
    with pytest.raises(ValueError,match='computational replay differs'):
        records.create_scientific_record(child_plan(bad,[dict(field='operations.excite.flip_deg',value=70.)]))


def test_http_failure_store_and_portable_ancestor_import(parent,tmp_path,monkeypatch):
    store=records.ScientificStore(tmp_path/'source.sqlite3');store.save(parent)
    monkeypatch.setattr(records,'default_store_path',lambda:tmp_path/'source.sqlite3');client=TestClient(app)
    plan=child_plan(parent,[dict(field='operations.encode.duration_s',value=.002)])
    del plan['execution']['parent_record']
    response=client.post('/research/records',json=plan)
    assert response.status_code==200,response.text
    child=response.json()['record']
    assert response.json()['view']['images']
    assert client.post(f"/research/records/{child['record_sha256']}/replay").json()['computational_replay_performed']
    exported=client.get(f"/research/records/{child['record_sha256']}/export").json()
    plan['execution']['updates'][0]['value']=.2
    assert client.post('/research/records',json=plan).status_code==422
    assert store.list()['total']==2
    monkeypatch.setattr(records,'default_store_path',lambda:tmp_path/'import.sqlite3')
    assert client.post('/research/records/import',json=exported).status_code==200
    assert client.get(f"/research/records/{parent['record_sha256']}").json()['record']==parent


def test_child_replays_identically_in_fresh_cli_process(parent,tmp_path):
    child=records.create_scientific_record(child_plan(parent,[dict(field='operations.excite.phase_deg',value=37.)]))
    source=tmp_path/'child.json';output=tmp_path/'replayed.json';source.write_text(records._dump(child))
    root=Path(__file__).resolve().parents[1]
    paths=['packages/sequence-ir','packages/physics','packages/recon','packages/mrqlab_experiment','services/api','services/local_agent']
    env={**os.environ,'PYTHONPATH':os.pathsep.join(str(root/p) for p in paths)}
    result=subprocess.run([sys.executable,'-m','mrqlab_api.scientific_records','--store',str(tmp_path/'cli.sqlite3'),
                           'replay',str(source),'--output',str(output)],cwd=root,env=env,text=True,capture_output=True)
    assert result.returncode==0,result.stderr
    assert json.loads(output.read_text())==child


def test_every_intermediate_state_matches_independent_scalar_rotation_and_relaxation():
    p = parameters()
    p['labels'] = [[0, 1, 0], [1, 0, 1]]
    p['operations'] = [
        dict(id='tip', kind='hard_rf', flip_deg=57., phase_deg=-32.),
        dict(id='gx', kind='gradient_hold', axis='x', amplitude_mt_m=-.06, duration_s=.003),
        dict(id='rotate', kind='hard_rf', flip_deg=113., phase_deg=71.),
        dict(id='wait', kind='delay', duration_s=.007),
        dict(id='gy', kind='gradient_hold', axis='y', amplitude_mt_m=.04, duration_s=.002),
    ]
    result = run_operation_sequence(p)
    expected = np.zeros((6, 3))
    for y, x in np.ndindex(2, 3):
        expected[y*3+x, 2] = p['tissues'][p['labels'][y][x]]['proton_density']
    elapsed = 0.
    for step, op in zip(result['operation_trace'], p['operations']):
        assert step['operation'] == op
        assert step['start_s'] == pytest.approx(elapsed, abs=1e-17)
        for y, x in np.ndindex(2, 3):
            index = y*3+x
            mx, my, mz = expected[index]
            if op['kind'] == 'hard_rf':
                # Independent scalar expansion of a transverse-axis rotation.
                angle, phase = np.deg2rad([op['flip_deg'], op['phase_deg']])
                c, s = np.cos(angle), np.sin(angle)
                nx, ny = np.cos(phase), np.sin(phase)
                projection = nx*mx + ny*my
                expected[index] = [mx*c + ny*mz*s + nx*projection*(1-c),
                                   my*c - nx*mz*s + ny*projection*(1-c),
                                   mz*c + (nx*my-ny*mx)*s]
            else:
                tissue = p['tissues'][p['labels'][y][x]]
                dt = op['duration_s']
                theta = 0.
                if op['kind'] == 'gradient_hold':
                    position = ((x-1)/3 if op['axis'] == 'x' else (y-1)/2)*.22
                    theta = 2*np.pi*42.57747892e6*1e-3*op['amplitude_mt_m']*position*dt
                decay = np.exp(-dt/tissue['t2_s'])
                expected[index] = [(mx*np.cos(theta)-my*np.sin(theta))*decay,
                                   (mx*np.sin(theta)+my*np.cos(theta))*decay,
                                   tissue['proton_density']+(mz-tissue['proton_density'])*np.exp(-dt/tissue['t1_s'])]
        elapsed += op.get('duration_s', 0.)
        assert step['end_s'] == pytest.approx(elapsed, abs=1e-17)
        np.testing.assert_allclose(step['magnetization'], expected, atol=1e-14, rtol=0)
    np.testing.assert_allclose(result['final_magnetization'], expected, atol=1e-14, rtol=0)


def test_two_second_boundary_is_consistent_for_root_edits_trace_and_snapshot():
    p = parameters()
    p['operations'] = [dict(id=f'g{i}', kind='gradient_hold', axis='x',
                            amplitude_mt_m=.02, duration_s=.1) for i in range(20)]
    result = run_operation_sequence(p)
    assert result['duration_s'] == result['operation_trace'][-1]['end_s'] == 2.
    assert result['linked_readout']['signal_vector']['sample_times_s'] == [2.]*16
    p['operations'][-1]['duration_s'] = .05
    pair = run_operation_sequence(p)['linked_readout']
    updated = apply_operation_edits(p, [dict(field='operations.g19.duration_s', value=.1)], pair=pair)
    assert run_operation_sequence(updated)['duration_s'] == 2.
    assert p['operations'][-1]['duration_s'] == .05
    updated['operations'].append(dict(id='excess', kind='delay', duration_s=1e-6))
    with pytest.raises(ValueError, match='two seconds'):
        run_operation_sequence(updated)


@pytest.mark.parametrize('count', [8, 9])
def test_http_edit_batch_boundary_is_atomic_and_preserves_parent(count, tmp_path, monkeypatch):
    plan = operation_sequence_example()
    plan['execution']['parameters']['operations'] = [
        dict(id=f'r{i}', kind='hard_rf', flip_deg=90., phase_deg=0.) for i in range(9)]
    parent = records.create_scientific_record(plan)
    untouched = copy.deepcopy(parent)
    store = records.ScientificStore(tmp_path/'batch.sqlite3')
    store.save(parent)
    monkeypatch.setattr(records, 'default_store_path', lambda: tmp_path/'batch.sqlite3')
    updates = [dict(field=f'operations.r{i}.flip_deg', value=45.) for i in range(count)]
    request = child_plan(parent, updates)
    del request['execution']['parent_record']
    response = TestClient(app).post('/research/records', json=request)
    assert response.status_code == (200 if count == 8 else 422), response.text
    assert store.list()['total'] == (2 if count == 8 else 1)
    assert store.get(parent['record_sha256']) == untouched == parent
    if count == 8:
        child = response.json()['record']
        retained = json.loads(child['payload_json'])['run']['replay_request']['parameters']['operations']
        assert [op['flip_deg'] for op in retained] == [45.]*8+[90.]
        assert records.replay_scientific_record(child)['computational_replay_performed']
