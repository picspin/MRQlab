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
