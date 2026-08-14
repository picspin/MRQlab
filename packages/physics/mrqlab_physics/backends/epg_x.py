from enum import Enum

import numpy as np


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


def apply_bloch_mcconnell(state: np.ndarray, dt: float) -> None:
    if state.ndim != 2 or state.shape[0] != 6 or dt < 0:
        raise ValueError("Bloch-McConnell state must have shape (6, orders) and non-negative dt")
    raise EpgXFeatureUnavailable("Bloch-McConnell exchange is outside physics v1")


def apply_magnetization_transfer(state: np.ndarray, dt: float) -> None:
    if state.ndim != 2 or state.shape[0] != 4 or dt < 0:
        raise ValueError("magnetization-transfer state must have shape (4, orders) and non-negative dt")
    raise EpgXFeatureUnavailable("magnetization transfer is outside physics v1")
