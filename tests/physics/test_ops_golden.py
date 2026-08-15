import numpy as np
import pytest

from mrqlab_physics.ops.relax import relaxation_factors
from mrqlab_physics.ops.rf import epg_rf_matrix, rotate_cartesian
from mrqlab_physics.ops.sample import demodulate
from mrqlab_physics.ops.types import AdcSample, GradInterval, Relax, RfOp, Shift


def test_operator_contract_fields_are_explicit():
    assert RfOp(0.0, np.pi / 2, 0.0).alpha_rad == pytest.approx(np.pi / 2)
    assert Relax(0.0, 0.01).dt == 0.01
    assert Shift(0.01, (1, 0, 0), "metadata").source == "metadata"
    assert GradInterval(0.0, 0.01, (1.0, 0.0, 0.0)).gradient[0] == 1.0
    assert AdcSample(0.02, 0.0, 0.0).t == 0.02


def test_epg_rf_90_x_has_weigel_coefficients():
    matrix = epg_rf_matrix(np.pi / 2, 0.0)
    expected = np.array([
        [0.5, 0.5, -1j],
        [0.5, 0.5, 1j],
        [-0.5j, 0.5j, 0.0],
    ])
    np.testing.assert_allclose(matrix, expected, atol=1e-12)


def test_cartesian_rf_phase_changes_rotation_axis():
    state = np.array([[0.0, 0.0, 1.0]])
    np.testing.assert_allclose(rotate_cartesian(state, np.pi / 2, 0.0), [[0.0, -1.0, 0.0]], atol=1e-12)
    np.testing.assert_allclose(rotate_cartesian(state, np.pi / 2, np.pi / 2), [[1.0, 0.0, 0.0]], atol=1e-12)


def test_relaxation_half_life_and_nco_demodulation():
    e1, e2 = relaxation_factors(np.log(2), 2.0, 1.0)
    assert e1 == pytest.approx(2 ** -0.5)
    assert e2 == pytest.approx(0.5)
    assert demodulate(1 + 0j, t=0.25, frequency_hz=1.0, phase_rad=0.0) == pytest.approx(-1j)
