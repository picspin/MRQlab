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


def test_press_volume_api_real_complex_maps_targets_and_source_pinned_replay():
    response=client.post('/research/run',json={'kind':'mrs_press'})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['view']['validation']['passed']
    assert len(data['view']['images'])==2 and data['view']['images'][0]['width']==17
    assert isinstance(data['result']['localization'][0]['spatial_response'][0][0][0]['imag'],float)
    assert data['result']['provenance']['simulations'][0]['coherence_path']==[-1,1,-1]
    assert data['view']['metrics']['RF refinement error']<.002
    replay=client.post('/research/run',json=data['replay_request'])
    assert replay.status_code==200,replay.text
    assert replay.json()['result_hash']==data['result_hash']
    failed=client.post('/research/run',json={'kind':'mrs_press','parameters':{'basis_mode':'center'}})
    assert failed.status_code==200,failed.text
    assert not failed.json()['view']['validation']['passed']
    assert failed.json()['view']['metrics']['Max relative amount error']>.5
    for patch in [{'refine_grid':17},{'refine_rf_steps':64},{'grid_size':True},{'max_memory_bytes':1000},{'max_work':1000}]:
        assert client.post('/research/run',json={'kind':'mrs_press','parameters':patch}).status_code==422


def test_press_pulse_search_replays_all_candidates_and_forbids_prior_or_basis_tuning():
    response=client.post('/research/search',json={'kind':'mrs_press','parameters':{'echo_s':.008},
        'candidates':[{'rf_duration_s':.002},{'rf_duration_s':.001}]})
    assert response.status_code==200,response.text
    data=response.json()
    assert not data['candidates'][0]['feasible']
    assert data['best']['parameters']=={'rf_duration_s':.001}
    assert client.post('/research/search',json=data['replay_search']).json()['search_hash']==data['search_hash']
    for patch in [{'basis_j_hz':0.},{'grid_size':9},{'basis_mode':'center'},{'target_rf_error':1.}]:
        assert client.post('/research/search',json={'kind':'mrs_press','candidates':[patch]}).status_code==422


def test_radial_tse_actual_echo_model_and_full_result_replay():
    response=client.post('/research/run',json={'kind':'radial_tse'})
    assert response.status_code==200,response.text
    r=response.json()
    assert r['view']['validation']['passed'] and len(r['view']['images'])==3
    assert [i['scale_group'] for i in r['view']['images']]==['echo','echo','static_control']
    assert r['view']['metrics']['Component NRMSE']<1e-6
    assert r['result']['provenance']['acquisition']['backend']=='independent direct Fourier acquisition'
    assert r['result']['samples'][0][0]['imag'] is not None
    assert client.post('/research/run',json=r['replay_request']).json()['result_hash']==r['result_hash']
    for patch in [{'spokes':95},{'max_work':True},{'max_work':50000000001},{'max_memory_bytes':1},{'basis_t2_s':[.04,.04]}]:
        assert client.post('/research/run',json={'kind':'radial_tse','parameters':patch}).status_code==422


def test_radial_tse_constrained_search_selects_only_passing_targets_and_replays_failures():
    r=client.post('/research/search',json={'kind':'radial_tse','parameters':{'target_max_rf_energy':60.},
        'candidates':[{'refocusing_angle':180.,'refocusing_end_angle':180.},{'refocusing_angle':140.,'refocusing_end_angle':110.}]})
    assert r.status_code==200,r.text
    data=r.json()
    assert data['candidates'][0]['feasible'] and not data['candidates'][0]['run']['view']['validation']['passed']
    assert data['best']['parameters']=={'refocusing_angle':140.,'refocusing_end_angle':110.}
    assert client.post('/research/search',json=data['replay_search']).json()['search_hash']==data['search_hash']
    for patch in [{'t2_s':[.03,.12]},{'basis_t2_s':[.03,.12]},{'target_image_error':1.},{'backend':'finufft'}]:
        assert client.post('/research/search',json={'kind':'radial_tse','candidates':[patch]}).status_code==422
    none=client.post('/research/search',json={'kind':'radial_tse','parameters':{'target_max_rf_energy':1.},'candidates':[{}]})
    assert none.status_code==200,none.text
    assert none.json()['best'] is None and none.json()['candidates'][0]['feasible']


def test_flow_epi_runs_actual_gradients_images_and_exact_replay():
    response=client.post('/research/run',json={'kind':'flow_epi','parameters':{'axial_spins':201}})
    assert response.status_code==200,response.text
    data=response.json();r=data['result']
    assert r['validation']['completed_images']==2 and r['validation']['completed_encoding_pairs']==1
    assert not r['validation']['passed'] and r['readout_status'][0]['adc_samples']==256
    assert len(data['view']['images'])==6
    assert any('validity' in image['label'] for image in data['view']['images'])
    assert r['provenance']['waveform']['delta_encoding_m1_t_s2_m']>0
    assert r['executions'][0]['tissues']['blood']['samples'][0]['value'][1] is not None
    assert client.post('/research/run',json=data['replay_request']).json()['result_hash']==data['result_hash']
    assert len(client.get('/protocol-recipes').json()['recipes'])==2


def test_flow_epi_partial_readout_and_missing_pair_remain_unmeasured():
    partial=client.post('/research/run',json={'kind':'flow_epi','parameters':{'r_peaks_s':[0.,.917],'observation_end_s':1.4,'axial_spins':201}})
    assert partial.status_code==200,partial.text
    r=partial.json();assert not r['view']['images'] and not r['view']['curves']
    assert 0<r['result']['readout_status'][0]['adc_samples']<256
    assert 'Velocity RMSE vs moment reference (m/s)' not in r['view']['metrics']
    single=client.post('/research/run',json={'kind':'flow_epi','parameters':{'r_peaks_s':[0.],'observation_end_s':1.1,'axial_spins':201}}).json()
    assert len(single['view']['images'])==3 and single['view']['validation']['completed_encoding_pairs']==0
    assert not single['result']['velocity_pairs']


def test_flow_epi_search_keeps_failed_and_infeasible_points_without_best():
    request={'kind':'flow_epi','parameters':{'axial_spins':201},'candidates':[{'inversion_time_s':.6},{'inversion_time_s':.9},{'dwell_s':.00001}]}
    response=client.post('/research/search',json=request);assert response.status_code==200,response.text
    r=response.json();assert r['best'] is None
    assert r['candidates'][0]['feasible'] and r['candidates'][1]['feasible'] and not r['candidates'][2]['feasible']
    assert client.post('/research/search',json=r['replay_search']).json()['search_hash']==r['search_hash']
    for patch in [{'preparation':'none'},{'target_velocity_rmse_m_s':.1},{'mean_gradient_pa_m':0.},{'axial_spins':33},{'max_gradient_t_m':.1}]:
        assert client.post('/research/search',json={'kind':'flow_epi','candidates':[patch]}).status_code==422
    for patch in [{'matrix_size':True},{'axial_spins':1000},{'scanner_export':True},{'dwell_s':0.}]:
        assert client.post('/research/run',json={'kind':'flow_epi','parameters':patch}).status_code==422


def test_finite_memory_cest_zero_offset_refinement_and_full_complex_replay():
    r=client.post('/research/run',json={'kind':'cest_memory','parameters':{'offsets_ppm':[-3.5,0.,3.5]}})
    assert r.status_code==200,r.text
    data=r.json();result=data['result']
    assert result['validation']['numerical_refinement_passed'] and not result['validation']['passed']
    assert result['memory_diagnostics']['coarse_steps']==3840 and not result['memory_diagnostics']['inter_pulse_reset']
    assert len(result['provenance']['rf_holds_uT'])==3840
    assert result['spectra']['full'][1]>0 and 'mt_contrast_at_zero' in data['view']['metrics']
    assert client.post('/research/run',json=data['replay_request']).json()['result_hash']==data['result_hash']
    coarse=client.post('/research/run',json={'kind':'cest_memory','parameters':{'offsets_ppm':[-3.5,0.,3.5],'steps_per_bin':4}}).json()
    assert not coarse['view']['validation']['numerical_refinement_passed']


def test_finite_memory_cest_search_cannot_change_priors_or_hide_convergence_failures():
    request={'kind':'cest_memory','parameters':{'offsets_ppm':[-3.5,0.,3.5]},'candidates':[{'b1_uT':.5},{'b1_uT':1.},{'gap_s':.04001}]}
    r=client.post('/research/search',json=request);assert r.status_code==200,r.text
    result=r.json();assert result['best'] is None
    assert result['candidates'][0]['feasible'] and result['candidates'][1]['feasible'] and not result['candidates'][2]['feasible']
    assert client.post('/research/search',json=result['replay_search']).json()['search_hash']==result['search_hash']
    for patch in [{'lineshape':'gaussian'},{'steps_per_bin':4},{'tau_c_s':1e-10},{'target_refinement_error':.1},{'bound_fraction':.04}]:
        assert client.post('/research/search',json={'kind':'cest_memory','candidates':[patch]}).status_code==422
    for patch in [{'steps_per_bin':True},{'orientation_order':64},{'scanner_export':True}]:
        assert client.post('/research/run',json={'kind':'cest_memory','parameters':patch}).status_code==422
