import base64
import copy
import hashlib
import numpy as np
import pytest
from mrqlab_experiment import flow_study as module
from mrqlab_experiment.flow_study import (
    FlowStudy, VelocityDataset, build_flow_study_example, import_velocity_csv,
    calibrate_pressure, run_flow_study,
)


def example(archive=True):
    study=build_flow_study_example().model_dump(mode='json')
    study['numerics']=dict(radial_rings=4,axial_spins=201,rf_steps=32)
    study['candidates']=[dict(inversion_time_s=.9)]
    if not archive:
        study['dataset'].pop('raw_csv_base64');study['dataset'].pop('raw_file_sha256')
    return study


def fit(study):
    spec=FlowStudy.model_validate(study)
    return calibrate_pressure(spec.dataset,spec.priors,spec.targets)


def test_raw_csv_exact_bytes_bom_and_si_headers():
    dataset=example()['dataset'];raw=b'\xef\xbb\xbf'+base64.b64decode(dataset['raw_csv_base64'])
    restored=import_velocity_csv(raw,source_ref='local:velocity.csv',origin='measured')
    assert restored.origin=='measured'
    assert base64.b64decode(restored.raw_csv_base64)==raw
    assert restored.raw_file_sha256==hashlib.sha256(raw).hexdigest()
    assert restored.measurements==VelocityDataset.model_validate(dataset).measurements
    with pytest.raises(ValueError,match='headers'):
        import_velocity_csv(raw.replace(b'time_s',b'time_ms'),source_ref='x',origin='synthetic')


@pytest.mark.parametrize('damage',['hash','rows','base64','missing_hash','duplicate_id','shared_acquisition','too_few_times'])
def test_measurement_archive_and_independence_rejected(damage):
    d=example()['dataset']
    if damage=='hash': d['raw_file_sha256']='0'*64
    elif damage=='rows': d['measurements'][0]['velocity_m_s']+=.001
    elif damage=='base64': d['raw_csv_base64']='!'
    elif damage=='missing_hash': d.pop('raw_file_sha256')
    elif damage=='duplicate_id': d['measurements'][1]['measurement_id']=d['measurements'][0]['measurement_id']
    elif damage=='shared_acquisition': d['measurements'][-1]['acquisition_id']=d['measurements'][0]['acquisition_id']
    else:
        for row in d['measurements']: row['time_s']=0.
    with pytest.raises(ValueError): VelocityDataset.model_validate(d)


def test_pressure_fit_known_sigma_covariance_and_phase_convention():
    s=example(False);r=fit(s)
    truth=np.array([100.,200*np.cos(.25),-200*np.sin(.25)])
    assert r['passed'] and r['rank']==3
    assert r['coefficients_pa_m']==pytest.approx(truth,abs=2e-12)
    # Independent Fisher information: inverse(A' W A), no residual scaling.
    spec=FlowStudy.model_validate(s);a=module.pressure_design(spec.priors,[x for x in spec.dataset.measurements if x.split=='calibration'])
    expected=np.linalg.inv(a.T@a/1e-6)
    assert np.array(r['covariance_pa2_m2'])==pytest.approx(expected,abs=1e-12)
    assert np.diag(expected)==pytest.approx([.98,5.5097084845,5.5097084845],rel=1e-10)
    assert r['calibration_reduced_chi2']<1e-20 and min(r['std_pa_m'])>.9
    for row in s['dataset']['measurements']: row['std_m_s']*=2
    doubled=fit(s)
    assert doubled['coefficients_pa_m']==pytest.approx(truth,abs=2e-12)
    assert np.array(doubled['covariance_pa2_m2'])==pytest.approx(4*expected,abs=1e-11)


def test_independent_finite_volume_velocity_recovers_pressure_without_bessel_reference():
    s=example(False);p=s['priors'];n=256;dr=p['radius_m']/n
    centers=(np.arange(n)+.5)*dr;faces=np.arange(n+1)*dr;nu=p['viscosity_pa_s']/p['density_kg_m3'];omega=2*np.pi*p['frequency_hz']
    lower=nu*faces[:-1]/(centers*dr**2);upper=nu*faces[1:]/(centers*dr**2);upper[-1]*=2
    laplacian=np.diag(-lower-upper)+np.diag(lower[1:],-1)+np.diag(upper[:-1],1)
    steady=np.linalg.solve(-laplacian,np.full(n,100/p['density_kg_m3']))
    harmonic=np.linalg.solve(1j*omega*np.eye(n)-laplacian,np.full(n,200*np.exp(.25j)/p['density_kg_m3']))
    for row in s['dataset']['measurements']:
        # Sample cell centers directly; no interpolation or analytic velocity.
        index=32 if row['measurement_id'].endswith('-0') else 160
        row['radius_m']=float(centers[index])
        row['velocity_m_s']=float(steady[index]+np.real(harmonic[index]*np.exp(1j*omega*row['time_s'])))
    r=fit(s)
    assert r['passed']
    assert r['coefficients_pa_m']==pytest.approx([100.,200*np.cos(.25),-200*np.sin(.25)],abs=.005)


def test_holdout_never_changes_coefficients_and_failure_applies_no_prior(monkeypatch):
    s=example(False);before=fit(s)
    for row in s['dataset']['measurements']:
        if row['split']=='holdout': row['velocity_m_s']+=.05
    after=fit(s)
    assert after['coefficients_pa_m']==before['coefficients_pa_m']
    assert after['covariance_pa2_m2']==before['covariance_pa2_m2']
    monkeypatch.setattr(module,'run_pulsatile_dir',lambda **kw:pytest.fail('failed holdout must not run MR'))
    result=run_flow_study(s)
    assert not result['validation']['calibration_and_holdout_passed']
    assert result['parameter_bindings']==[] and result['preview_simulation'] is None
    assert not any(p['executed'] for p in result['candidates'])


def test_unidentifiable_wall_samples_have_no_invented_pressure():
    s=example(False)
    for row in s['dataset']['measurements']: row.update(radius_m=s['priors']['radius_m'],velocity_m_s=0.)
    r=run_flow_study(s)
    assert not r['calibration']['passed'] and r['calibration']['coefficients_pa_m'] is None
    assert r['selected_index'] is None and not r['parameter_bindings']


@pytest.mark.parametrize('budget',[{'max_total_work':10000},{'max_memory_bytes':1}])
def test_complete_uncertainty_and_refinement_reserved_before_mr(monkeypatch,budget):
    s=example();s['budget'].update(budget)
    monkeypatch.setattr(module,'run_pulsatile_dir',lambda **kw:pytest.fail('no partial workflow before reservation'))
    r=run_flow_study(s)
    assert r['calibration']['passed'] and not r['validation']['complete_budget_reserved']
    assert r['preview_simulation'] is None and not r['candidates'][0]['scenarios']


def test_failed_attempts_are_conservatively_charged_not_faked_as_zero(monkeypatch):
    def failed(**kw): raise ValueError('infeasible receive coverage')
    monkeypatch.setattr(module,'run_pulsatile_dir',failed)
    s=example();r=run_flow_study(s)
    assert r['provenance']['estimated_work']==9*s['budget']['max_work_per_simulation']+r['calibration']['estimated_work']
    assert len(r['candidates'][0]['scenarios'])==9
    assert all(not c['completed'] for c in r['candidates'][0]['scenarios'])
    assert r['selected_index'] is None


def test_complete_corner_runs_retain_numerical_and_physical_failure_and_replay():
    s=example();r=run_flow_study(s);point=r['candidates'][0]
    assert r['calibration']['passed'] and point['executed'] and not point['eligible']
    assert len(point['scenarios'])==9 and all(c['completed'] for c in point['scenarios'])
    assert all('state_hash' in c['refined']['readouts'][0]['tissues']['blood'] for c in point['scenarios'])
    assert any(c['max_observation_refinement_error']>.01 for c in point['scenarios'])
    assert r['selected_index'] is None and r['preview_index']==0
    assert run_flow_study(s)==r


def test_mutated_model_cannot_bypass_archive_validation():
    s=FlowStudy.model_validate(example());s.dataset.measurements[0].velocity_m_s+=.01
    with pytest.raises(ValueError,match='archived CSV'): run_flow_study(s)
