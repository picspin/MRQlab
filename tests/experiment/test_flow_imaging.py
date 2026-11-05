import numpy as np
import pytest
from mrqlab_experiment.flow_imaging import (MovingBlochEnsemble, selective_sinc,
    plan_gated_readouts, run_flow_imaging, search_flow_timing, GAMMA)


def test_constant_velocity_gradient_phase_matches_exact_integral():
    z = np.array([-.003, 0., .002]); v = np.array([.01, -.02, 0.])
    spins = MovingBlochEnsemble(z, v, t1_s=2., t2_s=.2, off_hz=13.)
    spins.hard_rf(90.)
    dt = .017; g = .003
    spins.advance(dt, gz_t_m=g)
    expected = -1j*np.exp(-dt/.2)*np.exp(1j*(2*np.pi*13*dt+GAMMA*g*(z*dt+v*dt**2/2)))
    assert spins.state[:, 0]+1j*spins.state[:, 1] == pytest.approx(expected, abs=1e-13)
    assert spins.positions() == pytest.approx(z+v*dt)


def test_finite_rf_motion_relaxation_matches_independent_rk4():
    z0 = .001; velocity = .02; g = .001; b1 = 3.+2j; duration = .001
    def derivative(t, state):
        omega = np.array([GAMMA*b1.real*1e-6, GAMMA*b1.imag*1e-6, GAMMA*g*(z0+velocity*t)+2*np.pi*17])
        return np.cross(omega, state)+np.array([-state[0]/.08, -state[1]/.08, (1-state[2])/1.2])
    state = np.array([0., 0., 1.]); dt = duration/4096
    for i in range(4096):
        t = i*dt; k1 = derivative(t,state); k2 = derivative(t+dt/2,state+dt*k1/2)
        k3 = derivative(t+dt/2,state+dt*k2/2); k4 = derivative(t+dt,state+dt*k3)
        state += dt*(k1+2*k2+2*k3+k4)/6
    errors = []
    for steps in [32, 64, 128]:
        spins = MovingBlochEnsemble([z0], velocity, t1_s=1.2, t2_s=.08, off_hz=17)
        for _ in range(steps): spins.advance(duration/steps, b1_uT=b1, gz_t_m=g)
        errors.append(np.linalg.norm(spins.state[0]-state))
    assert errors[-1] < 1e-6
    assert errors[1] < errors[0]/3 and errors[2] < errors[1]/3


def test_selective_rf_is_finite_profile_not_binary_slab():
    z = np.array([0., .002, .004, .009])
    spins = MovingBlochEnsemble(z, 0., t1_s=1e6, t2_s=1e6)
    rf = selective_sinc(180., steps=256)
    for b in rf['b1_uT']: spins.advance(rf['dt_s'], b1_uT=complex(b), gz_t_m=rf['gz_t_m'])
    assert spins.state[0, 2] < -.999
    assert spins.state[-1, 2] > .99
    assert abs(spins.state[1, 2]-spins.state[0, 2]) > .05
    assert rf['rf_energy_uT2_s'] > 0


def test_gates_use_actual_rr_and_reject_crossings_and_last_trigger():
    gates = plan_gated_readouts([0., 1.2, 1.6, 2.2, 3.4], delay_s=.8)
    assert [g['rejection'] for g in gates] == [None, 'rr_outside_range', 'crosses_next_trigger', None, 'no_following_trigger']
    assert gates[0]['readout_s'] == .8
    assert gates[3]['readout_s'] == 3.


def test_flow_changes_suppression_and_persistent_cycles_replay():
    static = run_flow_imaging(blood_velocity_m_s=0.)
    moving = run_flow_imaging(blood_velocity_m_s=.025)
    assert moving['objective_loss'] < static['objective_loss']
    first, second = moving['readouts']
    assert first['tissues']['blood']['geometric_incoming_fraction'] == 1.
    assert abs(first['tissues']['blood']['mean_mz']-second['tissues']['blood']['mean_mz']) > .1
    assert not moving['validation']['passed']  # declared wall/blood targets really fail
    assert moving['provenance']['estimated_work'] <= moving['provenance']['planned_work'] <= 10000000
    replay = run_flow_imaging(**moving['provenance']['replay'])
    assert replay == moving


def test_moving_inverted_blood_matches_analytic_recovery_first_cycle():
    ti = .9
    r = run_flow_imaging(r_peaks_s=[0., 1.2], inversion_time_s=ti)
    assert r['readouts'][0]['tissues']['blood']['mean_mz'] == pytest.approx(1-2*np.exp(-ti/1.6), abs=5e-4)


def test_rf_and_reservoir_grid_convergence():
    base = run_flow_imaging(r_peaks_s=[0., 1.2], rf_steps=128, spin_count=801)
    fine_rf = run_flow_imaging(r_peaks_s=[0., 1.2], rf_steps=256, spin_count=801)
    fine_space = run_flow_imaging(r_peaks_s=[0., 1.2], rf_steps=256, spin_count=1601)
    for tissue in ['wall', 'blood']:
        b = base['readouts'][0]['tissues'][tissue]['mean_mz']
        f = fine_rf['readouts'][0]['tissues'][tissue]['mean_mz']
        s = fine_space['readouts'][0]['tissues'][tissue]['mean_mz']
        assert abs(f-b) < 1e-4 and abs(s-f) < .02


def test_search_runs_model_and_keeps_infeasible_candidates():
    r = search_flow_timing([.6, .9, 1.1, 1.3], r_peaks_s=[0., 1.2])
    assert r['best']['inversion_time_s'] == 1.1
    assert not r['candidates'][-1]['feasible']
    replay = run_flow_imaging(**r['best']['result']['provenance']['replay'])
    assert replay == r['best']['result']
    assert search_flow_timing([1.3], r_peaks_s=[0., 1.2])['best'] is None


@pytest.mark.parametrize('patch', [dict(max_work=1), dict(max_duration_s=.1),
    dict(rf_steps=True), dict(rf_steps=100000000), dict(spin_count=5),
    dict(thickness_m=0), dict(inversion_time_s=.001), dict(blood_target_max=0),
    dict(r_peaks_s=[0., .3, .6]), dict(r_peaks_s=[0., 0.]),
    dict(blood_velocity_m_s=float('nan'))])
def test_invalid_flow_design_and_budgets(patch):
    with pytest.raises(ValueError): run_flow_imaging(**patch)
