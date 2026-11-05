"""Matrix-free FINUFFT radial/Cartesian-kz operator and bounded CGLS inverse.

Type 1 is an adjoint, not an inverse. No density compensation, gain fitting,
regularization, image prior or hidden fallback to direct DFT is used here.
"""
import importlib
import numpy as np
from .spatial import validate_image
from .noncartesian import _cgls


def _backend():
    try:
        return importlib.import_module('finufft')
    except ImportError as exc:
        raise ValueError('FINUFFT backend unavailable; install mrqlab[noncartesian]') from exc


class RadialNUFFTOperator:
    """Unnormalized centered Fourier sum approximated by paired CPU NUFFTs.

    xy is (kx, ky), cycles/pixel; array axes are (z, y, x). Fixed single-thread,
    complex128, centered modes and oversampling 2 make the numerical method
    explicit. Memory/work limits are conservative planning estimates, not native
    allocator/RSS or wall-time guarantees. No M by N² array is allocated.
    """
    def __init__(self, xy, shape, *, eps=1e-13, max_work=10000000000,
                 max_memory_bytes=134217728):
        self.shape = tuple(shape)
        if len(self.shape) not in (2, 3) or any(type(n) is not int or n < 2 for n in self.shape) or self.shape[-2] != self.shape[-1]:
            raise ValueError('square 2D/3D grid required')
        for budget in (max_work, max_memory_bytes):
            if type(budget) is not int or budget <= 0:
                raise ValueError('positive integer budget required')
        if isinstance(eps, bool) or not np.isfinite(eps) or not 1e-14 <= eps <= 1e-3:
            raise ValueError('NUFFT eps must be between 1e-14 and 1e-3')
        coords = np.asarray(xy)
        if coords.ndim != 2 or coords.shape[1] != 2 or len(coords) == 0 or np.iscomplexobj(coords):
            raise ValueError('finite nonempty real kx/ky coordinates required')
        if not np.isfinite(coords).all() or np.any(abs(coords) > .5):
            raise ValueError('finite kx/ky within Nyquist required')
        self.nz = self.shape[0] if len(self.shape) == 3 else 1
        n = self.shape[-1]; m = len(coords); voxels = n*n
        self.sample_shape = (self.nz, m)
        # Guard before making plans. Allow smooth FFT sizes up to 4*n or 64,
        # two plans, sorting/coordinates, CG vectors and native-plan overhead.
        grid = max(4*n, 64)**2
        self.estimated_memory_bytes = 33554432 + 256*grid + 256*self.nz*(m+voxels)
        if self.estimated_memory_bytes > max_memory_bytes:
            raise ValueError('NUFFT estimated memory budget exceeded')
        width = int(np.ceil(-np.log10(eps)))+6
        self.operation_work = self.nz*(m*width**2 + int(5*grid*np.ceil(np.log2(grid)))) + int(2*self.nz*voxels*np.ceil(np.log2(max(2, self.nz))))
        self.max_work = max_work; self.work = 0; self.eps = float(eps)
        self._charge(2*self.operation_work)
        finufft = _backend(); self.backend_version = finufft.__version__
        self.xy = np.array(coords, dtype=float, copy=True)
        self.xy.flags.writeable = False
        self.ky = np.ascontiguousarray(2*np.pi*self.xy[:, 1])
        self.kx = np.ascontiguousarray(2*np.pi*self.xy[:, 0])
        options = dict(n_trans=1, eps=self.eps, dtype='complex128',
                       modeord=0, nthreads=1, upsampfac=2., fftw=64)
        # Swapped coordinate arguments follow NumPy (y,x) array ordering.
        self._forward = finufft.Plan(2, (n, n), isign=-1, **options)
        self._adjoint = finufft.Plan(1, (n, n), isign=1, **options)
        self._forward.setpts(self.ky, self.kx)
        self._adjoint.setpts(self.ky, self.kx)

    def _charge(self, count):
        if self.work+count > self.max_work:
            raise ValueError('NUFFT estimated work budget exceeded')
        self.work += count

    def forward(self, image):
        image = validate_image(image)
        if image.shape != self.shape:
            raise ValueError('inconsistent image dimensions')
        self._charge(self.operation_work)
        planes = image.reshape(self.nz, *self.shape[-2:])
        if len(self.shape) == 3:
            planes = np.fft.fftshift(np.fft.fft(np.fft.ifftshift(planes, axes=0), axis=0), axes=0)
        return np.stack([self._forward.execute(np.ascontiguousarray(plane)) for plane in planes])

    def adjoint(self, samples):
        samples = np.asarray(samples, complex)
        if samples.shape != self.sample_shape or not np.isfinite(samples).all():
            raise ValueError('inconsistent finite complex samples')
        self._charge(self.operation_work)
        planes = np.stack([self._adjoint.execute(np.ascontiguousarray(row)) for row in samples])
        if len(self.shape) == 3:
            planes = self.nz*np.fft.fftshift(np.fft.ifft(np.fft.ifftshift(planes, axes=0), axis=0), axes=0)
        return planes.reshape(self.shape)

    def diagnostics(self):
        return dict(backend='finufft', backend_version=self.backend_version,
                    eps=self.eps, dtype='complex128', nthreads=1, modeord=0,
                    upsampfac=2., normalization='unnormalized centered Fourier sum',
                    budget_model='nufft-plan-proxy-v1; estimates, not native RSS/time guarantees')


def radial_nufft_cgls(xy, samples, shape, *, max_iterations=1500, tolerance=1e-10,
                       eps=1e-13, max_work=10000000000, max_memory_bytes=134217728):
    """Unregularized matrix-free inverse; convergence uses a fresh data residual.

    eps is transform accuracy, not an image error bound. Ask for eps at least
    10 times smaller than solver tolerance. Ill conditioning/undersampling can
    still give a tiny residual and an inaccurate image; validate separately.
    """
    if type(max_iterations) is not int or max_iterations < 1:
        raise ValueError('positive integer iteration limit required')
    if isinstance(tolerance, bool) or not np.isfinite(tolerance) or not 0 < tolerance < 1:
        raise ValueError('relative data tolerance must lie between zero and one')
    if not np.isfinite(eps) or eps > tolerance*.1:
        raise ValueError('NUFFT eps must be at most one tenth of inverse tolerance')
    op = RadialNUFFTOperator(xy, shape, eps=eps, max_work=max_work, max_memory_bytes=max_memory_bytes)
    samples = np.asarray(samples, complex)
    if samples.shape != op.sample_shape or not np.isfinite(samples).all():
        raise ValueError('inconsistent finite complex samples')
    if op.work+2*op.operation_work > max_work:
        raise ValueError('insufficient work for inverse initialization and validation')
    image, diagnostic = _cgls(op, samples, max_iterations, tolerance, 'FINUFFT centered Fourier CGLS')
    diagnostic['operator'] = op.diagnostics()
    return image, diagnostic
