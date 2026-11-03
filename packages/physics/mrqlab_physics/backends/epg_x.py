from enum import Enum

import numpy as np

from ..models import BlochMcConnellPools, MagnetizationTransferPools, Phantom, LiquidPoolSystem
from ..ops.rf import epg_rf_matrix
from ..ops.super_lorentzian import apply_super_lorentzian_saturation
from ..ops.cest_saturation import apply_cw_bloch_mcconnell_saturation
from ..ops.types import GradInterval, Operator, Relax, RfOp, SaturationOp, Shift
from .epg import _translate


class EpgXFeatureUnavailable(NotImplementedError):
    pass


class EpgXLayout(str, Enum):
    BLOCH_MCCONNELL = "bloch-mcconnell"
    MAGNETIZATION_TRANSFER = "magnetization-transfer"


STATE_FIELDS = {
    EpgXLayout.BLOCH_MCCONNELL: ("F+a", "F-a", "Za", "F+b", "F-b", "Zb"),
    EpgXLayout.MAGNETIZATION_TRANSFER: ("F+a", "F-a", "Za", "Zb"),
}


def epg_x_zeros(layout: EpgXLayout, kmax: int) -> np.ndarray:
    if kmax < 0:
        raise ValueError("kmax must be non-negative")
    return np.zeros((len(STATE_FIELDS[layout]), 2 * kmax + 1), dtype=np.complex128)


from ..ops.cest_saturation import _matrix_exp


def apply_bloch_mcconnell(
    state: np.ndarray, dt: float, pools: BlochMcConnellPools, *, off_resonance_hz: float = 0.0
) -> None:
    system = pools if isinstance(pools, LiquidPoolSystem) else LiquidPoolSystem.from_two(pools)
    n = system.count
    if state.ndim != 2 or state.shape[0] != 3*n or not np.isfinite(dt) or dt < 0:
        raise ValueError("Bloch-McConnell requires a 3N-row state and nonnegative dt")
    if dt == 0:
        return
    for row, sign in ((0, 1), (1, -1)):
        generator = system.exchange.astype(complex) - np.diag(1/np.asarray(system.t2))
        generator += np.diag(sign*2j*np.pi*(np.asarray(system.offset_hz)+off_resonance_hz))
        indices = np.arange(row, 3*n, 3)
        state[indices] = _matrix_exp(generator, dt) @ state[indices]
    generator = system.exchange - np.diag(1/np.asarray(system.t1))
    propagator = _matrix_exp(generator, dt)
    equilibrium = np.linalg.solve(-generator, np.asarray(system.density)/np.asarray(system.t1))
    indices = np.arange(2, 3*n, 3)
    # Recovery acts only on k=0, never on nonzero configuration orders.
    state[indices] = propagator @ state[indices]
    state[indices, state.shape[1]//2] += (np.eye(n)-propagator) @ equilibrium


def apply_magnetization_transfer(
    state: np.ndarray,
    dt: float,
    pools: MagnetizationTransferPools,
    *,
    off_resonance_hz: float = 0.0,
) -> None:
    if state.ndim != 2 or state.shape[0] != 4 or dt < 0:
        raise ValueError("magnetization-transfer state must have shape (4, orders) and non-negative dt")
    if not isinstance(pools, MagnetizationTransferPools):
        raise TypeError("pools must be MagnetizationTransferPools")
    if dt == 0:
        return
    decay = np.exp(-dt / pools.t2_a)
    phase = 2j * np.pi * off_resonance_hz * dt
    state[0] *= decay * np.exp(phase)
    state[1] *= decay * np.exp(-phase)
    longitudinal = np.array([
        [-1 / pools.t1_a - pools.k_ab_hz, pools.k_ba_hz],
        [pools.k_ab_hz, -1 / pools.t1_b - pools.k_ba_hz],
    ])
    equilibrium = np.array([pools.pd_a / pools.t1_a, pools.pd_b / pools.t1_b])[:, None]
    propagator = _matrix_exp(longitudinal, dt)
    steady = np.linalg.solve(-longitudinal, equilibrium)
    state[[2, 3]] = propagator @ state[[2, 3]] + (np.eye(2) - propagator) @ steady


class EpgXBackend:
    def __init__(self, phantom: Phantom, kmax: int):
        if sum(x is not None for x in (phantom.bloch_mcconnell, phantom.liquid_pools, phantom.magnetization_transfer)) != 1:
            raise ValueError("epg-x requires exactly one explicit two-pool model")
        self.phantom = phantom
        self.zero = kmax
        self.layout = (EpgXLayout.BLOCH_MCCONNELL if (phantom.bloch_mcconnell or phantom.liquid_pools)
                       else EpgXLayout.MAGNETIZATION_TRANSFER)
        self.pools = phantom.liquid_pools or phantom.bloch_mcconnell
        if phantom.liquid_pools:
            self.omega = np.zeros((3*phantom.liquid_pools.count, 2*kmax+1), complex)
            self.omega[2::3, self.zero] = phantom.liquid_pools.density
        else:
            self.omega = epg_x_zeros(self.layout, kmax)
            pools = phantom.bloch_mcconnell or phantom.magnetization_transfer
            self.omega[2, self.zero] = pools.pd_a
            self.omega[-1, self.zero] = pools.pd_b

    def apply(self, op: Operator) -> None:
        if isinstance(op, SaturationOp):
            if self.layout is not EpgXLayout.BLOCH_MCCONNELL:
                raise EpgXFeatureUnavailable("CEST requires the 6-row two-liquid Bloch-McConnell layout")
            apply_cw_bloch_mcconnell_saturation(
                self.omega, op.duration_s, op.offset_hz - self.phantom.off_resonance_hz, op.b1_ut, self.pools
            )
        elif isinstance(op, RfOp):
            rotation = epg_rf_matrix(op.alpha_rad, op.phase_rad)
            self.omega[:3] = rotation @ self.omega[:3]
            if self.layout is EpgXLayout.BLOCH_MCCONNELL:
                for base in range(3, self.omega.shape[0], 3):
                    self.omega[base:base+3] = rotation @ self.omega[base:base+3]
            elif not np.isfinite(op.duration_s) or op.duration_s < 0:
                raise ValueError("MT RF duration_s must be finite and non-negative")
            elif op.duration_s > 0:
                pools = self.phantom.magnetization_transfer
                if pools.t2_b is None:
                    raise ValueError("Super-Lorentzian saturation requires finite positive t2_b")
                apply_super_lorentzian_saturation(
                    self.omega, op.duration_s, op.b1_ut, op.offset_hz, pools.t2_b
                )
        elif isinstance(op, Relax):
            if self.layout is EpgXLayout.BLOCH_MCCONNELL:
                apply_bloch_mcconnell(self.omega, op.dt, self.pools,
                                      off_resonance_hz=self.phantom.off_resonance_hz)
            else:
                apply_magnetization_transfer(self.omega, op.dt, self.phantom.magnetization_transfer,
                                             off_resonance_hz=self.phantom.off_resonance_hz)
        elif isinstance(op, Shift):
            pairs = tuple((i, i+1) for i in range(0, self.omega.shape[0], 3)) if self.layout is EpgXLayout.BLOCH_MCCONNELL else ((0, 1),)
            for plus, minus in pairs:
                self.omega[plus] = _translate(self.omega[plus], op.dk[0])
                self.omega[minus] = _translate(self.omega[minus], -op.dk[0])
        elif isinstance(op, GradInterval):
            return

    def observe(self) -> complex:
        signal = self.omega[0, self.zero]
        if self.layout is EpgXLayout.BLOCH_MCCONNELL:
            signal = self.omega[::3, self.zero].sum()
        return complex(signal)

    def snapshot(self) -> np.ndarray:
        return self.omega.copy()
