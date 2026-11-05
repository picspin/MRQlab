import numpy as np
import pytest
from mrqlab_recon.noncartesian import RadialFourierOperator, radial_cgls
from mrqlab_recon.spatial import radial_acquire, radial_reconstruct, image_quality
from mrqlab_recon.trajectories import _make_nema_like_phantom
from mrqlab_experiment.spatial_imaging import run_spatial_imaging


@pytest.mark.parametrize('shape', [(16, 16), (3, 16, 16), (4, 17, 17)])
def test_exact_operator_matches_acquisition_and_hermitian_adjoint(shape):
    rng = np.random.default_rng(17)
    image = rng.normal(size=shape)+1j*rng.normal(size=shape)
    xy, data = radial_acquire(image, 32, 32)
    op = RadialFourierOperator(xy, shape)
    assert op.forward(image) == pytest.approx(data, abs=1e-11)
    probe = rng.normal(size=data.shape)+1j*rng.normal(size=data.shape)
    assert np.vdot(op.forward(image), probe) == pytest.approx(np.vdot(image, op.adjoint(probe)), rel=1e-12)


@pytest.mark.parametrize('ndim', [2, 3])
def test_complex_amplitude_recovery_without_gain_fit(ndim):
    y, x = np.indices((16, 16))
    image = 2.7*_make_nema_like_phantom(16)*np.exp(1j*(x*.13-y*.07))
    if ndim == 3:
        image = np.stack([image, .3j*np.roll(image, 2, 0), 1.2*image])
    xy, data = radial_acquire(image, 48, 32)
    baseline = radial_reconstruct(xy, data, image.shape)
    recovered, d = radial_cgls(xy, data, image.shape)
    assert image_quality(image, recovered, 1e-6)['passed']
    assert np.linalg.norm(recovered-image) < np.linalg.norm(baseline-image)*1e-5
    assert d['converged'] and not d['gain_fit'] and d['regularization'] == 0
    assert d['estimated_work'] < 10000000000
    assert d['relative_data_residual'] < 1e-12
    assert len(d['residual_history']) == d['iterations']+1


@pytest.mark.parametrize('ndim', [2, 3])
def test_family_chain_iterative_inverse_quality_and_replay(ndim):
    labels = (_make_nema_like_phantom(16) > .4).astype(int)
    if ndim == 3:
        labels = np.stack([labels, 1-labels, np.roll(labels, 2, 0)])
    r = run_spatial_imaging('noncartesian', labels,
        encoding='radial' if ndim == 2 else 'stack_of_stars', spokes=48, points=32,
        reconstruction='cgls', max_work=10000000000)
    assert r['quality']['passed'] and r['quality']['threshold'] == 1e-6
    assert r['solvers'][0]['converged']
    replay = run_spatial_imaging(**r['provenance']['replay'])
    assert replay['image'] == pytest.approx(r['image'], abs=1e-12)
    assert replay['provenance'] == r['provenance']


def test_undersampling_has_small_data_residual_but_fails_image_quality():
    image = _make_nema_like_phantom(16)
    xy, data = radial_acquire(image, 2, 16)
    recovered, d = radial_cgls(xy, data, image.shape)
    assert d['converged']
    assert not image_quality(image, recovered, .1)['passed']


def test_iteration_and_work_exhaustion_return_honest_diagnostics():
    image = _make_nema_like_phantom(16)
    xy, data = radial_acquire(image, 48, 32)
    one, d = radial_cgls(xy, data, image.shape, max_iterations=1)
    assert not d['converged'] and d['stop_reason'] == 'max_iterations'
    assert not image_quality(image, one, 1e-6)['passed']
    bounded, d = radial_cgls(xy, data, image.shape, max_work=2000000)
    assert not d['converged'] and d['stop_reason'] == 'max_work'
    assert d['estimated_work'] <= 2000000
    assert np.isfinite(bounded).all()


@pytest.mark.parametrize('patch', [dict(max_iterations=True), dict(max_iterations=0),
    dict(tolerance=0), dict(tolerance=float('nan')), dict(max_work=1),
    dict(max_memory_bytes=1), dict(max_work=True)])
def test_invalid_inverse_and_preallocation_budgets_fail(patch):
    xy, data = radial_acquire(np.ones((16, 16)), 16, 16)
    with pytest.raises(ValueError):
        radial_cgls(xy, data, (16, 16), **patch)


@pytest.mark.parametrize('xy,shape', [([], (16, 16)), ([[float('nan'), 0]], (16, 16)),
    ([[.6, 0]], (16, 16)), ([[0, 0]], (16, 15)), ([[0, 0]], (True, 16))])
def test_invalid_operator_coordinates_and_shapes(xy, shape):
    with pytest.raises(ValueError): RadialFourierOperator(xy, shape)


def test_zero_signal_and_inconsistent_samples():
    op = RadialFourierOperator([[0, 0]], (16, 16))
    image, d = radial_cgls([[0, 0]], np.zeros((1, 1)), (16, 16))
    assert not np.any(image) and d['converged'] and d['stop_reason'] == 'zero_data'
    for samples in (np.zeros(1), [[complex('nan')]]):
        with pytest.raises(ValueError): op.adjoint(samples)


# Adapted from Claude hand-off e1574a8; retain the original strict image target.

def test_grid_32_stops_honestly_at_iterations_and_beats_gridding():
    image = _make_nema_like_phantom(32)
    xy, data = radial_acquire(image, 48, 32)
    recovered, d = radial_cgls(xy, data, (32, 32))
    # 1500 iterations need ~5.3 billion work < 10 billion default budget, so
    # the default stop is iteration exhaustion; convergence is not claimed.
    assert d['stop_reason'] == 'max_iterations' and not d['converged']
    assert not d['gain_fit'] and d['regularization'] == 0
    assert d['estimated_memory_bytes'] < 134217728
    # Iteration exhaustion leaves real image error: ~0.087 NRMSE on this
    # phantom, far outside the 16x16 1e-6 regime but still ahead of gridding.
    assert not image_quality(image, recovered, 1e-6)['passed']
    baseline = radial_reconstruct(xy, data, (32, 32))
    assert np.linalg.norm(recovered-image) < np.linalg.norm(baseline-image)/2


def test_grid_3d_32_hits_work_budget_inside_default_memory_cap():
    image = _make_nema_like_phantom(32)
    image = np.stack([image, .3j*np.roll(image, 2, 0), 1.2*image])
    xy, data = radial_acquire(image, 48, 32)
    recovered, d = radial_cgls(xy, data, (3, 32, 32), max_work=10000000000)
    # 1500 iterations would need ~14.2 billion work > 10 billion budget, so
    # the stop is work exhaustion; the 96.9 MiB estimate fits the 128 MiB cap.
    assert d['stop_reason'] == 'max_work' and not d['converged']
    assert d['estimated_work'] <= 10000000000
    assert d['estimated_memory_bytes'] < 134217728
    assert np.isfinite(recovered).all()
    assert not image_quality(image, recovered, 1e-6)['passed']


def test_memory_cap_rejects_large_3d_grid_before_solve():
    xy, data = radial_acquire(_make_nema_like_phantom(48), 32, 32)
    # ~228 MB estimate exceeds the 128 MiB default cap before any iteration.
    with pytest.raises(ValueError, match='memory budget'):
        radial_cgls(xy, data, (3, 48, 48))
    with pytest.raises(ValueError, match='memory budget'):
        RadialFourierOperator(xy, (3, 48, 48))


def test_family_chain_grid_32_retains_strict_target_failure_and_replay():
    labels = (_make_nema_like_phantom(32) > .4).astype(int)
    r = run_spatial_imaging('noncartesian', labels, encoding='radial',
        spokes=48, points=32, reconstruction='cgls', max_work=10000000000,
        quality_threshold=1e-6)
    assert not r['quality']['passed'] and r['quality']['threshold'] == 1e-6
    assert r['solvers'][0]['stop_reason'] == 'max_iterations'
    assert not r['solvers'][0]['converged']
    replay = run_spatial_imaging(**r['provenance']['replay'])
    assert replay['image'] == pytest.approx(r['image'], abs=1e-12)
    assert replay['provenance'] == r['provenance']
