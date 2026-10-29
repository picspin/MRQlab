import importlib.util
import numpy as np
import pytest
from mrqlab_experiment.radial_tse import run_radial_tse
from mrqlab_experiment.tse_imaging import run_tse_imaging
from mrqlab_recon.spatial import radial_acquire


def phantom():
    y,x=np.indices((16,16))
    return (((x-8)**2+(y-8)**2<20)|((x==3)&(y>3))).astype(int)


@pytest.fixture(scope='module')
def matched():
    return run_radial_tse(phantom(),component_phase_rad=[.2,-.6])


def test_epg_echo_weights_match_cartesian_chassis_and_samples_are_not_mean_weighted(matched):
    r=matched;labels=phantom()
    cart=run_tse_imaging(labels)
    assert r['tissue_echo_weights']==pytest.approx(cart['tissue_echo_weights'],abs=1e-14)
    e=r['echo_for_sample'];w=r['tissue_echo_weights']
    independently=sum(radial_acquire((labels==i)*np.exp(1j*phase),96,32)[1]*w[i,e] for i,phase in enumerate([.2,-.6]))
    assert r['samples']==pytest.approx(independently,abs=1e-12)
    static=sum(radial_acquire((labels==i)*np.exp(1j*phase),96,32)[1]*w[i].mean() for i,phase in enumerate([.2,-.6]))
    assert np.linalg.norm(static-r['samples'])/np.linalg.norm(r['samples'])>.01


def test_unscaled_echo_and_component_recovery_replay_and_magnitude_roi_target(matched):
    r=matched;labels=phantom()
    assert r['validation']['passed'] and r['quality']['nrmse']<1e-6
    assert np.linalg.norm(r['reconstructed_components']-r['reference_components'])/np.linalg.norm(r['reference_components'])<1e-6
    assert abs(r['image'].imag).max()>.01
    expected=abs(r['tissue_echo_weights'][0,1]-r['tissue_echo_weights'][1,1])
    assert r['validation']['roi_contrast']==pytest.approx(expected,abs=1e-7)
    assert not r['static_control']['quality']['passed']
    repeated=run_radial_tse(**r['provenance']['replay'])
    assert np.array_equal(repeated['samples'],r['samples']) and np.array_equal(repeated['image'],r['image'])
    assert repeated['provenance']==r['provenance']


def test_timeline_assigns_one_spoke_per_echo_and_preserves_complex_temporal_svd(matched):
    r=matched;seen=[]
    for train in r['timeline']:
        assert len(train['spokes'])==4
        for rf,line in zip(train['refocusing_s'],train['spokes']):
            assert train['excitation_s']<rf<line['adc_start_s']<line['adc_end_s']<train['tr_end_s']
            assert line['samples']*line['dwell_s']==pytest.approx(.002)
            assert line['tissue_weights']==pytest.approx(r['tissue_echo_weights'][:,line['echo']-1])
            seen.append(line['spoke'])
    assert sorted(seen)==list(range(96))
    assert r['physical_to_basis'].T@r['temporal_basis']==pytest.approx(r['basis_echo_weights'],abs=1e-14)
    assert r['provenance']['estimated_work']<=20_000_000_000
    assert r['provenance']['estimated_peak_memory_bytes']<=134217728


def test_budget_exhaustion_and_mismatched_t2_are_scientific_failures():
    limited=run_radial_tse(phantom(),max_work=4_000_000_000)
    assert limited['solvers'][0]['stop_reason']=='max_work' and not limited['validation']['passed']
    assert limited['provenance']['estimated_work']<=4_000_000_000
    mismatch=run_radial_tse(phantom(),basis_t2_s=[.03,.12],inverse_max_iterations=300,control_iterations=20)
    assert not mismatch['validation']['passed'] and mismatch['validation']['coefficient_error']>.1


def test_stack_of_stars_recovers_echoes_but_fails_declared_rf_limit():
    p=phantom();r=run_radial_tse(np.stack([p,1-p]),max_work=50_000_000_000)
    assert r['quality']['passed'] and r['validation']['coefficient_error']<1e-6
    assert not r['validation']['passed'] and r['validation']['rf_energy_relative']==204.
    assert r['validation']['rf_energy_relative']>r['validation']['target_max_rf_energy']
    assert sorted((t['kz_index'],s['spoke']) for t in r['timeline'] for s in t['spokes'])==[(z,s) for z in range(2) for s in range(96)]


@pytest.mark.skipif(importlib.util.find_spec('finufft') is None,reason='optional FINUFFT')
def test_finufft_echo_aware_image_recovery_has_its_own_backend_and_budget():
    r=run_radial_tse(phantom(),backend='finufft',max_work=50_000_000_000)
    assert r['validation']['passed']
    assert r['solvers'][0]['operator']['fourier']['backend']=='finufft'
    assert r['provenance']['estimated_work']>20_000_000_000


@pytest.mark.parametrize('patch',[{'echoes':5},{'display_echo':True},{'max_work':True},
    {'max_samples':1},{'max_memory_bytes':1},{'max_duration_s':1.},
    {'basis_t2_s':[.04,.04]},{'tr_s':.02},{'nufft_eps':float('nan')},{'component_phase_rad':[0.]}])
def test_invalid_design_and_rank_fail_closed(patch):
    with pytest.raises(ValueError): run_radial_tse(phantom(),**patch)
