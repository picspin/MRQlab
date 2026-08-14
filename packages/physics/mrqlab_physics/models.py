from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class Isochromat:
    t1: float = 1.0
    t2: float = 0.1
    proton_density: float = 1.0
    off_resonance_hz: float = 0.0
    position_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    weight: float = 1.0

    def __post_init__(self):
        if self.t1 <= 0 or self.t2 <= 0:
            raise ValueError("isochromat t1 and t2 must be positive")
        if self.proton_density < 0 or self.weight < 0:
            raise ValueError("isochromat proton_density and weight must be non-negative")


@dataclass(frozen=True, slots=True)
class SpectralPool:
    name: str
    fraction: float
    chemical_shift_ppm: float
    t1: float
    t2: float

    def __post_init__(self):
        if self.fraction < 0 or self.t1 <= 0 or self.t2 <= 0:
            raise ValueError("spectral pool fraction must be non-negative and relaxation times positive")


@dataclass(slots=True)
class Phantom:
    t1: float = 1.0
    t2: float = 0.1
    proton_density: float = 1.0
    off_resonance_hz: float = 0.0
    isochromats: tuple[Isochromat, ...] = ()
    pools: tuple[SpectralPool, ...] = ()

    def resolved_isochromats(self) -> tuple[Isochromat, ...]:
        if self.isochromats:
            return self.isochromats
        return (Isochromat(self.t1, self.t2, self.proton_density, self.off_resonance_hz),)


@dataclass(frozen=True, slots=True)
class ScannerModel:
    b0_t: float = 1.5
    gradient_scale: float = 1.0

    def __post_init__(self):
        if self.b0_t <= 0 or self.gradient_scale < 0:
            raise ValueError("scanner b0_t must be positive and gradient_scale non-negative")


@dataclass(frozen=True, slots=True)
class EngineOptions:
    dwell_time: float = 0.001
    return_magnetization: bool = True
    return_configurations: bool = False
    epg_kmax: int = 64
    epg_dk_scale: float = 0.001
    max_work: int = 2_000_000

    def __post_init__(self):
        if self.dwell_time <= 0 or self.epg_dk_scale <= 0:
            raise ValueError("dwell_time and epg_dk_scale must be positive")
        if self.epg_kmax < 0 or self.max_work < 1:
            raise ValueError("epg_kmax must be non-negative and max_work positive")


@dataclass(slots=True)
class SimResult:
    signal: np.ndarray
    k_trajectory: np.ndarray
    magnetization: np.ndarray | None = None
    configurations: np.ndarray | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    timing: dict[str, float] = field(default_factory=dict)
