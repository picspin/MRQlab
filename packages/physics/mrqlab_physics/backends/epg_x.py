from enum import Enum

import numpy as np

from ..models import BlochMcConnellPools, MagnetizationTransferPools, Phantom
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


def _matrix_exp(matrix: np.ndarray, dt: float) -> np.ndarray:
    values, vectors = np.linalg.eig(matrix)
    return np.real_if_close(vectors @ np.diag(np.exp(values * dt)) @ np.linalg.inv(vectors))


def apply_bloch_mcconnell(
    state: np.ndarray, dt: float, pools: BlochMcConnellPools, *, off_resonance_hz: float = 0.0
) -> None:
    if state.ndim != 2 or state.shape[0] != 6 or dt < 0:
        raise ValueError("Bloch-McConnell state must have shape (6, orders) and non-negative dt")
    if not isinstance(pools, BlochMcConnellPools):
        raise TypeError("pools must be BlochMcConnellPools")
    if dt == 0:
        return
    # Rates are in cycles/s as declared by the tissue contract; exchange itself
    # is a first-order rate (no 2*pi conversion). Both pools share the phantom
    # off-resonance until per-tissue offsets become part of ExperimentGraph.
    transverse = np.array([
        [-1 / pools.t2_a - pools.k_ab_hz, pools.k_ba_hz],
        [pools.k_ab_hz, -1 / pools.t2_b - pools.k_ba_hz],
    ], dtype=complex)
    phase = 2j * np.pi * off_resonance_hz
    for rows, sign in (((0, 3), 1), ((1, 4), -1)):
        generator = transverse + np.eye(2) * sign * phase
        state[list(rows)] = _matrix_exp(generator, dt) @ state[list(rows)]
    longitudinal = np.array([
        [-1 / pools.t1_a - pools.k_ab_hz, pools.k_ba_hz],
        [pools.k_ab_hz, -1 / pools.t1_b - pools.k_ba_hz],
    ])
    equilibrium = np.array([pools.pd_a / pools.t1_a, pools.pd_b / pools.t1_b])[:, None]
    propagator = _matrix_exp(longitudinal, dt)
    steady = np.linalg.solve(-longitudinal, equilibrium)
    state[[2, 5]] = propagator @ state[[2, 5]] + (np.eye(2) - propagator) @ steady


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
        if (phantom.bloch_mcconnell is None) == (phantom.magnetization_transfer is None):
            raise ValueError("epg-x requires exactly one explicit two-pool model")
        self.phantom = phantom
        self.zero = kmax
        self.layout = (EpgXLayout.BLOCH_MCCONNELL if phantom.bloch_mcconnell
                       else EpgXLayout.MAGNETIZATION_TRANSFER)
        self.omega = epg_x_zeros(self.layout, kmax)
        pools = phantom.bloch_mcconnell or phantom.magnetization_transfer
        self.omega[2, self.zero] = pools.pd_a
        self.omega[-1, self.zero] = pools.pd_b

    def apply(self, op: Operator) -> None:
        if isinstance(op, SaturationOp):
            if self.layout is not EpgXLayout.BLOCH_MCCONNELL:
                raise EpgXFeatureUnavailable("CEST requires the 6-row two-liquid Bloch-McConnell layout")
            apply_cw_bloch_mcconnell_saturation(
                self.omega, op.duration_s, op.offset_hz, op.b1_ut, self.phantom.bloch_mcconnell
            )
        elif isinstance(op, RfOp):
            rotation = epg_rf_matrix(op.alpha_rad, op.phase_rad)
            self.omega[:3] = rotation @ self.omega[:3]
            if self.layout is EpgXLayout.BLOCH_MCCONNELL:
                self.omega[3:] = rotation @ self.omega[3:]
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
                apply_bloch_mcconnell(self.omega, op.dt, self.phantom.bloch_mcconnell,
                                      off_resonance_hz=self.phantom.off_resonance_hz)
            else:
                apply_magnetization_transfer(self.omega, op.dt, self.phantom.magnetization_transfer,
                                             off_resonance_hz=self.phantom.off_resonance_hz)
        elif isinstance(op, Shift):
            pairs = ((0, 1), (3, 4)) if self.layout is EpgXLayout.BLOCH_MCCONNELL else ((0, 1),)
            for plus, minus in pairs:
                self.omega[plus] = _translate(self.omega[plus], op.dk[0])
                self.omega[minus] = _translate(self.omega[minus], -op.dk[0])
        elif isinstance(op, GradInterval):
            return

    def observe(self) -> complex:
        signal = self.omega[0, self.zero]
        if self.layout is EpgXLayout.BLOCH_MCCONNELL:
            signal += self.omega[3, self.zero]
        return complex(signal)

    def snapshot(self) -> np.ndarray:
        return self.omega.copy()
