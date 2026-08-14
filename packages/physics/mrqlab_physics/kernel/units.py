import numpy as np


def deg_to_rad(value: float) -> float:
    return float(np.deg2rad(value))


def gradient_hz_per_m(value: float, scale: float) -> float:
    return float(value * scale)
