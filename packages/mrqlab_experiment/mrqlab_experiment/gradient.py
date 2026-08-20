import math
from typing import Any, Literal
import numpy as np
from pydantic import BaseModel, Field


class GradientHardwareConstraints(BaseModel):
    max_gradient_mt_m: float = Field(default=45.0, gt=0)   # mT/m
    max_slew_rate_t_m_s: float = Field(default=150.0, gt=0) # T/m/s (or mT/m/ms)


class GradientPulseSpec(BaseModel):
    amplitude_mt_m: float
    duration_ms: float
    ramp_time_ms: float
    channel: Literal["Gx", "Gy", "Gz"] = "Gx"


class DiffusionSpec(BaseModel):
    g_max_mt_m: float = Field(default=40.0, gt=0)
    delta_small_ms: float = Field(default=25.0, gt=0)  # pulse duration δ
    delta_big_ms: float = Field(default=50.0, gt=0)    # pulse interval Δ


class GradientValidationResult(BaseModel):
    is_valid: bool
    violations: list[str]
    actual_slew_rate: float
    actual_amplitude: float
    b_value_s_mm2: float | None = None
    sar_estimate_a_u: float | None = None


def validate_gradient(
    grad: GradientPulseSpec,
    hw: GradientHardwareConstraints,
) -> GradientValidationResult:
    """Validate gradient pulse against scanner hardware constraints."""
    violations = []
    
    # 1. Amplitude check
    if abs(grad.amplitude_mt_m) > hw.max_gradient_mt_m:
        violations.append(
            f"Amplitude {abs(grad.amplitude_mt_m):.1f} mT/m exceeds Gmax ({hw.max_gradient_mt_m:.1f} mT/m)"
        )
        
    # 2. Slew rate check (Slew = Amp / Ramp)
    slew = abs(grad.amplitude_mt_m) / max(1e-3, grad.ramp_time_ms) # mT/m / ms = T/m/s
    if slew > hw.max_slew_rate_t_m_s:
        violations.append(
            f"Slew rate {slew:.1f} T/m/s exceeds SlewRateMax ({hw.max_slew_rate_t_m_s:.1f} T/m/s)"
        )
        
    return GradientValidationResult(
        is_valid=len(violations) == 0,
        violations=violations,
        actual_slew_rate=slew,
        actual_amplitude=abs(grad.amplitude_mt_m),
    )


def calculate_diffusion_b_value(diff: DiffusionSpec) -> float:
    r"""
    Calculate Stejskal-Tanner Diffusion b-value:
    b = γ² * G² * δ² * (Δ - δ/3)
    where:
      γ = 2.675e8 rad/(s·T)  (1H gyromagnetic ratio)
      G is in T/m  (1 mT/m = 1e-3 T/m)
      δ, Δ are in seconds
    Result returned in s/mm² (1 s/m² = 1e-6 s/mm²).
    """
    gamma = 2.67513e8  # rad / (s * T)
    g_t_m = diff.g_max_mt_m * 1e-3
    delta = diff.delta_small_ms * 1e-3
    delta_big = diff.delta_big_ms * 1e-3
    
    # Standard Stejskal-Tanner formula for rectangular gradients
    b_s_m2 = (gamma ** 2) * (g_t_m ** 2) * (delta ** 2) * (delta_big - delta / 3.0)
    b_s_mm2 = b_s_m2 * 1e-6
    return float(b_s_mm2)


def generate_diffusion_waveform(diff: DiffusionSpec, num_points: int = 100) -> dict[str, Any]:
    """Generate time and amplitude arrays for dual Stejskal-Tanner diffusion gradients."""
    total_time_ms = diff.delta_big_ms + diff.delta_small_ms + 10.0
    t = np.linspace(0, total_time_ms, num_points)
    g = np.zeros_like(t)
    
    # First lobe: [5, 5 + delta]
    t1_start = 5.0
    t1_end = t1_start + diff.delta_small_ms
    g[(t >= t1_start) & (t <= t1_end)] = diff.g_max_mt_m
    
    # Second lobe: [5 + Delta, 5 + Delta + delta]
    t2_start = 5.0 + diff.delta_big_ms
    t2_end = t2_start + diff.delta_small_ms
    g[(t >= t2_start) & (t <= t2_end)] = diff.g_max_mt_m
    
    return {
        "time_ms": t.tolist(),
        "gradient_mt_m": g.tolist(),
        "b_value_s_mm2": calculate_diffusion_b_value(diff),
    }
