from dataclasses import dataclass, field
from numbers import Integral, Real
from typing import Any

import numpy as np


def _require_finite_real(name: str, value: Real) -> None:
    if isinstance(value, bool) or not isinstance(value, Real) or not np.isfinite(value):
        raise ValueError(f"{name} must be a finite real number")


def _require_strict_int(name: str, value: Integral) -> None:
    if isinstance(value, Real) and not isinstance(value, bool) and not np.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be a strict integer")


def _require_strict_bool(name: str, value: bool) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a strict boolean")


@dataclass(frozen=True, slots=True)
class Isochromat:
    t1: float = 1.0
    t2: float = 0.1
    proton_density: float = 1.0
    off_resonance_hz: float = 0.0
    position_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    weight: float = 1.0

    def __post_init__(self):
        for name in ("t1", "t2", "proton_density", "off_resonance_hz", "weight"):
            _require_finite_real(f"isochromat {name}", getattr(self, name))
        if len(self.position_m) != 3:
            raise ValueError("isochromat position_m must contain three finite values")
        for value in self.position_m:
            _require_finite_real("isochromat position_m", value)
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
        for name in ("fraction", "chemical_shift_ppm", "t1", "t2"):
            _require_finite_real(f"spectral pool {name}", getattr(self, name))
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

    def __post_init__(self):
        for name in ("t1", "t2", "proton_density", "off_resonance_hz"):
            _require_finite_real(f"phantom {name}", getattr(self, name))
        if self.t1 <= 0 or self.t2 <= 0:
            raise ValueError("phantom t1 and t2 must be positive")
        if self.proton_density < 0:
            raise ValueError("phantom proton_density must be non-negative")
        if any(not isinstance(spin, Isochromat) for spin in self.isochromats):
            raise TypeError("phantom isochromats must contain Isochromat values")
        if any(not isinstance(pool, SpectralPool) for pool in self.pools):
            raise TypeError("phantom pools must contain SpectralPool values")

    def resolved_isochromats(self) -> tuple[Isochromat, ...]:
        if self.isochromats:
            return self.isochromats
        return (Isochromat(self.t1, self.t2, self.proton_density, self.off_resonance_hz),)


@dataclass(frozen=True, slots=True)
class ScannerModel:
    b0_t: float = 1.5
    gradient_scale: float = 1.0

    def __post_init__(self):
        _require_finite_real("scanner b0_t", self.b0_t)
        _require_finite_real("scanner gradient_scale", self.gradient_scale)
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
        _require_finite_real("dwell_time", self.dwell_time)
        _require_finite_real("epg_dk_scale", self.epg_dk_scale)
        _require_strict_int("epg_kmax", self.epg_kmax)
        _require_strict_int("max_work", self.max_work)
        _require_strict_bool("return_magnetization", self.return_magnetization)
        _require_strict_bool("return_configurations", self.return_configurations)
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
    slice_profile: dict[str, np.ndarray] | None = None
    phase_distribution: dict[str, np.ndarray] | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    timing: dict[str, float] = field(default_factory=dict)
