import numpy as np
def fft_reconstruct(data: np.ndarray, dimensions: int = 1) -> np.ndarray:
    """Centered Cartesian FFT reconstruction. NUFFT is a future adapter."""
    axes = tuple(range(-dimensions, 0))
    return np.fft.fftshift(np.fft.ifftn(np.fft.ifftshift(data, axes=axes), axes=axes), axes=axes)
def nufft_reconstruct(*args, **kwargs):
    raise NotImplementedError("NUFFT adapter is planned; MVP supports Cartesian FFT")
