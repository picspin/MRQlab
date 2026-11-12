import numpy as np
import pytest
from mrqlab_recon.trajectories import _make_nema_like_phantom
from mrqlab_recon.spatial import (cartesian_acquire, cartesian_reconstruct,
    radial_acquire, radial_reconstruct, image_quality)
from mrqlab_experiment.spatial_imaging import run_spatial_imaging


def labels(ndim=2):
    p = _make_nema_like_phantom(16)
    a = (p > .4).astype(int)
    return a if ndim == 2 else np.stack([a, np.roll(a, 2, 0), 1-a, a])


@pytest.mark.parametrize('shape', [(17, 19), (5, 16, 18)])
@pytest.mark.parametrize('order', ['sequential_ky', 'centric_ky', 'epi'])
def test_cartesian_complex_phantom_recovery(shape, order):
    rng = np.random.default_rng(7)
    image = rng.normal(size=shape)+1j*rng.normal(size=shape)
    indices, samples = cartesian_acquire(image, order)
    recovered = cartesian_reconstruct(indices, samples, shape)
    assert image_quality(image, recovered, 1e-12)['passed']


@pytest.mark.parametrize('chain,encoding,ndim', [
    ('cartesian_2d', 'cartesian', 2), ('partition_3d', 'cartesian', 3),
    ('noncartesian', 'radial', 2), ('noncartesian', 'stack_of_stars', 3),
    ('cest', 'cartesian', 2), ('adc', 'cartesian', 2)])
def test_spatial_clinical_simulation_reconstruction_validation_provenance(chain, encoding, ndim):
    result = run_spatial_imaging(chain, labels(ndim), encoding=encoding)
    assert result['clinical_question'] and result['quality']['passed']
    assert result['image'].shape == labels(ndim).shape
    p = result['provenance']
    assert p['physical'] and p['acquisitions'] and len(p['input_hash']) == 64
    assert all(len(a['samples_hash']) == 64 for a in p['acquisitions'])
    replay = run_spatial_imaging(**p['replay'])
    assert replay['image'] == pytest.approx(result['image'])
    assert replay['provenance']['acquisitions'] == p['acquisitions']
    if chain in {'cest', 'adc'}:
        # Every voxel, including both known tissue classes, survives k-space.
        assert result['image'] == pytest.approx(result['reference'], abs=1e-12)
        assert result['reconstructed_frames'] == pytest.approx(result['source_images'], abs=1e-12)
        assert np.ptp(result['reference']) > 1e-5
    if chain == 'adc':
        assert set(np.round(result['image'].ravel(), 7)) == {.0006, .001}


@pytest.mark.parametrize('ndim', [2, 3])
def test_radial_phantom_density_gridding_and_undersampling(ndim):
    p = _make_nema_like_phantom(24)
    image = p if ndim == 2 else np.stack([p, .5*p, np.roll(p, 3, 0), .8*p])
    xy, data = radial_acquire(image, 128, 96)
    recon = radial_reconstruct(xy, data, image.shape)
    dense = image_quality(image, recon, .2)
    xy, data = radial_acquire(image, 4, 24)
    sparse = image_quality(image, radial_reconstruct(xy, data, image.shape), .1)
    assert dense['passed']
    assert sparse['nrmse'] > dense['nrmse']
    assert not sparse['passed']


@pytest.mark.parametrize('patch', [dict(encoding='spiral'), dict(order='bad'),
    dict(max_samples=1), dict(max_work=1), dict(acceleration=0),
    dict(quality_threshold=float('nan')), dict(spokes=True)])
def test_invalid_design_and_budgets_fail(patch):
    with pytest.raises(ValueError):
        run_spatial_imaging('cartesian_2d', labels(), **patch)


def test_inconsistent_grids_and_indices_fail():
    indices, samples = cartesian_acquire(np.ones((16, 16)))
    for bad_indices, bad_samples, shape in [(indices, samples, (8, 8)),
            (indices[:, :1], samples, (16, 16)), (indices, samples[:-1], (16, 16)),
            (np.zeros_like(indices), samples, (16, 16))]:
        with pytest.raises(ValueError):
            cartesian_reconstruct(bad_indices, bad_samples, shape)
    with pytest.raises(ValueError):
        radial_reconstruct(np.zeros((20, 2)), np.zeros((2, 20)), (16, 16))
    with pytest.raises(ValueError):
        run_spatial_imaging('partition_3d', labels())


def test_cartesian_undersampling_reports_failed_quality():
    indices, samples = cartesian_acquire(_make_nema_like_phantom(24), acceleration=3)
    result = cartesian_reconstruct(indices, samples, (24, 24))
    assert not image_quality(_make_nema_like_phantom(24), result, .1)['passed']


def test_radial_positive_nyquist_endpoint_is_kept_not_dropped():
    # k-space is periodic: a sample at the +0.5 Nyquist corner maps to grid
    # index n and must wrap to index 0. Before the wrap fix the interpolation
    # corner fell outside [0, n) and was silently discarded, so an
    # endpoint-only input reconstructed to an all-zero image.
    n = 16
    endpoint_only = radial_reconstruct(np.array([[.5, 0.]]), np.array([[1 + 0j]]), (n, n))
    assert np.abs(endpoint_only).max() > 0
    # The endpoint must actually change the image, not vanish.
    without_endpoint = radial_reconstruct(np.array([[0., 0.]]), np.array([[1 + 0j]]), (n, n))
    assert not np.allclose(endpoint_only, without_endpoint)


def test_cartesian_work_exceeds_sample_count_and_bounds_reconstruction():
    # Cartesian reconstruction is an FFT per frame, so estimated_work must not
    # collapse to estimated_samples and max_work must be able to reject a budget
    # below the reconstruction cost.
    result = run_spatial_imaging('cartesian_2d', labels())
    provenance = result['provenance']
    assert provenance['estimated_work'] > provenance['estimated_samples']
    with pytest.raises(ValueError):
        run_spatial_imaging('cartesian_2d', labels(), max_work=provenance['estimated_work'] - 1)
    # The non-Cartesian direct-DFT work model is unchanged by the Cartesian fix.
    radial = run_spatial_imaging('noncartesian', labels(), encoding='radial')
    n = labels().shape[-1]
    assert radial['provenance']['estimated_work'] == radial['provenance']['estimated_samples']*n*n
