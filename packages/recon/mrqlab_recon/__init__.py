import numpy as np

from .trajectories import (
    TrajectorySpec,
    generate_trajectory,
    gridding_recon_2d,
    undersampled_recon_demo,
)


def fft_reconstruct(data: np.ndarray, dimensions: int = 1) -> np.ndarray:
    """Centered Cartesian FFT reconstruction."""
    axes = tuple(range(-dimensions, 0))
    return np.fft.fftshift(np.fft.ifftn(np.fft.ifftshift(data, axes=axes), axes=axes), axes=axes)


def nufft_reconstruct(kx, ky, kdata, grid_size: int = 128, **kwargs) -> np.ndarray:
    """Gridding NUFFT adapter (density-compensated nearest-neighbor)."""
    return gridding_recon_2d(
        np.asarray(kx, dtype=np.float64),
        np.asarray(ky, dtype=np.float64),
        np.asarray(kdata, dtype=np.complex128),
        grid_size=grid_size,
    )
