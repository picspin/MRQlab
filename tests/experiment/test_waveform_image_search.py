import copy
import json
from hashlib import sha256

import numpy as np
import pytest
from fastapi.testclient import TestClient

from mrqlab_api.main import app
from mrqlab_api import scientific_records as records
from mrqlab_experiment.waveform_cartesian import run_waveform_cartesian
from mrqlab_experiment.waveform_image_search import search_waveform_image
from test_waveform_cartesian import independent_signal, parameters


def request():
    base=parameters();base['waveform']['max_step_s']=1e-6
    return dict(base=base,rf_block_id='rf',scales=[0.,.1,.5,1.],
        scenarios=[dict(id='nominal',b0_delta_hz=0.,b1_scale_factor=1.),
                   dict(id='shifted',b0_delta_hz=20.,b1_scale_factor=.8)],
        signal_refinement_tolerance=1e-6,image_refinement_tolerance=1e-6,max_total_work=500000)


def test_image_grid_retains_all_candidates_and_selects_minimum_passing_energy():
    p=request();original=copy.deepcopy(p);result=search_waveform_image(p)
    assert p==original
    assert [v['scale'] for v in result['candidates']]==[0.,.1,.5,1.]
    assert [v['executable'] for v in result['candidates']]==[False,True,True,True]
    assert [v['eligible'] for v in result['candidates']]==[False,False,True,True]
    assert result['selected_index']==2 and result['validation']['passed']
    assert 'nonzero RF block' in result['candidates'][0]['reasons'][0]
    winner=result['candidates'][2]
    assert winner['rf_energy_proxy_ut2_s']==pytest.approx(3*(15*.5)**2*1e-5)
    for scenario in winner['scenarios']:
        assert scenario['target_passed'] and scenario['refinement_passed']
        assert scenario['refined']['waveform']['work']['voxel_steps']==2*scenario['coarse']['waveform']['work']['voxel_steps']
        assert scenario['refined']['linked_readout']['signal_vector']['sample_times_s']==pytest.approx([.0005,.0008,.0011,.0014])
    # Independent affine-exponential signal and direct inverse DFT for the
    # selected nominal waveform; no search result is used as its own reference.
    nominal=winner['scenarios'][0]['refined'];independent=copy.deepcopy(p['base'])
    independent['waveform']['sequence']['blocks'][0]['rf']['samples_ut']=[7.5]*3
    samples=nominal['waveform']['samples'];indices=independent['grid_indices']
    reference=[independent_signal(independent,s,i) for s,i in zip(samples,indices)]
    image=np.array([sum(reference[j]*np.exp(2j*np.pi*((ky-1)*(y-1)/2+(kx-1)*(x-1)/2))
                        for j,(ky,kx) in enumerate(indices))/4 for y,x in np.ndindex(2,2)])
    expected=float(np.mean(np.abs(image[[0,3]]))-np.mean(np.abs(image[[1,2]])))
    assert nominal['validation']['image_target']['measured']==pytest.approx(expected,abs=1e-9)
    actual=sum(s['coarse']['waveform']['work']['voxel_steps']+s['refined']['waveform']['work']['voxel_steps']
               for v in result['candidates'] for s in v['scenarios'])
    assert result['work']['total_voxel_steps']==actual
    assert search_waveform_image(p)==result


def test_failed_image_signal_and_refinement_are_not_selected():
    p=request();p['base']['image_target']['value']=100.
    result=search_waveform_image(p)
    assert result['selected_index'] is None and not result['validation']['passed']
    assert any('target failed' in x for x in result['candidates'][2]['reasons'])
    p=request();p['base']['waveform']['target']=dict(sample_index=0,metric='magnitude',operator='ge',value=100.)
    assert search_waveform_image(p)['selected_index'] is None
    p=request();p['image_refinement_tolerance']=0.
    result=search_waveform_image(p)
    assert not result['candidates'][2]['eligible']
    assert any('refinement tolerance failed' in x for x in result['candidates'][2]['reasons'])


def test_fine_only_image_target_pass_cannot_select():
    p=request();p['scales']=[1.];p['scenarios']=p['scenarios'][:1]
    coarse=run_waveform_cartesian(p['base'])['validation']['image_target']['measured']
    fine=copy.deepcopy(p['base']);fine['waveform']['substeps_per_interval']=2
    refined=run_waveform_cartesian(fine)['validation']['image_target']['measured']
    assert coarse!=refined
    p['base']['image_target']['operator']='ge' if refined>coarse else 'le'
    p['base']['image_target']['value']=(coarse+refined)/2
    result=search_waveform_image(p);s=result['candidates'][0]['scenarios'][0]
    assert s['refined']['validation']['passed'] and not s['coarse']['validation']['passed']
    assert result['selected_index'] is None


def test_budget_and_trajectory_fail_before_spin_integration(monkeypatch):
    import mrqlab_experiment.waveform_image_search as module
    import mrqlab_experiment.waveform_cartesian as cartesian
    def forbidden(*args,**kwargs): raise AssertionError('spin integration started')
    monkeypatch.setattr(module,'run_waveform_cartesian',forbidden)
    p=request();p['max_total_work']=1
    with pytest.raises(ValueError,match='no candidates were integrated'):
        module.search_waveform_image(p)
    monkeypatch.setattr(cartesian,'run_waveform_bloch',forbidden)
    p=parameters();p['grid_indices'][0],p['grid_indices'][1]=p['grid_indices'][1],p['grid_indices'][0]
    with pytest.raises(ValueError,match='gradient moment differs'):
        cartesian.run_waveform_cartesian(p)


def test_image_search_requires_image_target_and_nominal_scenario():
    p=request();p['base']['image_target']=None
    with pytest.raises(ValueError,match='explicit image target'): search_waveform_image(p)
    p=request();p['scenarios']=p['scenarios'][1:]
    with pytest.raises(ValueError,match='nominal B0/B1'): search_waveform_image(p)


def test_api_record_all_candidates_and_replay_without_fallback(tmp_path,monkeypatch):
    monkeypatch.setattr(records,'default_store_path',lambda:tmp_path/'records.sqlite3')
    plan=dict(context=dict(study_id='image-rf-search',research_question='How do RF scales affect synthetic reconstructed tissue contrast?',
                           target_rationale='Minimum RF proxy subject to an authored image target.'),
              execution=dict(type='waveform_image_search',parameters=request()))
    client=TestClient(app);response=client.post('/research/records',json=plan)
    assert response.status_code==200,response.text
    body=response.json();record=body['record'];result=json.loads(record['payload_json'])['result']
    assert record['summary']['candidate_count']==4 and record['summary']['selected_index']==2
    assert body['view']['images'][0]['values']==result['candidates'][2]['scenarios'][0]['refined']['image']['magnitude']
    assert records.replay_scientific_record(record)['computational_replay_performed']
    raw=json.loads(record['request_json']);payload=json.loads(record['payload_json'])
    forged=copy.deepcopy(payload)
    forged['result']['candidates'][2]['scenarios'][0]['coarse']['validation']['image_target']['measured']+=1.
    forged['result_hash']=sha256(json.dumps(forged['result'],sort_keys=True,allow_nan=False).encode()).hexdigest()
    with pytest.raises(ValueError,match='measurement differs from reconstructed pixels'):
        records._summary(raw,forged,record['api_source_hash'])
    forged=copy.deepcopy(payload);forged['result']['candidates'][2]['scenarios'][0]['max_image_difference']=0.
    forged['result_hash']=sha256(json.dumps(forged['result'],sort_keys=True,allow_nan=False).encode()).hexdigest()
    with pytest.raises(ValueError,match='refinement or target status differs'):
        records._summary(raw,forged,record['api_source_hash'])
    forged=copy.deepcopy(payload);forged['view']['images'][0]['values'][0]+=1.
    with pytest.raises(ValueError,match='preview differs'):
        records._summary(raw,forged,record['api_source_hash'])
    plan['execution']['parameters']['base']['image_target']['value']=100.
    failed=client.post('/research/records',json=plan)
    assert failed.status_code==200,failed.text
    assert failed.json()['record']['summary']['selected_index'] is None
    assert failed.json()['view']['images']==[] and failed.json()['view']['curves']==[]
