import numpy as np
import pytest
from mrqlab_experiment.mrs_basis import (spin_hamiltonian, spin_operators,
    simulate_density_fid, fit_full_basis, run_mrs_basis, search_mrs_echo, _unitary)


def test_spin_commutators_unitarity_and_secular_doublet_analytic():
    ops=spin_operators(2)
    assert ops[0][0]@ops[0][1]-ops[0][1]@ops[0][0] == pytest.approx(1j*ops[0][2])
    h,ops=spin_hamiltonian([-100.,100.],[[0.,7.],[7.,0.]],coupling_model='secular')
    u=_unitary(h,.04)
    assert u.conj().T@u == pytest.approx(np.eye(4),abs=1e-13)
    # Independent exact weak-coupling FID after an ideal hard 90°.
    x=sum(a[0] for a in ops); y=sum(a[1] for a in ops); z=sum(a[2] for a in ops)
    rho=_unitary(x,np.pi/2)@(z/np.trace(z@z))@_unitary(x,np.pi/2).conj().T
    for t in [0.,.01,.04,.08]:
        u=_unitary(h,t); signal=np.trace((u@rho@u.conj().T)@(x+1j*y))
        expected=-.5j*(np.exp(-2j*np.pi*100*t)+np.exp(2j*np.pi*100*t))*np.cos(np.pi*7*t)
        assert signal == pytest.approx(expected,abs=1e-12)


def test_finite_rf_converges_and_has_off_resonance_bandwidth_effect():
    args=dict(offsets_hz=[-100.],couplings_hz=[[0.]],echo_s=.03)
    a,_=simulate_density_fid(**args,rf_steps=32)
    b,_=simulate_density_fid(**args,rf_steps=64)
    c,record=simulate_density_fid(**args,rf_steps=128)
    assert np.linalg.norm(c-b)<np.linalg.norm(b-a)/3
    short,_=simulate_density_fid(**args,rf_duration_s=.0002,rf_steps=128)
    assert np.linalg.norm(short-c)>1e-3
    assert record['hermiticity_error']<1e-12 and abs(record['trace_real'])<1e-12


def test_j_coupling_changes_fid_and_basis_mismatch_is_not_calibrated_away():
    matched=run_mrs_basis()
    mismatch=run_mrs_basis(basis_j_hz=0.)
    assert matched['validation']['passed']
    assert matched['fit']['amounts']==pytest.approx([.02,.015,.01,.008],abs=1e-12)
    assert not mismatch['validation']['passed']
    assert mismatch['validation']['max_relative_amount_error']>.1
    assert mismatch['fit']['relative_residual']>.02


def test_full_fit_recovers_shift_phase_noisy_amounts_and_replay():
    r=run_mrs_basis(noise_std=1e-5,phase_rad=.15,shift_hz=2.,
        fit_phase_grid_rad=[-.15,0.,.15],fit_shift_grid_hz=[-2.,0.,2.])
    assert r['validation']['passed']
    assert r['fit']['phase_rad']==.15 and r['fit']['shift_hz']==2.
    replay=run_mrs_basis(**r['provenance']['replay'])
    assert replay['provenance']==r['provenance']
    assert replay['fit']['amounts']==r['fit']['amounts']
    assert replay['signal']==pytest.approx(r['signal'])
    assert r['provenance']['estimated_work']<=100000000


def test_active_subset_fit_recovers_zero_and_rejects_duplicate_basis():
    t=np.arange(128)*.001; basis=np.array([np.exp(2j*np.pi*31*t),np.exp(2j*np.pi*77*t)]).T
    fit=fit_full_basis(2*basis[:,0],basis)
    assert fit['amounts']==pytest.approx([2.,0.],abs=1e-12)
    with pytest.raises(ValueError,match='rank'):
        fit_full_basis(basis[:,0],np.column_stack([basis[:,0],basis[:,0]]))


def test_finite_rf_spatial_response_and_echo_search_infeasibility():
    centered,_=simulate_density_fid([0.],[[0.]],position_m=[0.,0.,0.])
    outside,_=simulate_density_fid([0.],[[0.]],position_m=[.04,0.,0.])
    assert np.linalg.norm(outside)<.05*np.linalg.norm(centered)
    s=search_mrs_echo([.001,.02,.04],noise_std=1e-5)
    assert not s['candidates'][0]['feasible'] and s['best']
    assert search_mrs_echo([.001])['best'] is None


@pytest.mark.parametrize('patch',[dict(max_work=1),dict(points=True),dict(points=10000),
    dict(rf_steps=2),dict(dwell_s=.01),dict(echo_s=.001),dict(noise_std=-1.),
    dict(amounts=[1.,2.]),dict(target_relative_amount_error=0.),dict(seed=True)])
def test_invalid_spectroscopy_design_and_budgets(patch):
    with pytest.raises(ValueError): run_mrs_basis(**patch)
