"""Single-voxel, two-liquid-pool CW Bloch--McConnell saturation."""

import numpy as np

from ..kernel.units import GAMMA_BAR_HZ_T
from ..models import BlochMcConnellPools


def _matrix_exp(generator: np.ndarray, duration_s: float) -> np.ndarray:
    values, vectors = np.linalg.eig(generator)
    return np.real_if_close(vectors @ np.diag(np.exp(values * duration_s)) @ np.linalg.inv(vectors))


def apply_cw_bloch_mcconnell_saturation(
    state: np.ndarray, duration_s: float, offset_hz: float, b1_ut: float,
    pools: BlochMcConnellPools,
) -> None:
    """Evolve only k=0 in the existing 6-row EPG-X BM layout.

    A homogeneous affine 7x7 generator evolves ``(Mx, My, Mz)`` for water and
    solute plus a constant equilibrium coordinate.  Other configuration orders
    are intentionally untouched.
    """
    if state.shape[0] != 6 or duration_s <= 0 or b1_ut <= 0:
        raise ValueError("CEST saturation requires a 6-row state and positive duration/power")
    if not all(np.isfinite(v) for v in (duration_s, offset_hz, b1_ut)):
        raise ValueError("CEST saturation values must be finite")
    zero = state.shape[1] // 2
    w1 = 2 * np.pi * GAMMA_BAR_HZ_T * b1_ut * 1e-6
    dw = 2 * np.pi * offset_hz
    ds = 2 * np.pi * (offset_hz - pools.delta_b_hz)
    g = np.zeros((7, 7), dtype=float)
    for base, t1, t2, loss, gain, delta, pd in (
        (0, pools.t1_a, pools.t2_a, pools.k_ab_hz, pools.k_ba_hz, dw, pools.pd_a),
        (3, pools.t1_b, pools.t2_b, pools.k_ba_hz, pools.k_ab_hz, ds, pools.pd_b),
    ):
        other = 3 - base
        g[base, base] = g[base + 1, base + 1] = -1 / t2 - loss
        g[base + 2, base + 2] = -1 / t1 - loss
        g[base, base + 1], g[base + 1, base] = delta, -delta
        g[base + 1, base + 2], g[base + 2, base + 1] = w1, -w1
        g[base:base + 3, other:other + 3] += np.eye(3) * gain
        g[base + 2, 6] = pd / t1
    vector = np.array([
        state[0, zero].real, state[0, zero].imag, state[2, zero].real,
        state[3, zero].real, state[3, zero].imag, state[5, zero].real, 1.0,
    ])
    out = _matrix_exp(g, duration_s) @ vector
    state[0, zero], state[1, zero], state[2, zero] = out[0] + 1j*out[1], out[0] - 1j*out[1], out[2]
    state[3, zero], state[4, zero], state[5, zero] = out[3] + 1j*out[4], out[3] - 1j*out[4], out[5]
