import copy
import json
from hashlib import sha256

import numpy as np
import pytest
from fastapi.testclient import TestClient

from mrqlab_api.main import app
from mrqlab_api import scientific_records as records
from mrqlab_experiment.waveform_cartesian import run_waveform_cartesian
from mrqlab_experiment.linked_readout import validate_linked_edits, verify_linked_readout
from test_waveform_bloch import _expm_taylor


def parameters():
    gamma=42_577_478.92;fov=.22
    # 21 holds of 10 us accumulate 1/FOV cycles per meter.
    amplitude=1/(fov*gamma*1e-3*21*1e-5)
    gx=[0.]*130;gy=[0.]*130
    for start,sign in [(2,1),(35,-1),(65,1),(95,-1)]:
        gx[start:start+21]=[sign*amplitude]*21
    for start,sign in [(2,1),(65,-1)]:
        gy[start:start+21]=[sign*amplitude]*21
    blocks=[dict(id='rf',start_s=0.,rf=dict(samples_ut=[15.,15.,15.],phase_rad=[0.,0.,0.],raster_s=1e-5)),
            dict(id='encoding',start_s=.0002,gradients=[dict(axis='gx',samples_mt_m=gx,raster_s=1e-5),
                                                          dict(axis='gy',samples_mt_m=gy,raster_s=1e-5)])]
    for i,center in enumerate([.0005,.0008,.0011,.0014]):
        blocks.append(dict(id=f'adc{i}',start_s=center-1e-6,adc=dict(delay_s=0.,dwell_s=2e-6,sample_count=1)))
    return dict(waveform=dict(sequence=dict(id='cartesian',duration_s=.0016,blocks=blocks),
        labels=[[0,1],[1,0]],tissues=[dict(id='a',proton_density=1.,t1_s=1.,t2_s=.08),
                                      dict(id='b',proton_density=.6,t1_s=.7,t2_s=.03)],
        fov_m=fov,max_step_s=5e-7,max_work=100000),
        grid_indices=[[0,0],[0,1],[1,0],[1,1]],trajectory_tolerance_cycles_m=1e-7,
        image_target=dict(target_tissue_id='a',reference_tissue_id='b',operator='ge',value=.01))


def independent_signal(plan,sample,index):
    gamma=42_577_478.92; shape=(2,2); labels=plan['waveform']['labels']; fov=plan['waveform']['fov_m']
    ky,kx=index; total=0j; elapsed=sample['time_s']-30e-6
    for y,x in np.ndindex(shape):
        t=plan['waveform']['tissues'][labels[y][x]];w=2*np.pi*gamma*15e-6
        r1=1/t['t1_s'];r2=1/t['t2_s']
        generator=np.array([[-r2,0,0,0],[0,-r2,-w,0],[0,w,-r1,r1*t['proton_density']],[0,0,0,0.]])
        state=_expm_taylor(generator*30e-6)@np.array([0.,0.,t['proton_density'],1.])
        phase=-2j*np.pi*((ky-1)*(y-1)/2+(kx-1)*(x-1)/2)
        total+=(state[0]+1j*state[1])*np.exp(-elapsed/t['t2_s']+phase)
    return total


def test_cartesian_waveform_acquires_complex_samples_and_reconstructs_direct_dft():
    plan=parameters();out=run_waveform_cartesian(plan)
    samples=out['waveform']['samples']; indices=plan['grid_indices']
    assert [s['time_s'] for s in samples]==pytest.approx([.0005,.0008,.0011,.0014],abs=1e-15)
    assert out['encoding']['max_error_cycles_m'] < 1e-11
    expected_samples=np.array([independent_signal(plan,s,i) for s,i in zip(samples,indices)])
    actual=np.array([complex(s['real'],s['imag']) for s in samples])
    np.testing.assert_allclose(actual,expected_samples,atol=1e-9,rtol=0)
    # Independent direct inverse DFT, with no gain fitting.
    direct=np.array([sum(expected_samples[j]*np.exp(2j*np.pi*((ky-1)*(y-1)/2+(kx-1)*(x-1)/2))
                         for j,(ky,kx) in enumerate(indices))/4 for y,x in np.ndindex(2,2)])
    image=np.array(out['image']['real'])+1j*np.array(out['image']['imag'])
    np.testing.assert_allclose(image,direct,atol=1e-9,rtol=0)
    # Replacing all acquisition times by the first sample creates an ideal
    # simultaneous reference; the actual readout retains T2 modulation.
    static_samples=np.array([independent_signal(plan,{'time_s':samples[0]['time_s']},i) for i in indices])
    static=np.array([sum(static_samples[j]*np.exp(2j*np.pi*((ky-1)*(y-1)/2+(kx-1)*(x-1)/2))
                         for j,(ky,kx) in enumerate(indices))/4 for y,x in np.ndindex(2,2)])
    assert np.max(np.abs(image-static))>1e-5
    state=np.asarray(out['waveform']['final_magnetization']);final=state[:,0]+1j*state[:,1]
    assert np.max(np.abs(image-final))>1e-5
    assert out['validation']['passed'] is True
    assert out['validation']['image_target']['measured']>0
    assert verify_linked_readout(out['linked_readout'])['transform_passed']
    assert any(c['field']=='rf.samples.0.amplitude_ut' for c in out['linked_readout']['controls'])
    assert out['linked_readout']['signal_vector']['sample_times_s']==[s['time_s'] for s in samples]
    with pytest.raises(ValueError,match='unsupported or unbound control'):
        validate_linked_edits(out['linked_readout'],[dict(field='rf.amplitude',value=10.,view='image')])


def test_time_step_refinement_reduces_error_against_independent_signal():
    fine=parameters();coarse=copy.deepcopy(fine);coarse['waveform']['max_step_s']=1e-6
    results=[run_waveform_cartesian(p) for p in (coarse,fine)];errors=[]
    for plan,result in zip((coarse,fine),results):
        errors.append(max(abs(complex(s['real'],s['imag'])-independent_signal(plan,s,index))
                          for s,index in zip(result['waveform']['samples'],plan['grid_indices'])))
    assert errors[1] < errors[0]/4
    assert errors[1] < 1e-9


def test_wrong_trajectory_and_incomplete_or_duplicate_grid_are_rejected():
    plan=parameters();plan['grid_indices'][0],plan['grid_indices'][1]=plan['grid_indices'][1],plan['grid_indices'][0]
    with pytest.raises(ValueError,match='gradient moment differs'): run_waveform_cartesian(plan)
    plan=parameters();plan['grid_indices'][0]=plan['grid_indices'][1]
    with pytest.raises(ValueError,match='complete unique Cartesian'): run_waveform_cartesian(plan)
    plan=parameters();plan['waveform']['sequence']['blocks'].pop()
    with pytest.raises(ValueError,match='exactly one ADC'): run_waveform_cartesian(plan)


def test_no_gradient_during_rf_and_no_unbound_target():
    plan=parameters();plan['waveform']['sequence']['blocks'][1]['start_s']=0.
    with pytest.raises(ValueError,match='gradients before or during RF'): run_waveform_cartesian(plan)
    plan=parameters();plan['image_target']['reference_tissue_id']='missing'
    with pytest.raises(ValueError,match='declared target/reference'): run_waveform_cartesian(plan)
    plan=parameters();plan['image_target']=None
    assert run_waveform_cartesian(plan)['validation']['passed'] is False
    plan=parameters();plan['image_target']['value']=100.
    assert run_waveform_cartesian(plan)['validation']['passed'] is False
    plan=parameters();plan['waveform']['target']=dict(sample_index=0,metric='magnitude',operator='ge',value=100.)
    result=run_waveform_cartesian(plan)
    assert result['validation']['image_target']['passed'] is True
    assert result['validation']['signal_target']['passed'] is False
    assert result['validation']['passed'] is False


def test_scientific_record_api_image_signal_and_replay(tmp_path,monkeypatch):
    monkeypatch.setattr(records,'default_store_path',lambda:tmp_path/'records.sqlite3')
    plan=dict(context=dict(study_id='cartesian-waveform',research_question='How does sequential sampling alter tissue contrast?',
                           target_rationale='Evaluate an authored magnitude difference.'),
              execution=dict(type='waveform_cartesian',parameters=parameters()))
    response=TestClient(app).post('/research/records',json=plan)
    assert response.status_code==200,response.text
    body=response.json();record=body['record'];result=json.loads(record['payload_json'])['result']
    assert body['view']['images'][0]['values']==result['image']['magnitude']
    assert len(body['view']['curves'])==2 and record['summary']['model_reported_passed'] is True
    assert record['summary']['input_origins']==['authored_model_inputs','synthetic']
    assert records.replay_scientific_record(record)['computational_replay_performed']
    payload=json.loads(record['payload_json']);source=record['api_source_hash']
    missing=copy.deepcopy(payload);missing['result'].pop('linked_readout')
    missing['result_hash']=sha256(json.dumps(missing['result'],sort_keys=True,allow_nan=False).encode()).hexdigest()
    with pytest.raises(ValueError,match='requires the linked image/signal pair'):
        records._validate_run(missing,source)
    inconsistent=copy.deepcopy(payload);inconsistent['result']['image']['real'][0]+=1.
    inconsistent['result_hash']=sha256(json.dumps(inconsistent['result'],sort_keys=True,allow_nan=False).encode()).hexdigest()
    with pytest.raises(ValueError,match='differ from the linked pair'):
        records._validate_run(inconsistent,source)
