import pytest
from importlib.util import find_spec
from fastapi.testclient import TestClient
from mrqlab_api.main import app

client=TestClient(app)


@pytest.mark.parametrize('kind',['tse','noncartesian','flow','cest','mrs'])
def test_research_real_runner_and_source_pinned_replay(kind):
    response=client.post('/research/run',json={'kind':kind})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['result']['clinical_question'] and data['result']['design']
    assert data['view']['curves'] and 'passed' in data['view']['validation']
    assert data['view']['metrics'] and data['runtime']['numpy']
    assert len(data['source_hash'])==64
    replay=client.post('/research/run',json=data['replay_request'])
    assert replay.status_code==200,replay.text
    assert replay.json()['result_hash']==data['result_hash']
    assert replay.json()['result']['provenance']==data['result']['provenance']
    stale={**data['replay_request'],'expected_source_hash':'0'*64}
    assert client.post('/research/run',json=stale).status_code==409


@pytest.mark.parametrize('kind,patch',[('tse',{'echoes':True}),('tse',{'echoes':3}),
    ('tse',{'t2_s':[-1.,.1]}),('noncartesian',{'max_work':10000000001}),
    ('noncartesian',{'max_memory_bytes':1000000000}),('flow',{'spin_count':100000}),
    ('flow',{'r_peaks_s':[0.,100.]}),('cest',{'offsets_ppm':[-3.5,0.,3.5]}),
    ('mrs',{'points':10000}),('mrs',{'amounts':[1e300,1.,1.,1.]}),
    ('tse',{'unlock_milestone_b':True}),('flow',{'scanner_export':True}),
    ('tse',{'labels':[[0,1]]*17}),('tse',{'labels':[[0,1],[0]]})])
def test_research_limits_and_invalid_model_fail_closed(kind,patch):
    assert client.post('/research/run',json={'kind':kind,'parameters':patch}).status_code==422


def test_grid_search_replays_selected_point_and_preserves_failures():
    r=client.post('/research/search',json={'kind':'mrs','candidates':[{'echo_s':.001},{'echo_s':.03}]})
    assert r.status_code==200,r.text
    data=r.json()
    assert not data['candidates'][0]['feasible']
    assert data['best']['parameters']=={'echo_s':.03}
    repeated=client.post('/research/search',json=data['replay_search'])
    assert repeated.status_code==200,repeated.text
    assert repeated.json()['search_hash']==data['search_hash']
    run=data['best']['run']
    assert client.post('/research/run',json=run['replay_request']).json()['result_hash']==run['result_hash']
    no=client.post('/research/search',json={'kind':'mrs','candidates':[{'echo_s':.001}]})
    assert no.json()['best'] is None
    assert client.post('/research/search',json={'kind':'flow','candidates':[{}]*5}).status_code==422
    assert client.post('/research/search',json={'kind':'flow','candidates':[{'unknown':1}]}).status_code==422


def test_echo_weight_model_failure_is_visible_and_catalog_stays_locked():
    data=client.post('/research/run',json={'kind':'tse'}).json()
    assert not data['view']['validation']['passed']
    assert data['result']['psf_prediction_quality']['passed']
    assert 'scanner' not in data['replay_request']['parameters']
    # The product catalog does not acquire these research-only chains.
    catalog=client.get('/protocol-recipes').json()
    assert len(catalog['recipes'])==2


def test_live_source_edit_is_rejected_until_server_restart(monkeypatch):
    import mrqlab_api.research as module
    monkeypatch.setattr(module,'source_hash',lambda:'0'*64)
    response=client.post('/research/run',json={'kind':'tse'})
    assert response.status_code==409
    assert 'Restart' in response.text


@pytest.mark.skipif(find_spec('finufft') is None,reason='optional NUFFT backend')
def test_nufft_api_uses_native_backend_and_replays_all_result_fields():
    response=client.post('/research/run',json={'kind':'noncartesian','parameters':{'reconstruction':'nufft_cgls','inverse_tolerance':1e-11}})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['result']['provenance']['version']=='spatial-nufft-v1'
    assert data['result']['solvers'][0]['operator']['backend']=='finufft'
    assert data['view']['validation']['passed']
    replay=client.post('/research/run',json=data['replay_request'])
    assert replay.status_code==200,replay.text
    assert replay.json()['result_hash']==data['result_hash']
    assert client.post('/research/run',json={'kind':'noncartesian','parameters':{'reconstruction':'nufft_cgls','nufft_eps':1e-4}}).status_code==422


@pytest.mark.skipif(find_spec('finufft') is None,reason='optional NUFFT backend')
def test_only_fast_path_accepts_larger_grid_and_keeps_failed_image_target_visible():
    import numpy as np
    y,x=np.indices((32,32)); labels=(((x-16)**2+(y-16)**2)<64).astype(int).tolist()
    parameters={'labels':labels,'reconstruction':'nufft_cgls','inverse_max_iterations':1}
    response=client.post('/research/run',json={'kind':'noncartesian','parameters':parameters})
    assert response.status_code==200,response.text
    data=response.json()
    assert not data['view']['validation']['passed']
    assert not data['result']['solvers'][0]['converged']
    assert client.post('/research/run',json={'kind':'noncartesian','parameters':{**parameters,'reconstruction':'cgls'}}).status_code==422



def test_pulsatile_causal_backend_replays_interrupted_preparations_and_failed_targets():
    parameters={'r_peaks_s':[0.,.45,1.65],'observation_end_s':2.8,'radial_rings':4,'axial_spins':201}
    response=client.post('/research/run',json={'kind':'pulsatile_flow','parameters':parameters})
    assert response.status_code==200,response.text
    data=response.json()
    assert not data['view']['validation']['passed']
    assert len(data['result']['executions'])==2 and len(data['result']['readouts'])==1
    assert data['result']['gates'][0]['scheduled'] and not data['result']['gates'][0]['accepted']
    assert data['result']['provenance']['actual_hard_rf_count']==2
    replay=client.post('/research/run',json=data['replay_request'])
    assert replay.status_code==200,replay.text
    assert replay.json()['result_hash']==data['result_hash']
    absent=client.post('/research/run',json={'kind':'pulsatile_flow','parameters':{'r_peaks_s':[0.],'observation_end_s':.5}})
    assert absent.status_code==200,absent.text
    assert absent.json()['view']['curves']==[]
    assert 'Blood max |Mz|' not in absent.json()['view']['metrics']
    assert client.post('/research/run',json={'kind':'pulsatile_flow','parameters':{'radial_rings':True}}).status_code==422
    assert client.post('/research/run',json={'kind':'pulsatile_flow','parameters':{'max_work':100}}).status_code==422


def test_pulsatile_search_preserves_cancellation_and_prediction_failures():
    response=client.post('/research/search',json={'kind':'pulsatile_flow','parameters':{'radial_rings':4,'axial_spins':201},'candidates':[{'inversion_time_s':.9},{'inversion_time_s':1.3}]})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['candidates'][1]['run']['result']['validation']['completed_readouts']==0
    assert not data['candidates'][1]['run']['view']['validation']['passed']
    assert data['best']['parameters']=={'inversion_time_s':.9}
    assert client.post('/research/search',json=data['replay_search']).json()['search_hash']==data['search_hash']


def test_solomon_relay_api_actual_signed_contrast_and_source_pinned_replay():
    response=client.post('/research/run',json={'kind':'cest_solomon'})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['view']['validation']['passed']
    assert data['result']['metrics']['relayed_noe_contrast']>.005
    assert data['result']['provenance']['dipolar_rates']['sigma_s1']<0
    assert not any(data['result']['provenance']['liquid_system']['rates'][4])
    assert client.post('/research/run',json=data['replay_request']).json()['result_hash']==data['result_hash']
    fast=client.post('/research/run',json={'kind':'cest_solomon','parameters':{'tau_c_s':1e-10}})
    assert fast.status_code==200,fast.text
    assert fast.json()['view']['metrics']['relayed_noe_contrast']<0
    assert not fast.json()['view']['validation']['passed']
    assert client.post('/research/run',json={'kind':'cest_solomon','parameters':{'distance_m':0.}}).status_code==422
    assert client.post('/research/run',json={'kind':'cest_solomon','parameters':{'offsets_ppm':[-3.5,0.,3.5]}}).status_code==422


def test_solomon_pulse_search_preserves_failed_target_and_keeps_molecular_priors_fixed():
    response=client.post('/research/search',json={'kind':'cest_solomon','candidates':[{'b1_uT':.1},{'b1_uT':1.}]})
    assert response.status_code==200,response.text
    data=response.json()
    assert not data['candidates'][0]['run']['view']['validation']['passed']
    assert data['best']['parameters']=={'b1_uT':1.}
    assert client.post('/research/search',json={'kind':'cest_solomon','candidates':[{'tau_c_s':1e-8}]}).status_code==422
    assert client.post('/research/search',json=data['replay_search']).json()['search_hash']==data['search_hash']
