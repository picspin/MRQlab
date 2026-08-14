from dataclasses import dataclass, field
from typing import Any
import numpy as np

@dataclass
class Phantom:
    t1: float = 1.0
    t2: float = .1
    proton_density: float = 1.0
    off_resonance_hz: float = 0.0

@dataclass
class ScannerModel:
    b0_t: float = 1.5
    gradient_scale: float = 1.0

@dataclass
class EngineOptions:
    dwell_time: float = .001
    return_magnetization: bool = True

@dataclass
class SimResult:
    signal: np.ndarray
    k_trajectory: np.ndarray
    magnetization: np.ndarray | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    timing: dict[str, float] = field(default_factory=dict)
