import numpy as np


def demodulate(value: complex, t: float, frequency_hz: float, phase_rad: float) -> complex:
    return complex(value * np.exp(-1j * (2.0 * np.pi * frequency_hz * t + phase_rad)))
