"""Paired temporal-basis Fourier encoding; no image support or gain fitting.

Known temporal signal curves are model priors. Unknowns are independent complex
coefficient images, not known segmentation masks. Temporal rank does not certify
spatial identifiability. Exact DFT and optional FINUFFT are distinct backends.
"""
import numpy as np
from .noncartesian import RadialFourierOperator, _cgls
from .nufft import RadialNUFFTOperator


class EchoSubspaceOperator:
    def __init__(self, xy, spatial_shape, weights, *, backend='exact', eps=1e-13,
                 max_work=10000000000, max_memory_bytes=134217728):
        weights = np.asarray(weights, complex)
        if (weights.ndim != 2 or not 1 <= len(weights) <= 4 or
                weights.shape[1] != len(xy) or not np.isfinite(weights).all()):
            raise ValueError('one to four finite temporal weight rows, one column per xy sample required')
        singular = np.linalg.svd(weights, compute_uv=False)
        if singular[-1] <= singular[0]*1e-10:
            raise ValueError('temporal basis is rank deficient or ill conditioned')
        if backend not in {'exact', 'finufft'}:
            raise ValueError('exact or finufft backend required')
        if type(max_memory_bytes) is not int or max_memory_bytes <= 0:
            raise ValueError('positive integer memory budget required')
        spatial_shape = tuple(spatial_shape)
        if len(spatial_shape) not in (2, 3) or any(type(n) is not int or n < 2 for n in spatial_shape):
            raise ValueError('square 2D/3D spatial shape required')
        k = len(weights); nz = spatial_shape[0] if len(spatial_shape) == 3 else 1
        # Additional coefficient CG vectors and weighted data temporaries, before
        # the underlying dense basis or native plans can be created.
        extra = 128*k*int(np.prod(spatial_shape)) + 64*k*nz*len(xy) + weights.nbytes
        if extra >= max_memory_bytes:
            raise ValueError('subspace memory budget exceeded')
        kwargs = dict(max_work=max_work, max_memory_bytes=max_memory_bytes-extra)
        self.fourier = (RadialFourierOperator(xy, spatial_shape, **kwargs) if backend == 'exact'
                        else RadialNUFFTOperator(xy, spatial_shape, eps=eps, **kwargs))
        self.weights = weights.copy(); self.weights.flags.writeable = False
        self.spatial_shape = spatial_shape; self.shape = (k, *spatial_shape)
        self.sample_shape = self.fourier.sample_shape; self.max_work = max_work
        self.weight_work = k*nz*len(xy)
        self.operation_work = k*self.fourier.operation_work+self.weight_work
        self.estimated_memory_bytes = self.fourier.estimated_memory_bytes+extra
        self.backend = backend; self.temporal_condition = float(singular[0]/singular[-1])

    @property
    def work(self):
        return self.fourier.work

    def forward(self, coefficients):
        coefficients = np.asarray(coefficients, complex)
        if coefficients.shape != self.shape or not np.isfinite(coefficients).all():
            raise ValueError('finite complex coefficient maps matching declared basis required')
        # Reserve a whole operation so a budget failure cannot occur mid-sum.
        if self.work+self.operation_work > self.max_work:
            raise ValueError('subspace work budget exceeded')
        self.fourier._charge(self.weight_work)
        return sum(w*self.fourier.forward(c) for w, c in zip(self.weights, coefficients))

    def adjoint(self, samples):
        samples = np.asarray(samples, complex)
        if samples.shape != self.sample_shape or not np.isfinite(samples).all():
            raise ValueError('finite complex sample array matching acquisition required')
        if self.work+self.operation_work > self.max_work:
            raise ValueError('subspace work budget exceeded')
        self.fourier._charge(self.weight_work)
        return np.array([self.fourier.adjoint(w.conj()*samples) for w in self.weights])

    def diagnostics(self):
        return dict(backend=self.backend, temporal_condition=self.temporal_condition,
            components=len(self.weights), spatial_shape=list(self.spatial_shape),
            fourier=self.fourier.diagnostics() if self.backend == 'finufft' else
                dict(backend='exact-centered-DFT', normalization='unnormalized Fourier sum'),
            model='sum_k weights[k,m] * Fourier(coefficients[k])[kz,m]',
            gain_fit=False, regularization=0., spatial_support='not supplied')


def echo_subspace_cgls(xy, samples, spatial_shape, weights, *, backend='exact',
                       max_iterations=2000, tolerance=1e-10, eps=1e-13,
                       max_work=10000000000, max_memory_bytes=134217728):
    if type(max_iterations) is not int or max_iterations < 1:
        raise ValueError('positive integer iteration limit required')
    if isinstance(tolerance, bool) or not np.isfinite(tolerance) or not 0 < tolerance < 1:
        raise ValueError('relative data tolerance between zero and one required')
    if backend == 'finufft' and (not np.isfinite(eps) or eps > tolerance/10):
        raise ValueError('NUFFT eps must be at most one tenth of inverse tolerance')
    op = EchoSubspaceOperator(xy, spatial_shape, weights, backend=backend, eps=eps,
                             max_work=max_work, max_memory_bytes=max_memory_bytes)
    samples = np.asarray(samples, complex)
    if samples.shape != op.sample_shape or not np.isfinite(samples).all():
        raise ValueError('finite complex sample array matching acquisition required')
    if op.work+2*op.operation_work > max_work:
        raise ValueError('insufficient work for subspace initialization and validation')
    coefficients, diagnostic = _cgls(op, samples, max_iterations, tolerance, 'temporal-basis Fourier CGLS')
    diagnostic['operator'] = op.diagnostics()
    return coefficients, diagnostic
