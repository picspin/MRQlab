import copy
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from mrqlab_api.main import app
from mrqlab_api import scientific_records as records
from mrqlab_experiment.waveform_bloch import run_waveform_bloch


def parameters():
    return dict(sequence=dict(id='finite-rf-readout',duration_s=.0003,blocks=[
        dict(id='rf',start_s=0.,rf=dict(samples_ut=[15.,15.,15.],phase_rad=[.3,.3,.3],raster_s=.00001),
             gradients=[dict(axis='gx',samples_mt_m=[0.,1.,0.],raster_s=.00001)]),
        dict(id='readout',start_s=.00019,gradients=[dict(axis='gx',samples_mt_m=[0.,1.,0.],raster_s=.00001)]),
        dict(id='adc',start_s=.0002,adc=dict(delay_s=0.,dwell_s=.00001,sample_count=2)),
    ]),labels=[[0,1],[1,0]],tissues=[
        dict(id='a',proton_density=1.,t1_s=1.,t2_s=.1,b0_hz=17.,b1_scale=.9),
        dict(id='b',proton_density=.8,t1_s=.7,t2_s=.06,b0_hz=-22.,b1_scale=1.1)],
        fov_m=.22,z_m=0.,max_step_s=.0000002,max_work=100000)


def _expm_taylor(matrix):
    """Independent scaling-and-squaring Taylor exponential, no RK4 steps."""
    scaled=matrix/16
    total=np.eye(4);term=np.eye(4)
    for j in range(1,60):
        term=term@scaled/j;total+=term
    for _ in range(4): total=total@total
    return total


def _reference_sample(plan, stop):
    gamma=42_577_478.92; xy=[(-.11,-.11),(0.,-.11),(-.11,0.),(0.,0.)]
    labels=np.asarray(plan['labels']).ravel(); total=0j
    # Independent manually enumerated RF/gradient intervals for this fixture.
    intervals=[(0,10e-6,15.,0.),(10e-6,20e-6,15.,1.),(20e-6,30e-6,15.,0.),
               (30e-6,200e-6,0.,0.),(200e-6,210e-6,0.,1.),(210e-6,300e-6,0.,0.)]
    for index,(x,_) in enumerate(xy):
        t=plan['tissues'][labels[index]];state=np.array([0.,0.,t['proton_density'],1.])
        for start,end,rf,g in intervals:
            duration=max(0.,min(stop,end)-start)
            if duration<=0: continue
            w=2*np.pi*gamma*rf*1e-6*t['b1_scale'];wx=w*np.cos(.3);wy=w*np.sin(.3)
            wz=2*np.pi*(t['b0_hz']+gamma*g*1e-3*x)
            r1=1/t['t1_s'];r2=1/t['t2_s']
            matrix=np.array([[-r2,-wz,wy,0.],[wz,-r2,-wx,0.],[-wy,wx,-r1,r1*t['proton_density']],[0.,0.,0.,0.]])
            state=_expm_taylor(matrix*duration)@state
        total+=state[0]+1j*state[1]
    return total


def test_sampled_rf_gradient_and_adc_match_independent_affine_exponential():
    plan=parameters();result=run_waveform_bloch(plan);samples=result['samples']
    assert [s['time_s'] for s in samples]==[.000205,.000215]
    for sample in samples:
        expected=_reference_sample(plan,sample['time_s'])
        assert complex(sample['real'],sample['imag'])==pytest.approx(expected,abs=2e-11)
    gamma=42_577_478.92
    assert samples[0]['k_cycles_m'][0]==pytest.approx(gamma*1e-3*15e-6,abs=1e-14)
    assert samples[1]['k_cycles_m'][0]==pytest.approx(gamma*1e-3*20e-6,abs=1e-14)
    assert result['validation']['passed'] is False
    assert 'point_adc' in result['model']


def test_refinement_and_budget_are_explicit_and_deterministic():
    plan=parameters();coarse=copy.deepcopy(plan);coarse['max_step_s']=.000001
    fine=copy.deepcopy(plan)
    a=run_waveform_bloch(coarse);b=run_waveform_bloch(fine)
    np.testing.assert_allclose([[s['real'],s['imag']] for s in a['samples']],
                               [[s['real'],s['imag']] for s in b['samples']],atol=2e-9,rtol=0)
    assert run_waveform_bloch(plan)==run_waveform_bloch(plan)
    plan['max_work']=1
    with pytest.raises(ValueError,match='complete waveform work.*no time steps were coarsened'):
        run_waveform_bloch(plan)


def test_unsupported_offsets_and_boolean_labels_fail_closed():
    plan=parameters();plan['sequence']['blocks'][0]['rf']['carrier_offset_hz']=10.
    with pytest.raises(ValueError,match='RF carrier offset'):
        run_waveform_bloch(plan)
    plan=parameters();plan['sequence']['blocks'][2]['adc']['frequency_offset_hz']=10.
    with pytest.raises(ValueError,match='ADC receiver frequency offset'):
        run_waveform_bloch(plan)
    plan=parameters();plan['labels'][0][0]=True
    with pytest.raises(ValueError): run_waveform_bloch(plan)
    plan=parameters();plan['sequence']['blocks'][0]['rf']['samples_ut'][0]=True
    with pytest.raises(ValueError,match='boolean values'):
        run_waveform_bloch(plan)
    plan=parameters();plan['sequence']['blocks'][0]['rf']['samples_ut'][0]=1e308
    with pytest.raises(ValueError,match='bounded 1000 uT research input domain'):
        run_waveform_bloch(plan)


def test_receiver_phase_rotates_each_complex_sample_without_changing_spin_or_trajectory():
    base=parameters(); shifted=copy.deepcopy(base)
    shifted['sequence']['blocks'][2]['adc']['phase_offset_rad']=np.pi/2
    reference=run_waveform_bloch(base); result=run_waveform_bloch(shifted)
    for original,observed in zip(reference['samples'],result['samples']):
        expected=complex(original['imag'],-original['real'])
        assert complex(observed['real'],observed['imag'])==pytest.approx(expected,abs=1e-13)
        assert observed['k_cycles_m']==original['k_cycles_m'] and observed['time_s']==original['time_s']
    assert result['final_magnetization']==reference['final_magnetization']
    assert result['work']==reference['work']
    shifted['target']=dict(sample_index=0,metric='real',operator='ge',value=0.)
    assert run_waveform_bloch(shifted)['validation']['measured']==pytest.approx(reference['samples'][0]['imag'],abs=1e-13)
    shifted['sequence']['blocks'][2]['adc']['phase_offset_rad']=1e7
    with pytest.raises(ValueError,match='ADC receiver phase exceeds'):
        run_waveform_bloch(shifted)


def test_signal_target_reports_success_failure_and_invalid_index():
    plan=parameters();plan['target']=dict(sample_index=0,metric='magnitude',operator='ge',value=.4)
    result=run_waveform_bloch(plan)
    assert result['validation']['passed'] is True
    assert result['validation']['measured']==pytest.approx(abs(_reference_sample(plan,.000205)),abs=2e-11)
    plan['target']['value']=1.
    assert run_waveform_bloch(plan)['validation']['passed'] is False
    plan['target']['sample_index']=2
    with pytest.raises(ValueError,match='outside the complete ADC'):
        run_waveform_bloch(plan)


def test_scientific_record_api_and_full_replay(tmp_path,monkeypatch):
    monkeypatch.setattr(records,'default_store_path',lambda:tmp_path/'records.sqlite3')
    plan=dict(context=dict(study_id='waveform-demo',research_question='How do RF and readout evolve synthetic tissue?',
                           target_rationale='Verify complex point ADC against declared waveform.'),
              execution=dict(type='waveform_bloch',parameters=parameters()))
    plan['execution']['parameters']['sequence']['blocks'][2]['adc']['phase_offset_rad']=.7
    client=TestClient(app);response=client.post('/research/records',json=plan)
    assert response.status_code==200,response.text
    body=response.json();record=body['record'];payload=json.loads(record['payload_json'])
    assert payload['result']['sample_count']==2
    assert body['view']['validation']['passed'] is False
    assert record['summary']['input_origins']==['authored_model_inputs','synthetic']
    assert records.replay_scientific_record(record)['computational_replay_performed']
    response=client.post('/research/records/'+record['record_sha256']+'/replay')
    assert response.status_code==200 and response.json()['computational_replay_performed']
    plan['execution']['parameters']['target']=dict(sample_index=0,metric='magnitude',operator='ge',value=.4)
    passed=client.post('/research/records',json=plan)
    assert passed.status_code==200,passed.text
    assert passed.json()['record']['summary']['model_reported_passed'] is True
    assert records.replay_scientific_record(passed.json()['record'])['computational_replay_performed']
