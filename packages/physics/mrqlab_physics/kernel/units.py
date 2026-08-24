import numpy as np

GAMMA_BAR_HZ_T = 42.57747892e6
DEFAULT_FOV_M = 0.22


def deg_to_rad(value: float) -> float:
    return float(np.deg2rad(value))


def gradient_hz_per_m(value, scanner, units: str):
    """Convert a gradient vector to Hz/m without reinterpreting teaching values."""
    gradient = np.asarray(value, dtype=float)
    if units == "teaching":
        return gradient * scanner.gradient_scale
    if units == "mt_m":
        return gradient * 1e-3 * GAMMA_BAR_HZ_T
    raise ValueError("gradient_units must be 'teaching' or 'mt_m'")
