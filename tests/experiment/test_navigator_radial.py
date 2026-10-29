import numpy as np
import pytest
from mrqlab_experiment.navigator_radial import estimate_tse_navigator,run_navigator_radial_tse
from mrqlab_experiment.lab_study import build_lab_study_example
from mrqlab_recon.spatial import radial_coordinates

BOUNDS=[[.03973685083017578,.040263149169824236],[.11867600979567682,.1213239902043232]]


def navigator_data(t2=(.0399,.1207),amplitudes=(190*np.exp(.3j),66*np.exp(-.2j))):
    # Independent analytic ideal-180 mixture, not the production EPG generator.
    times=np.arange(1,7)*.008
    signal=np.exp(-times[:,None]/np.asarray(t2))@np.asarray(amplitudes)
    ids=np.tile(np.arange(6),8)
    return np.zeros((len(ids),2)),signal[ids][None,:],ids


def infer(xy,data,ids,**kwargs):
    return estimate_tse_navigator(xy,data,ids,echoes=6,echo_spacing_s=.008,tr_s=.4,t2_bounds_s=BOUNDS,**kwargs)


def test_data_only_complex_mixture_recovers_global_t2_without_truth_or_labels():
    xy,data,ids=navigator_data();fit=infer(xy,data,ids)
    assert fit['passed'] and fit['t2_s']==pytest.approx([.0399,.1207],rel=1e-7)
    assert fit['fit_echoes']==[1,2,3,4] and fit['withheld_echoes']==[5,6]
    assert fit['relative_holdout_residual']<1e-10
    assert fit['locally_identifiable'] and fit['estimated_work']<=20000000
    # Changing overall complex DC amplitudes does not change the inferred poles.
    _,scaled,_=navigator_data(amplitudes=(12*np.exp(-.4j),37*np.exp(1.1j)))
    other=infer(xy,scaled,ids)
    assert other['passed'] and other['t2_s']==pytest.approx(fit['t2_s'],rel=1e-7)


def test_withheld_echoes_never_enter_fit_and_detect_wrong_model():
    xy,data,ids=navigator_data();control=infer(xy,data,ids)
    bad=data.copy();bad[:,ids>=4]*=1.001
    fit=infer(xy,bad,ids)
    assert fit['t2_s']==control['t2_s']
    assert not fit['passed'] and fit['relative_fit_residual']<1e-10 and fit['relative_holdout_residual']>1e-4
    assert any('withheld' in reason for reason in fit['reasons'])


def test_repeat_inconsistency_and_noise_are_not_reported_as_exact_validity():
    xy,data,ids=navigator_data();bad=data.copy();bad[0,0]+=.001
    fit=infer(xy,bad,ids)
    assert not fit['passed'] and fit['empirical_sample_std']>0
    assert any('repeats' in reason for reason in fit['reasons'])
    noisy=infer(xy,data,ids,declared_sample_std=.1)
    assert not noisy['passed'] and any('uncertainty' in reason for reason in noisy['reasons'])


def test_single_present_component_is_not_two_identifiable_t2_values():
    xy,data,ids=navigator_data(t2=(.04,.12),amplitudes=(1.,0.))
    fit=infer(xy,data,ids)
    assert not fit['passed'] and not fit['locally_identifiable']


def test_exact_center_required_not_nearest_sample_or_even_trajectory():
    xy,data,ids=navigator_data()
    with pytest.raises(ValueError,match='exact k=0'): infer(xy+1e-16,data,ids)
    coords=radial_coordinates((16,16),144,32)
    assert not np.any(np.all(coords==0,axis=1))
    with pytest.raises(ValueError,match='exact k=0'):
        infer(coords,np.ones((1,len(coords)),complex),np.repeat(np.arange(144)%6,32))


@pytest.mark.parametrize('patch',[{'t2_bounds_s':[[.04,.13],[.12,.2]]}, {'fit_echoes':5},
    {'max_evaluations':True},{'declared_sample_std':-1.}])
def test_strict_navigation_bounds_and_holdout_inputs(patch):
    xy,data,ids=navigator_data()
    request=dict(echoes=6,echo_spacing_s=.008,tr_s=.4,t2_bounds_s=BOUNDS,**{})
    request.update(patch)
    with pytest.raises(ValueError): estimate_tse_navigator(xy,data,ids,**request)


def test_exhausted_evaluation_allowance_is_failed_and_charged():
    xy,data,ids=navigator_data();fit=infer(xy,data,ids,max_evaluations=8)
    assert not fit['passed'] and fit['estimated_work']==20000000
    assert any('allowance exhausted' in reason for reason in fit['reasons'])


@pytest.fixture(scope='module')
def navigated():
    sample=build_lab_study_example()
    return run_navigator_radial_tse(sample.labels,t2_bounds_s=BOUNDS,echoes=6,spokes=144,points=33,
        t2_s=[BOUNDS[0][0],BOUNDS[1][0]],basis_t2_s=[.04,.12],experiment=sample.experiment,
        max_work=50000000000,component_phase_rad=[.3,-.2])


def test_spatial_inverse_uses_same_complex_raw_samples_and_keeps_strict_targets(navigated):
    r=navigated
    assert r['navigator_fit']['passed'] and r['navigator_reconstruction_performed']
    assert r['validation']['passed'] and r['quality']['nrmse']<1e-6
    assert r['validation']['coefficient_error']<1e-6
    assert not r['fixed_prior_control']['validation']['passed']
    assert r['fixed_prior_control']['validation']['coefficient_error']>.01
    assert r['navigator_fit']['t2_s']==pytest.approx([BOUNDS[0][0],BOUNDS[1][0]],rel=1e-7)
    assert not r['solvers'][0]['gain_fit'] and r['solvers'][0]['operator']['spatial_support']=='not supplied'
    assert r['provenance']['estimated_work']<=50000000000
    assert r['provenance']['estimated_peak_memory_bytes']<=134217728
    assert r['design']['points']==33 and len(r['navigator_fit']['center_indices'])==144


def test_navigator_input_has_no_access_to_spatial_truth(navigated):
    r=navigated
    # Re-estimate solely from the serialized acquisition; altered sample labels,
    # reference maps and true T2 are not arguments of the inference function.
    fit=infer(r['coordinates'],r['samples'],r['echo_for_sample'])
    assert fit['passed'] and fit['t2_s']==pytest.approx(r['navigator_fit']['t2_s'],rel=1e-7)


def test_unsupported_navigation_design_rejected_before_acquisition(monkeypatch):
    import mrqlab_experiment.navigator_radial as module
    monkeypatch.setattr(module,'run_radial_tse',lambda *a,**kw:pytest.fail('must reject before acquisition'))
    with pytest.raises(ValueError,match='odd-point'): run_navigator_radial_tse([],t2_bounds_s=BOUNDS,echoes=6,points=32)
    with pytest.raises(ValueError,match='>=6'): run_navigator_radial_tse([],t2_bounds_s=BOUNDS,echoes=4,points=33)
