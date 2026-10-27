"""Single-voxel N-liquid-pool rectangular Bloch--McConnell saturation."""

import math

import numpy as np

from ..kernel.units import GAMMA_BAR_HZ_T
from ..models import BlochMcConnellPools
from .types import Relax, SaturationOp


def _matrix_exp(generator: np.ndarray, duration_s: float) -> np.ndarray:
    a = np.asarray(generator)*duration_s
    scale = max(0, int(np.ceil(np.log2(max(float(np.linalg.norm(a, ord=np.inf)), 1.)))))
    a = a / 2**scale
    result = np.eye(a.shape[0], dtype=a.dtype)
    term = result.copy()
    for k in range(1, 80):
        term = term @ a / k
        result += term
        if np.linalg.norm(term, ord=np.inf) < 1e-16:
            break
    for _ in range(scale):
        result = result @ result
    return np.real_if_close(result)


def apply_cw_bloch_mcconnell_saturation(
    state: np.ndarray, duration_s: float, offset_hz: float, b1_ut: float,
    pools: BlochMcConnellPools,
) -> None:
    """Evolve k=0 via an affine (3N+1)-dimensional BM generator.

    Other configuration orders are intentionally untouched. Two-pool models
    adapt to the same generator with their historical parameter semantics.
    """
    from ..models import LiquidPoolSystem
    system = pools if isinstance(pools, LiquidPoolSystem) else LiquidPoolSystem.from_two(pools)
    n = system.count
    if state.ndim != 2 or state.shape[0] != 3*n or duration_s <= 0 or b1_ut <= 0:
        raise ValueError("CEST requires a 3N-row state and positive duration/power")
    if not all(np.isfinite(v) for v in (duration_s, offset_hz, b1_ut)):
        raise ValueError("CEST saturation values must be finite")
    zero = state.shape[1] // 2
    w1 = 2 * np.pi * GAMMA_BAR_HZ_T * b1_ut * 1e-6
    g = np.zeros((3*n+1, 3*n+1))
    for i in range(n):
        base = 3*i
        delta = 2*np.pi*(offset_hz-system.offset_hz[i])
        g[base:base+3, base:base+3] = np.array([
            [-1/system.t2[i], delta, 0], [-delta, -1/system.t2[i], w1],
            [0, -w1, -1/system.t1[i]]])
        for j in range(n):
            g[base:base+3, 3*j:3*j+3] += np.eye(3)*system.exchange[i,j]
        g[base+2, -1] = system.density[i]/system.t1[i]
    vector = np.ones(3*n+1)
    for i in range(n):
        vector[3*i:3*i+3] = (state[3*i,zero].real, state[3*i,zero].imag, state[3*i+2,zero].real)
    out = _matrix_exp(g, duration_s) @ vector
    for i in range(n):
        state[3*i,zero] = out[3*i]+1j*out[3*i+1]
        state[3*i+1,zero] = out[3*i]-1j*out[3*i+1]
        state[3*i+2,zero] = out[3*i+2]


def validate_cest_timing(cest: dict) -> tuple[str, int, float, float, float, float]:
    """Return mode, pulse count, pulse/gap durations, elapsed time, and duty cycle."""
    mode = cest.get("mode", "cw")
    if mode not in {"cw", "pulsed"}:
        raise ValueError("CEST mode must be 'cw' or 'pulsed'")
    duration = float(cest["saturation_duration_s"])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("CEST saturation duration must be finite and positive")
    if mode == "cw":
        return mode, 1, duration, 0.0, duration, 1.0
    required = ("n_pulses", "pulse_duration_s", "gap_duration_s")
    if any(key not in cest for key in required):
        raise ValueError("pulsed CEST requires n_pulses, pulse_duration_s, and gap_duration_s")
    raw_n = cest["n_pulses"]
    if isinstance(raw_n, bool) or not isinstance(raw_n, int) or raw_n < 1:
        raise ValueError("pulsed CEST n_pulses must be an integer >= 1")
    pulse, gap = float(cest["pulse_duration_s"]), float(cest["gap_duration_s"])
    if not math.isfinite(pulse) or pulse <= 0 or not math.isfinite(gap) or gap < 0:
        raise ValueError("pulsed CEST pulse and gap durations are invalid")
    elapsed = raw_n * pulse + max(raw_n - 1, 0) * gap
    if abs(duration - elapsed) > 1e-9:
        raise ValueError("pulsed CEST saturation_duration_s must match train elapsed time")
    return mode, raw_n, pulse, gap, elapsed, raw_n * pulse / elapsed


def expand_cest_saturation_ops(n_pulses: int, pulse_duration_s: float, gap_duration_s: float,
                               offset_hz: float, power_uT: float):
    """Expand one rectangular pulsed saturation train into executable operators."""
    for index in range(n_pulses):
        yield SaturationOp(0.0, pulse_duration_s, offset_hz, power_uT)
        if index < n_pulses - 1:
            yield Relax(0.0, gap_duration_s)
