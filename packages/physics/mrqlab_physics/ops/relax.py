import numpy as np


def relaxation_factors(dt: float, t1: float, t2: float) -> tuple[float, float]:
    if dt < 0 or t1 <= 0 or t2 <= 0:
        raise ValueError("dt must be non-negative and relaxation times positive")
    return float(np.exp(-dt / t1)), float(np.exp(-dt / t2))
