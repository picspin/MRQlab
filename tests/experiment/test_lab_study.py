import copy
import csv
import io
import json
import os
import subprocess
import sys
import numpy as np
import pytest
from mrqlab_experiment.family_recipes import build_family_recipe
from mrqlab_experiment.lab_study import (EchoDataset,LabStudy,StudyTargets,calibrate_t2,
    StudyBudget,build_lab_study_example,import_echo_csv,run_lab_study,fingerprint)
from mrqlab_experiment.study_records import (create_study_record,replay_study_record,
    verify_study_record,save_study_record)


@pytest.fixture
def spec():
    graph=build_family_recipe('brain_t1_3d_tse'); rows=[]
    for tissue,t2 in zip(graph.tissue,[.04,.12]):
        for split,indices in [('calibration',[1,3,5,7]),('holdout',[2,4,6,8])]:
            for i in indices:
                rows.append(dict(measurement_id=f'{tissue.id}-{i}',acquisition_id=split,tissue_id=tissue.id,split=split,
                    echo_time_s=i*.008,signal_a_u=float(.4*np.exp(-i*.008/t2)),std_a_u=.0005))
    y,x=np.indices((16,16)); labels=(((x-8)**2+(y-8)**2)<20).astype(int)
    return dict(experiment=graph.model_dump(mode='json'),
        dataset=dict(source_ref='synthetic:analytic-cpmg-v1',origin='synthetic',measurements=rows),
        tissue_order=[t.id for t in graph.tissue],labels=labels.tolist(),candidates=[{'echoes':2},{'echoes':4},{'echoes':8}])


def test_analytic_calibration_independent_holdout_and_graph_nonmutation(spec):
    before=copy.deepcopy(spec); result=run_lab_study(spec)
    assert spec==before
    assert [f['t2_s'] for f in result['calibration']]==pytest.approx([.04,.12],abs=1e-10)
    assert all(f['t2_std_s']>0 and f['passed'] for f in result['calibration'])
    assert result['validation']==dict(calibration_and_holdout_passed=True,complete_budgeted_search=True,selected_design_passed=True)
    assert result['selected_index']==0
    assert result['calibrated_experiment']['tissue'][0]['t2']==pytest.approx(.04)
    assert result['original_experiment']['tissue'][0]['t2']==.08
    assert result['selected_simulation']['design']['tissue'][0]['proton_density']==.8
    assert all(len(p['scenarios'])==5 for p in result['candidates'])
    assert result['provenance']['estimated_work']<=result['provenance']['reserved_work']<=1000000000
    assert [s['id'] for s in result['provenance']['stages']]==['measurements','calibration','independent_holdout_validation','calibrated_experiment','design_search','target_validation']


def test_holdout_cannot_change_calibration_or_sneak_into_selected_design(spec):
    good=run_lab_study(spec)
    for row in spec['dataset']['measurements']:
        if row['split']=='holdout': row['signal_a_u']+=.1
    bad=run_lab_study(spec)
    assert [f['t2_s'] for f in good['calibration']]==[f['t2_s'] for f in bad['calibration']]
    assert good['provenance']['stages'][1]['output_sha256']==bad['provenance']['stages'][1]['output_sha256']
    assert good['provenance']['stages'][2]['output_sha256']!=bad['provenance']['stages'][2]['output_sha256']
    assert not bad['validation']['calibration_and_holdout_passed']
    assert bad['selected_index'] is None and bad['selected_simulation'] is None
    assert all(not p['executed'] for p in bad['candidates'])


def test_measured_t2_changes_physical_design_outcomes(spec):
    slow=run_lab_study(spec)
    for row in spec['dataset']['measurements']:
        if row['tissue_id']=='white_matter': row['signal_a_u']=float(.4*np.exp(-row['echo_time_s']/.02))
    fast=run_lab_study(spec)
    assert fast['calibration'][0]['t2_s']==pytest.approx(.02)
    assert fast['candidates'][0]['worst_psf_rms_voxels']>slow['candidates'][0]['worst_psf_rms_voxels']
    assert fast['candidates'][0]['scenarios'][0]['roi_image_contrast']!=slow['candidates'][0]['scenarios'][0]['roi_image_contrast']
    assert slow['selected_index'] is not None and fast['selected_index'] is None


def test_known_sigma_controls_uncertainty_without_residual_rescaling(spec):
    a=EchoDataset.model_validate(spec['dataset']); b=copy.deepcopy(a)
    for row in b.measurements: row.std_a_u*=2
    fit=calibrate_t2(a,'white_matter',[.005,2.],StudyTargets())
    doubled=calibrate_t2(b,'white_matter',[.005,2.],StudyTargets())
    assert doubled['t2_s']==pytest.approx(fit['t2_s'],abs=1e-10)
    assert doubled['t2_std_s']==pytest.approx(2*fit['t2_std_s'],rel=1e-7)


def test_uncertainty_corners_can_reject_nominally_passing_design(spec):
    baseline=run_lab_study(spec); nominal=baseline['candidates'][0]['scenarios'][0]['max_psf_rms_voxels']
    worst=baseline['candidates'][0]['worst_psf_rms_voxels']
    spec['targets']={'max_psf_rms_voxels':float((nominal+worst)/2)}
    result=run_lab_study(spec)
    assert result['candidates'][0]['scenarios'][0]['passed']
    assert not result['candidates'][0]['eligible']
    assert result['selected_index'] is None


def test_budgets_and_failed_targets_do_not_select_partial_grid(spec):
    spec['budget']={'max_total_work':15000000,'max_work_per_simulation':10000000}
    result=run_lab_study(spec)
    assert not result['validation']['complete_budgeted_search'] and result['selected_index'] is None
    spec.pop('budget'); spec['targets']={'min_roi_image_contrast':1.}
    result=run_lab_study(spec)
    assert result['validation']['calibration_and_holdout_passed'] and result['selected_index'] is None
    assert all(not p['eligible'] for p in result['candidates'])

    example=build_lab_study_example()
    example.budget=StudyBudget(max_total_work=1000000000,max_work_per_simulation=20000)
    result=run_lab_study(example)
    assert len(result['candidates'])==3
    assert all(not p['scenarios'] for p in result['candidates'])
    assert not result['validation']['complete_budgeted_search']

    example.budget=StudyBudget(max_total_work=70000,max_work_per_simulation=30000)
    result=run_lab_study(example)
    assert any(p['scenarios'] for p in result['candidates'])
    assert any(p['scenarios'] and not p['executed'] for p in result['candidates'])
    assert not result['validation']['complete_budgeted_search']
    assert result['selected_index'] is None


def test_csv_exact_units_byte_hash_and_independent_acquisitions(spec):
    rows=spec['dataset']['measurements']; output=io.StringIO()
    writer=csv.DictWriter(output,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    raw=output.getvalue().encode(); dataset=import_echo_csv(raw,source_ref='test.csv',origin='synthetic')
    assert dataset.raw_file_sha256 and dataset.measurements[0].echo_time_s==.008
    with pytest.raises(ValueError): import_echo_csv(raw.replace(b'echo_time_s',b'echo_time_ms'),source_ref='test.csv',origin='synthetic')
    with pytest.raises(ValueError): import_echo_csv(raw+b'bad,row\n',source_ref='test.csv',origin='synthetic')
    spec['dataset']['measurements'][0]['acquisition_id']='holdout'
    with pytest.raises(ValueError,match='disjoint'): LabStudy.model_validate(spec)


def test_record_integrity_computational_replay_and_atomic_no_overwrite(spec,tmp_path):
    record=create_study_record(spec)
    assert verify_study_record(record)['integrity_passed']
    replay=replay_study_record(record)
    assert replay==record
    path=save_study_record(record,tmp_path/'study.json')
    assert json.loads(path.read_text())==record
    with pytest.raises(FileExistsError): save_study_record(record,path)
    assert not list(tmp_path.glob('.mrqlab-study-*'))
    tampered=copy.deepcopy(record);tampered['request']['candidates'][0]['echoes']=8
    with pytest.raises(ValueError,match='integrity'): verify_study_record(tampered)
    with pytest.raises(ValueError): save_study_record(tampered,tmp_path/'bad.json')
    assert not (tmp_path/'bad.json').exists()


def test_replay_pins_source_runtime_and_process_loaded_code(spec,monkeypatch):
    import mrqlab_experiment.study_records as module
    record=create_study_record(spec)
    altered=copy.deepcopy(record); altered['runtime']['python']='0.0.0'
    altered['record_sha256']=fingerprint({k:v for k,v in altered.items() if k!='record_sha256'})
    with pytest.raises(ValueError,match='runtime'): replay_study_record(altered)
    monkeypatch.setattr(module,'source_manifest',lambda: {'files':{},'sha256':'0'*64})
    with pytest.raises(ValueError,match='source changed'): replay_study_record(record)


def test_real_cli_save_verify_and_replay(spec,tmp_path):
    source=tmp_path/'input.json'; source.write_text(json.dumps(spec))
    output=tmp_path/'record.json'; replay=tmp_path/'replayed.json'
    env={**os.environ,'PYTHONPATH':os.pathsep.join(sys.path)}
    base=[sys.executable,'-m','mrqlab_experiment.study_records']
    run=subprocess.run([*base,'run',str(source),'--output',str(output)],env=env,capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    verify=subprocess.run([*base,'verify',str(output)],env=env,capture_output=True,text=True)
    assert verify.returncode==0 and 'integrity only' in verify.stdout
    again=subprocess.run([*base,'replay',str(output),'--output',str(replay)],env=env,capture_output=True,text=True)
    assert again.returncode==0,again.stderr
    assert json.loads(output.read_text())==json.loads(replay.read_text())


@pytest.mark.parametrize('patch',[{'t2_bounds_s':[1e-9,2.]},{'tissue_order':['white_matter','unknown']},
    {'labels':[[0,1],[0]]},{'budget':{'max_total_work':1}},{'candidates':[{'echoes':True}]}])
def test_invalid_study_and_calibration_budget_fail(spec,patch):
    spec.update(patch)
    with pytest.raises(ValueError): run_lab_study(spec)



def test_linearized_known_noise_uncertainty_agrees_with_independent_repeated_data(spec):
    dataset=EchoDataset.model_validate(spec['dataset']); rng=np.random.default_rng(91)
    estimates=[]; uncertainties=[]
    for _ in range(120):
        sample=dataset.model_copy(deep=True)
        for row in sample.measurements:
            if row.split=='calibration': row.signal_a_u+=float(rng.normal(0,row.std_a_u))
        fit=calibrate_t2(sample,'white_matter',[.005,2.],StudyTargets())
        estimates.append(fit['t2_s']);uncertainties.append(fit['t2_std_s'])
    assert abs(np.mean(estimates)-.04)<np.mean(uncertainties)*.3
    assert .75<np.std(estimates,ddof=1)/np.mean(uncertainties)<1.25


def test_cli_imports_original_csv_bytes_and_preserves_failed_validation(spec,tmp_path):
    text=io.StringIO(); rows=spec['dataset']['measurements']
    writer=csv.DictWriter(text,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    raw=b'\xef\xbb\xbf'+text.getvalue().encode(); source_csv=tmp_path/'echoes.csv'; source_csv.write_bytes(raw)
    source=tmp_path/'input.json'; source.write_text(json.dumps(spec)); output=tmp_path/'record.json'
    env={**os.environ,'PYTHONPATH':os.pathsep.join(sys.path)}
    result=subprocess.run([sys.executable,'-m','mrqlab_experiment.study_records','run',str(source),
        '--measurements-csv',str(source_csv),'--output',str(output)],env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    import hashlib
    record=json.loads(output.read_text())
    assert record['request']['dataset']['raw_file_sha256']==hashlib.sha256(raw).hexdigest()


def test_tse_chassis_reuses_authored_priors_and_rejects_unwired_models(spec):
    from mrqlab_experiment.tse_imaging import run_tse_imaging
    graph=copy.deepcopy(spec['experiment']); original=copy.deepcopy(graph)
    base=run_tse_imaging(spec['labels'],t2_s=[.04,.12],experiment=graph)
    assert graph==original
    graph['tissue'][0]['proton_density']=.4
    assert base['provenance']['replay']['experiment']['tissue'][0]['proton_density']==.8
    replay=run_tse_imaging(**base['provenance']['replay'])
    assert replay['image']==pytest.approx(base['image'])
    changed=run_tse_imaging(spec['labels'],t2_s=[.04,.12],experiment=graph)
    assert changed['tissue_echo_weights'][0]==pytest.approx(.5*np.array(base['tissue_echo_weights'][0]),abs=1e-10)
    assert changed['psf_prediction_quality']['passed']
    graph['tissue'][0]['flow_velocity_mps']=.02
    with pytest.raises(ValueError,match='independent relaxation'): run_tse_imaging(spec['labels'],experiment=graph)



def test_record_survives_real_javascript_json_parse_stringify(spec):
    import shutil
    node=shutil.which('node')
    if node is None: pytest.skip('cross-language JSON transport test requires frontend Node runtime')
    record=create_study_record(spec)
    process=subprocess.run([node,'-e','let s="";process.stdin.on("data",x=>s+=x);process.stdin.on("end",()=>process.stdout.write(JSON.stringify(JSON.parse(s))));'],
        input=json.dumps(record),capture_output=True,text=True,check=True)
    transported=json.loads(process.stdout)
    assert replay_study_record(transported)==record
    assert fingerprint({'value':1.,'zero':-0.})==fingerprint({'zero':0,'value':1})
    assert fingerprint(True)!=fingerprint(1)
    assert fingerprint(1)!=fingerprint('0x1.0000000000000p+0')
    assert fingerprint(['number','0x1.0000000000000p+0'])!=fingerprint(1)
    with pytest.raises(ValueError): fingerprint(float('nan'))



def test_record_runtime_snapshot_does_not_alias_numpy_configuration(spec,monkeypatch):
    import mrqlab_experiment.study_records as module
    monkeypatch.setattr(np.__config__,'CONFIG',{'nested':{'value':1}})
    record=create_study_record(spec)
    record['runtime']['blas_configuration']['nested']['value']=2
    assert module.runtime_manifest()['blas_configuration']['nested']['value']==1
