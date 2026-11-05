"""Bounded exact-DFT/CGLS reference inverse for small research grids.

This is an iterative inverse, not a fast NUFFT, density-compensated adjoint,
scanner reconstruction, or clinical calibration. No image-dependent gain fit.
"""
import numpy as np
from .spatial import validate_image


class RadialFourierOperator:
    """Unnormalized centered Fourier sum, with Cartesian kz for 3D.

    xy columns are kx, ky in cycles/pixel, matching radial_acquire. The
    Hermitian adjoint includes the nz factor of the unnormalized kz FFT.
    Work counts complex multiply terms plus a conservative FFT proxy.
    """
    def __init__(self, xy, shape, *, max_work=10000000000, max_memory_bytes=134217728):
        self.shape = tuple(shape)
        if len(self.shape) not in (2, 3) or any(type(n) is not int or n < 2 for n in self.shape) or self.shape[-2] != self.shape[-1]:
            raise ValueError('square 2D/3D grid required')
        self.xy = np.array(xy, dtype=float, copy=True)
        if self.xy.ndim != 2 or self.xy.shape[1] != 2 or len(self.xy) == 0 or not np.isfinite(self.xy).all() or np.any(abs(self.xy) > .5):
            raise ValueError('finite nonempty kx/ky in cycles/pixel within Nyquist required')
        for budget in (max_work, max_memory_bytes):
            if type(budget) is not int or budget <= 0:
                raise ValueError('positive integer budget required')
        self.nz = self.shape[0] if len(self.shape) == 3 else 1
        n = self.shape[-1]; m = len(self.xy); voxels = n*n
        self.sample_shape = (self.nz, m)
        # Includes basis/conjugate, construction temporaries and CG vectors.
        self.estimated_memory_bytes = 64*m*voxels + 128*self.nz*(m+voxels)
        if self.estimated_memory_bytes > max_memory_bytes:
            raise ValueError('exact DFT memory budget exceeded; use a smaller grid')
        self.max_work = max_work; self.work = 0
        self.operation_work = self.nz*m*voxels + int(2*self.nz*voxels*np.ceil(np.log2(max(2, self.nz))))
        self._charge(m*voxels)
        pos = np.arange(n)-n//2; xx, yy = np.meshgrid(pos, pos)
        self.basis = np.exp(-2j*np.pi*(self.xy[:, 0, None]*xx.ravel()+self.xy[:, 1, None]*yy.ravel()))
        self.basis_h = self.basis.conj().T

    def _charge(self, count):
        if self.work+count > self.max_work:
            raise ValueError('exact DFT work budget exceeded')
        self.work += count

    def forward(self, image):
        image = validate_image(image)
        if image.shape != self.shape:
            raise ValueError('inconsistent image dimensions')
        self._charge(self.operation_work)
        planes = image.reshape(self.nz, -1)
        if len(self.shape) == 3:
            planes = np.fft.fftshift(np.fft.fft(np.fft.ifftshift(planes, axes=0), axis=0), axes=0)
        return planes @ self.basis.T

    def adjoint(self, samples):
        samples = np.asarray(samples, complex)
        if samples.shape != self.sample_shape or not np.isfinite(samples).all():
            raise ValueError('inconsistent finite complex samples')
        self._charge(self.operation_work)
        planes = samples @ self.basis_h.T
        if len(self.shape) == 3:
            planes = self.nz*np.fft.fftshift(np.fft.ifft(np.fft.ifftshift(planes, axes=0), axis=0), axes=0)
        return planes.reshape(self.shape)


def radial_cgls(xy, samples, shape, *, max_iterations=1500, tolerance=1e-12,
                max_work=10000000000, max_memory_bytes=134217728):
    """Minimize ||A x - samples||², zero start, no regularizer or gain scaling.

    A small data residual does not imply image identifiability (especially for
    undersampling). Image quality must be tested separately against a known
    reference. All stop reasons, actual work and residual history are returned.
    """
    if type(max_iterations) is not int or max_iterations < 1:
        raise ValueError('positive integer iteration limit required')
    if not np.isfinite(tolerance) or not 0 < tolerance < 1:
        raise ValueError('relative data tolerance must lie between zero and one')
    op = RadialFourierOperator(xy, shape, max_work=max_work, max_memory_bytes=max_memory_bytes)
    samples = np.asarray(samples, complex)
    # Reserve adjoint initialization and final measured residual before starting.
    if op.work+2*op.operation_work > max_work:
        raise ValueError('insufficient work for inverse initialization and validation')
    r = samples.copy(); z = op.adjoint(r); direction = z.copy()
    gamma = float(np.vdot(z, z).real)
    image = np.zeros(shape, complex); norm = float(np.linalg.norm(samples))
    history = [1. if norm else 0.]; iterations = 0
    reason = 'zero_data' if norm == 0 else 'max_iterations'
    for _ in range(max_iterations if norm else 0):
        if gamma == 0:
            reason = 'least_squares_stationary'; break
        if op.work+3*op.operation_work > max_work:
            reason = 'max_work'; break
        q = op.forward(direction); delta = float(np.vdot(q, q).real)
        if delta <= 0 or not np.isfinite(delta):
            reason = 'numerical_breakdown'; break
        alpha = gamma/delta; image += alpha*direction; r -= alpha*q
        iterations += 1; history.append(float(np.linalg.norm(r)/norm))
        if history[-1] <= tolerance:
            reason = 'data_residual'; break
        z = op.adjoint(r); next_gamma = float(np.vdot(z, z).real)
        direction = z+(next_gamma/gamma)*direction; gamma = next_gamma
    measured = float(np.linalg.norm(op.forward(image)-samples)/(norm or 1.))
    return image, dict(method='exact-centered-DFT CGLS', iterations=iterations,
        tolerance=tolerance, stop_reason=reason, converged=measured <= tolerance,
        relative_data_residual=measured, residual_history=history,
        estimated_work=op.work, estimated_memory_bytes=op.estimated_memory_bytes,
        gain_fit=False, regularization=0.,
        identifiability='not certified; data convergence does not certify image recovery')
