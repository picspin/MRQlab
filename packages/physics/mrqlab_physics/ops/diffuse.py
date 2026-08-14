import numpy as np


def diffusion_attenuation(
    order: int,
    dk_cycles_per_m: float,
    diffusion_m2_s: float,
    dt: float,
) -> float:
    if diffusion_m2_s < 0 or dt < 0 or dk_cycles_per_m < 0:
        raise ValueError("diffusion coefficient, dt, and dk spacing must be non-negative")
    wave_number_rad_per_m = 2.0 * np.pi * abs(order) * dk_cycles_per_m
    return float(np.exp(-diffusion_m2_s * wave_number_rad_per_m**2 * dt))
