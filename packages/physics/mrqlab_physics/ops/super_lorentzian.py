"""Super-Lorentzian RF absorption for a longitudinal bound pool."""

import numpy as np

from ..kernel.units import GAMMA_BAR_HZ_T


_MAGIC_U = 1 / np.sqrt(3)
_MAGIC_ANGLE_CUTOFF = 1e-8
_QUADRATURE_ORDER = 256


def _integrate_interval(start: float, stop: float, offset_hz: float, t2_b: float) -> float:
    nodes, weights = np.polynomial.legendre.leggauss(_QUADRATURE_ORDER)
    u = (stop - start) * nodes / 2 + (stop + start) / 2
    denominator = 3 * u**2 - 1
    exponent = -2 * (2 * np.pi * offset_hz * t2_b / denominator) ** 2
    integrand = np.sqrt(2 / np.pi) * t2_b / np.abs(denominator) * np.exp(exponent)
    return float((stop - start) / 2 * np.dot(weights, integrand))


def super_lorentzian_lineshape(offset_hz: float, t2_b: float) -> float:
    """Return canonical bound-pool G_SL in seconds.

    The u=cos(theta) integral is split around the magic angle, excluding a
    1e-8-wide interval in u on either side. For nonzero offsets the limiting
    integrand is zero there; the cutoff prevents numerical division by zero.
    """
    if not np.isfinite(offset_hz) or offset_hz == 0:
        raise ValueError("Super-Lorentzian offset_hz must be finite and nonzero")
    if not np.isfinite(t2_b) or t2_b <= 0:
        raise ValueError("Super-Lorentzian t2_b must be finite and positive")
    return _integrate_interval(0, _MAGIC_U - _MAGIC_ANGLE_CUTOFF, offset_hz, t2_b) + \
        _integrate_interval(_MAGIC_U + _MAGIC_ANGLE_CUTOFF, 1, offset_hz, t2_b)


def super_lorentzian_absorption_rate(b1_ut: float | None, offset_hz: float, t2_b: float) -> float:
    """Return R_rfb = pi * omega1**2 * G_SL in inverse seconds."""
    if b1_ut is None or not np.isfinite(b1_ut) or b1_ut <= 0:
        raise ValueError("Super-Lorentzian b1_ut must be finite and positive")
    omega1 = 2 * np.pi * GAMMA_BAR_HZ_T * b1_ut * 1e-6
    return float(np.pi * omega1**2 * super_lorentzian_lineshape(offset_hz, t2_b))


def apply_super_lorentzian_saturation(
    state: np.ndarray, duration_s: float, b1_ut: float | None, offset_hz: float, t2_b: float
) -> None:
    """Attenuate only Zb in a homogeneous four-row MT configuration state."""
    if state.ndim != 2 or state.shape[0] != 4:
        raise ValueError("Super-Lorentzian MT state must have shape (4, orders)")
    if not np.isfinite(duration_s) or duration_s < 0:
        raise ValueError("Super-Lorentzian duration_s must be finite and non-negative")
    if duration_s == 0:
        return
    rate = super_lorentzian_absorption_rate(b1_ut, offset_hz, t2_b)
    state[3] *= np.exp(-rate * duration_s)
