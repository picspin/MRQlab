import numpy as np
import pytest
from mrqlab_physics.models import LiquidPoolSystem
from mrqlab_physics.ops.cest_saturation import apply_cw_bloch_mcconnell_saturation, _matrix_exp
from mrqlab_physics.ops.super_lorentzian import super_lorentzian_absorption_rate
from mrqlab_experiment.cest_mt_noe import (joint_pool_system, joint_generator,
    run_cest_mt_noe, search_cest_power)


def initial(system, fraction=.08):
    state = np.zeros(3*system.count+2); state[2:3*system.count:3] = system.density
    state[-2] = fraction; state[-1] = 1.
    return state


def test_joint_unsaturated_equilibrium_and_zero_mt_liquid_regression():
    system = joint_pool_system()
    state = initial(system)
    assert joint_generator(system, 0., 0.) @ state == pytest.approx(np.zeros_like(state), abs=1e-14)
    g = joint_generator(system, 447., 1., bound_fraction=0., bound_to_water_hz=0.)
    combined = _matrix_exp(g, .3) @ initial(system, 0.)
    epg = np.zeros((12, 1), complex); epg[2::3, 0] = system.density
    apply_cw_bloch_mcconnell_saturation(epg, .3, 447., 1., system)
    assert combined[2:12:3] == pytest.approx(epg[2::3, 0].real, abs=1e-12)


def test_joint_generator_matches_independent_explicit_ode_rk4():
    system = joint_pool_system(); duration = .004; hz = 150.; b1 = .5
    g = joint_generator(system, hz, b1)
    state = initial(system); expected = _matrix_exp(g, duration) @ state
    # Derivative written independently of joint_generator and matrix exponential.
    from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
    w1 = 2*np.pi*GAMMA_BAR_HZ_T*b1*1e-6
    rate = super_lorentzian_absorption_rate(b1, hz, 12e-6)
    def derivative(s):
        m = s[:12].reshape(4, 3); out = np.zeros_like(s)
        for i in range(4):
            x,y,z = m[i]; delta = 2*np.pi*(hz-system.offset_hz[i])
            out[3*i:3*i+3] = [-x/system.t2[i]+delta*y,
                -delta*x-y/system.t2[i]+w1*z,
                -w1*y+(system.density[i]-z)/system.t1[i]]
            for j in range(4):
                out[3*i:3*i+3] += system.rates[j][i]*m[j]-system.rates[i][j]*m[i]
        out[:3] -= .08*20*m[0]
        out[2] += 20*s[12]
        out[12] = (.08-s[12])+(.08*20*m[0,2]-20*s[12])-rate*s[12]
        return out
    dt = duration/2048
    for _ in range(2048):
        k1=derivative(state); k2=derivative(state+dt*k1/2)
        k3=derivative(state+dt*k2/2); k4=derivative(state+dt*k3)
        state += dt*(k1+2*k2+2*k3+k4)/6
    assert state == pytest.approx(expected, abs=2e-11)


def test_controls_disentangle_asymmetry_from_amide_and_replay():
    r = run_cest_mt_noe()
    m = r['metrics']
    assert m['amide_exchange_contrast'] > 0
    assert m['effective_noe_contrast'] > 0
    assert m['mt_contrast_at_amide'] > 0
    assert m['mtr_asym_3p5'] < 0 < m['amide_exchange_contrast']
    assert m['unsaturated_water'] == pytest.approx(1., abs=1e-11)
    assert r['validation']['passed']
    assert run_cest_mt_noe(**r['provenance']['replay']) == r


def test_liquid_pool_permutation_with_fixed_water_is_invariant():
    s = joint_pool_system(); order=[0,3,2,1]
    perm = LiquidPoolSystem(*(tuple(np.array(getattr(s,k))[order]) for k in ['t1','t2','density','offset_hz']),
        tuple(map(tuple, np.array(s.rates)[np.ix_(order,order)])))
    out = _matrix_exp(joint_generator(s, 447., 1.), .2) @ initial(s)
    swapped = _matrix_exp(joint_generator(perm, 447., 1.), .2) @ initial(perm)
    assert swapped[2] == pytest.approx(out[2], abs=1e-12)


def test_pulsed_train_gap_zero_equals_cw_and_positive_gap_changes_signal():
    args=dict(offsets_ppm=[-3.5,3.5], saturation_s=.2)
    cw = run_cest_mt_noe(**args)
    train = run_cest_mt_noe(**args, mode='pulsed', n_pulses=4, pulse_s=.05)
    for key in cw['spectra']:
        assert train['spectra'][key] == pytest.approx(cw['spectra'][key], abs=1e-11)
    gap = run_cest_mt_noe(offsets_ppm=[-3.5,3.5], saturation_s=.35,
        mode='pulsed', n_pulses=4, pulse_s=.05, gap_s=.05)
    assert gap['provenance']['duty_cycle'] == pytest.approx(.2/.35)
    assert not np.allclose(gap['spectra']['full'], train['spectra']['full'])


def test_gaussian_zero_offset_is_explicit_and_sl_zero_fails_closed():
    r = run_cest_mt_noe(offsets_ppm=[-3.5,0.,3.5], lineshape='gaussian')
    assert r['spectra']['full'][1] < .01
    with pytest.raises(ValueError, match='nonzero'):
        run_cest_mt_noe(offsets_ppm=[-3.5,0.,3.5])


def test_power_search_budget_and_failed_target_are_not_hidden():
    search = search_cest_power([.5,1.,2.], offsets_ppm=[-3.5,3.5], max_rf_energy_uT2_s=10.)
    assert search['best'] and not search['candidates'][-1]['feasible']
    assert search_cest_power([2.], offsets_ppm=[-3.5,3.5], max_rf_energy_uT2_s=1.)['best'] is None
    assert not run_cest_mt_noe(offsets_ppm=[-3.5,3.5], target_min_amide_contrast=.9)['validation']['passed']


@pytest.mark.parametrize('patch', [dict(offsets_ppm=[-3.5]), dict(offsets_ppm=[-3.5,3.5,3.5]),
    dict(b1_uT=0.), dict(b0_t=0.), dict(bound_fraction=-.1), dict(bound_t2_s=0.),
    dict(bound_to_water_hz=-1.), dict(lineshape='lorentzian'), dict(max_work=1),
    dict(max_duration_s=.1), dict(saturation_s=0.), dict(target_min_amide_contrast=0.),
    dict(mode='pulsed', n_pulses=True)])
def test_invalid_joint_design_and_budgets(patch):
    with pytest.raises(ValueError): run_cest_mt_noe(**patch)
