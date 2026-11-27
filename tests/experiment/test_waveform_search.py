import copy
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from mrqlab_api.main import app
from mrqlab_api import scientific_records as records
from mrqlab_experiment.waveform_search import search_waveform_bloch
from mrqlab_experiment.waveform_bloch import run_waveform_bloch
from test_waveform_bloch import parameters


def request():
    base=parameters();base['max_step_s']=.000001
    base['target']=dict(sample_index=0,metric='magnitude',operator='ge',value=.3)
    return dict(base=base,rf_block_id='rf',scales=[0.,.5,1.,2.],
                scenarios=[dict(id='nominal',b0_delta_hz=0.,b1_scale_factor=1.),
                           dict(id='shifted',b0_delta_hz=20.,b1_scale_factor=.8)],
                refinement_tolerance=1e-7,max_total_work=100000)


def test_grid_preserves_failed_candidates_and_minimum_energy_eligible():
    search=request();original=copy.deepcopy(search);result=search_waveform_bloch(search)
    assert search==original
    assert [p['scale'] for p in result['candidates']]==[0.,.5,1.,2.]
    assert [p['eligible'] for p in result['candidates']]==[False,False,True,True]
    assert result['selected_index']==2 and result['validation']['passed'] is True
    assert 'signal target failed' in result['candidates'][0]['reasons'][0]
    winner=result['candidates'][2]
    assert winner['rf_energy_proxy_ut2_s']==pytest.approx(3*15**2*1e-5)
    assert all(s['target_passed'] and s['refinement_passed'] for s in winner['scenarios'])
    assert all(s['refined']['work']['substeps_per_interval']==2*s['coarse']['work']['substeps_per_interval']
               and s['refined']['work']['voxel_steps']==2*s['coarse']['work']['voxel_steps'] for s in winner['scenarios'])
    actual=sum(s['coarse']['work']['voxel_steps']+s['refined']['work']['voxel_steps']
               for p in result['candidates'] for s in p['scenarios'])
    assert result['work']['total_voxel_steps']==actual
    assert search_waveform_bloch(search)==result


def test_no_passing_candidate_and_refinement_failure_have_no_fallback():
    search=request();search['base']['target']['value']=100.
    result=search_waveform_bloch(search)
    assert result['selected_index'] is None and result['validation']['passed'] is False
    assert all(not p['eligible'] for p in result['candidates'])
    search=request();search['refinement_tolerance']=0.
    result=search_waveform_bloch(search)
    assert not result['candidates'][2]['eligible']
    assert any('refinement tolerance failed' in reason for reason in result['candidates'][2]['reasons'])


def test_fine_only_target_pass_does_not_select_a_candidate():
    search=request();search['scales']=[1.];search['scenarios']=search['scenarios'][:1]
    search['base']['max_step_s']=2e-6
    coarse=run_waveform_bloch(search['base'])['samples'][0]['real']
    fine_parameters=copy.deepcopy(search['base']);fine_parameters['substeps_per_interval']=2
    fine=run_waveform_bloch(fine_parameters)['samples'][0]['real']
    assert coarse!=fine
    search['base']['target']=dict(sample_index=0,metric='real',operator='ge' if fine>coarse else 'le',value=(coarse+fine)/2)
    search['refinement_tolerance']=1.
    result=search_waveform_bloch(search);scenario=result['candidates'][0]['scenarios'][0]
    assert scenario['refined']['validation']['passed'] is True
    assert scenario['coarse']['validation']['passed'] is False
    assert scenario['target_passed'] is False and result['selected_index'] is None


def test_refinement_really_doubles_substeps_even_when_angular_bound_dominates():
    search=request();search['scales']=[1.];search['scenarios']=search['scenarios'][:1]
    search['base']['max_step_s']=1e-5
    scenario=search_waveform_bloch(search)['candidates'][0]['scenarios'][0]
    assert scenario['refined']['work']['voxel_steps']==2*scenario['coarse']['work']['voxel_steps']
    assert scenario['max_sample_difference']>0


def test_preflight_rejects_total_budget_without_integrating(monkeypatch):
    import mrqlab_experiment.waveform_search as module
    def forbidden(*args,**kwargs): raise AssertionError('integration started')
    monkeypatch.setattr(module,'run_waveform_bloch',forbidden)
    search=request();search['max_total_work']=1
    with pytest.raises(ValueError,match='no candidates were integrated'):
        module.search_waveform_bloch(search)


def test_invalid_candidates_are_retained_and_cannot_win():
    search=request();search['base']['sequence']['blocks'][0]['rf']['samples_ut']=[600.,600.,600.]
    search['scales']=[.001,2.]
    result=search_waveform_bloch(search)
    assert result['candidates'][1]['executable'] is False
    assert '1000 uT' in result['candidates'][1]['reasons'][0]
    assert result['selected_index'] is None


def test_search_requires_nominal_scenario_and_explicit_target():
    search=request();search['scenarios']=search['scenarios'][1:]
    with pytest.raises(ValueError,match='include the nominal'): search_waveform_bloch(search)
    search=request();search['base']['target']=None
    with pytest.raises(ValueError,match='explicit ADC point-signal target'): search_waveform_bloch(search)


def test_search_record_api_persists_all_candidates_and_replays(tmp_path,monkeypatch):
    monkeypatch.setattr(records,'default_store_path',lambda:tmp_path/'records.sqlite3')
    plan=dict(context=dict(study_id='rf-search',research_question='Which authored RF scale meets this point signal?',
                           target_rationale='Finite-grid teaching demonstration.'),
              execution=dict(type='waveform_search',parameters=request()))
    client=TestClient(app);response=client.post('/research/records',json=plan)
    assert response.status_code==200,response.text
    body=response.json();record=body['record'];result=json.loads(record['payload_json'])['result']
    assert record['summary']['candidate_count']==4
    assert record['summary']['selected_index']==2
    assert record['summary']['model_reported_passed'] is True
    assert len(result['candidates'][2]['scenarios'])==2
    assert records.replay_scientific_record(record)['computational_replay_performed']
    plan['execution']['parameters']['base']['target']['value']=100.
    failed=client.post('/research/records',json=plan)
    assert failed.status_code==200,failed.text
    assert failed.json()['record']['summary']['selected_index'] is None
    assert failed.json()['view']['curves']==[]
    assert failed.json()['view']['validation']['passed'] is False
