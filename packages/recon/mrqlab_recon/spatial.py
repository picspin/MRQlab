"""Ideal Fourier encoding. Array axes are (z, y, x) or (y, x).

Radial sampling uses the actual discrete Fourier sum, not rounded FFT samples.
Linear splatting with radial |k| density weights is approximate, without kernel
 deapodization. kz remains Cartesian and is inverse transformed after gridding.
"""
import numpy as np
from .trajectories import TrajectorySpec, generate_trajectory


def fft_image(image):
    return np.fft.fftshift(np.fft.fftn(np.fft.ifftshift(image)))


def ifft_image(data):
    return np.fft.fftshift(np.fft.ifftn(np.fft.ifftshift(data)))


def validate_image(image):
    image = np.asarray(image, complex)
    if image.ndim not in (2, 3) or min(image.shape) < 2 or not np.isfinite(image).all():
        raise ValueError('finite 2D/3D image required')
    return image


def cartesian_indices(shape, order='sequential_ky', acceleration=1):
    if order not in {'sequential_ky', 'centric_ky', 'epi'} or type(acceleration) is not int or acceleration < 1:
        raise ValueError('invalid encoding')
    nz, ny, nx = (1, *shape) if len(shape) == 2 else shape
    lines = list(range(0, ny, acceleration))
    if order == 'centric_ky':
        lines.sort(key=lambda y: (abs(y-ny//2), y))
    return np.array([(z, y, x) for z in range(nz) for i, y in enumerate(lines)
                     for x in (range(nx-1, -1, -1) if order == 'epi' and i % 2 else range(nx))])[:, -len(shape):]


def cartesian_acquire(image, order='sequential_ky', acceleration=1):
    image = validate_image(image)
    indices = cartesian_indices(image.shape, order, acceleration)
    return indices, fft_image(image)[tuple(indices.T)]


def cartesian_reconstruct(indices, samples, shape):
    indices = np.asarray(indices); samples = np.asarray(samples)
    if len(shape) not in (2, 3) or any(type(n) is not int or n < 2 for n in shape):
        raise ValueError('invalid grid shape')
    if indices.ndim != 2 or indices.shape != (samples.size, len(shape)) or samples.ndim != 1 or indices.dtype.kind not in 'iu':
        raise ValueError('inconsistent grid dimensions')
    if not np.isfinite(samples).all() or np.any(indices < 0) or np.any(indices >= np.array(shape)) or len(np.unique(indices, axis=0)) != len(indices):
        raise ValueError('invalid or repeated encoding indices')
    grid = np.zeros(shape, complex); grid[tuple(indices.T)] = samples
    return ifft_image(grid)


def radial_acquire(image, spokes, points):
    image = validate_image(image)
    n = image.shape[-1]
    if image.shape[-2] != n or n < 16:
        raise ValueError('radial requires square grid >=16')
    spec = TrajectorySpec(trajectory_type='radial', matrix_size=n,
                          num_spokes_or_interleaves=spokes, points_per_arm=points)
    trajectory = generate_trajectory(spec)
    # cycles/pixel; exclude positive Nyquist endpoint symmetry issues.
    xy = np.column_stack([trajectory['kx'], trajectory['ky']]) * .5
    pos = (np.arange(n)-n//2)
    xx, yy = np.meshgrid(pos, pos)
    # Bounded chunks avoid materializing samples x voxels for large spokes.
    planes = image[None] if image.ndim == 2 else image
    kz_planes = np.fft.fftshift(np.fft.fft(np.fft.ifftshift(planes, axes=0), axis=0), axes=0) if image.ndim == 3 else planes
    data = np.empty((len(planes), len(xy)), complex)
    for start in range(0, len(xy), 256):
        k = xy[start:start+256]
        basis = np.exp(-2j*np.pi*(k[:, 0, None]*xx.ravel()+k[:, 1, None]*yy.ravel()))
        data[:, start:start+256] = kz_planes.reshape(len(planes), -1) @ basis.T
    return xy, data


def radial_reconstruct(xy, samples, shape):
    xy = np.asarray(xy, float); samples = np.asarray(samples, complex)
    if len(shape) not in (2, 3) or min(shape) < 2 or shape[-1] != shape[-2]:
        raise ValueError('invalid radial grid')
    n = shape[-1]; nz = shape[0] if len(shape) == 3 else 1
    if xy.ndim != 2 or xy.shape[1] != 2 or samples.shape != (nz, len(xy)) or not np.isfinite(xy).all() or not np.isfinite(samples).all() or np.any(abs(xy) > .5):
        raise ValueError('inconsistent radial grid dimensions or coordinates')
    coords = xy*n+n//2; base = np.floor(coords).astype(int); fraction = coords-base
    density = np.maximum(np.linalg.norm(xy, axis=1), 1/(2*n))
    grid = np.zeros((nz, n, n), complex); weights = np.zeros((n, n))
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        x = base[:, 0]+dx; y = base[:, 1]+dy
        w = density*(fraction[:, 0] if dx else 1-fraction[:, 0])*(fraction[:, 1] if dy else 1-fraction[:, 1])
        valid = (x >= 0) & (x < n) & (y >= 0) & (y < n)
        np.add.at(weights, (y[valid], x[valid]), w[valid])
        for z in range(nz):
            np.add.at(grid[z], (y[valid], x[valid]), samples[z, valid]*w[valid])
    mask = weights > 0
    grid[:, mask] /= weights[mask]
    # Local density-normalized interpolation, not a NUFFT or iterative inversion.
    return ifft_image(grid if len(shape) == 3 else grid[0])


def image_quality(reference, reconstructed, threshold):
    reference = validate_image(reference); reconstructed = validate_image(reconstructed)
    if reference.shape != reconstructed.shape or not np.isfinite(threshold) or threshold <= 0:
        raise ValueError('inconsistent quality grid or threshold')
    norm = np.linalg.norm(reference)
    if norm == 0:
        raise ValueError('nonzero reference required')
    error = reconstructed-reference
    nrmse = float(np.linalg.norm(error)/norm)
    return dict(nrmse=nrmse, max_absolute_error=float(np.max(abs(error))), threshold=threshold, passed=nrmse <= threshold)
