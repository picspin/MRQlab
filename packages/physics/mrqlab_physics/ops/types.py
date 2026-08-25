from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True, slots=True)
class RfOp:
    t: float
    alpha_rad: float
    phase_rad: float
    duration_s: float = 0.0
    offset_hz: float = 0.0
    b1_ut: float | None = None


@dataclass(frozen=True, slots=True)
class SaturationOp:
    """Declared homogeneous CW saturation; distinct from instantaneous hard RF."""

    t: float
    duration_s: float
    offset_hz: float
    b1_ut: float


@dataclass(frozen=True, slots=True)
class Relax:
    t: float
    dt: float


@dataclass(frozen=True, slots=True)
class Shift:
    t: float
    dk: tuple[int, int, int]
    source: str


@dataclass(frozen=True, slots=True)
class GradInterval:
    t: float
    dt: float
    gradient: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class AdcSample:
    t: float
    nco_frequency_hz: float
    nco_phase_rad: float


Operator: TypeAlias = RfOp | SaturationOp | Relax | Shift | GradInterval | AdcSample
