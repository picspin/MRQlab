"""Independent direct sums, complex images and failure gates for fast inverse."""
import importlib.util
import numpy as np
import pytest
from mrqlab_recon.nufft import RadialNUFFTOperator, radial_nufft_cgls
from mrqlab_recon.noncartesian import RadialFourierOperator
from mrqlab_recon.spatial import radial_acquire, radial_coordinates, image_quality
from mrqlab_recon.trajectories import _make_nema_like_phantom
from mrqlab_experiment.spatial_imaging import run_spatial_imaging

HAS_FINUFFT = importlib.util.find_spec('finufft') is not None
backend = pytest.mark.skipif(not HAS_FINUFFT, reason='optional mrqlab[noncartesian] dependency')


@backend
@pytest.mark.parametrize('shape', [(16,16), (17,17), (3,16,16), (4,17,17)])
def test_paired_nufft_matches_independent_direct_acquisition_and_adjoint(shape):
    rng = np.random.default_rng(39)
    image = rng.normal(size=shape)+1j*rng.normal(size=shape)
    xy, data = radial_acquire(image,32,32)
    op = RadialNUFFTOperator(xy, shape)
    forward = op.forward(image)
    assert np.linalg.norm(forward-data)/np.linalg.norm(data) < 5e-12
    probe = rng.normal(size=data.shape)+1j*rng.normal(size=data.shape)
    adjoint = op.adjoint(probe)
    reference = RadialFourierOperator(xy, shape).adjoint(probe)
    assert np.linalg.norm(adjoint-reference)/np.linalg.norm(reference) < 5e-12
    assert abs(np.vdot(forward,probe)-np.vdot(image,adjoint))/abs(np.vdot(forward,probe)) < 5e-12
    # A single displaced spin verifies axes, centering, sign and absolute scale.
    impulse=np.zeros(shape,complex); impulse[tuple(1 for _ in shape)]=2.7j
    assert op.forward(impulse) == pytest.approx(RadialFourierOperator(xy,shape).forward(impulse),abs=2e-11)


@backend
@pytest.mark.parametrize('ndim',[2,3])
def test_inverse_recovers_unscaled_complex_image_from_direct_dft_data(ndim):
    y,x=np.indices((16,16)); image=2.7*_make_nema_like_phantom(16)*np.exp(1j*(x*.13-y*.07))
    if ndim==3: image=np.stack([image,.3j*np.roll(image,2,0),1.2*image])
    xy,data=radial_acquire(image,48,32)
    recovered,d=radial_nufft_cgls(xy,data,image.shape,tolerance=1e-11)
    assert image_quality(image,recovered,1e-6)['passed']
    assert d['relative_data_residual'] < 1e-11 and d['converged']
    assert not d['gain_fit'] and d['regularization']==0.
    assert d['operator']['backend_version']=='2.5.0'
    assert d['estimated_work']<=10_000_000_000


@backend
@pytest.mark.parametrize('encoding',['radial','stack_of_stars'])
def test_family_fast_acquisition_inverse_and_replay(encoding):
    labels=(_make_nema_like_phantom(16)>.4).astype(int)
    if encoding=='stack_of_stars': labels=np.stack([labels,1-labels,np.roll(labels,2,0)])
    r=run_spatial_imaging('noncartesian',labels,encoding=encoding,spokes=48,points=32,
        reconstruction='nufft_cgls',inverse_tolerance=1e-11,max_work=10_000_000_000)
    assert r['quality']['passed']
    assert r['provenance']['acquisitions'][0]['operator']['eps']==1e-13
    replay=run_spatial_imaging(**r['provenance']['replay'])
    assert np.array_equal(replay['image'],r['image'])
    assert replay['provenance']==r['provenance']


@backend
def test_large_grid_never_allocates_dense_fourier_basis_and_has_independent_sample_checks():
    shape=(128,128); y,x=np.indices(shape)
    image=2.7*np.exp(-((x-64)**2+(y-64)**2)/180)*np.exp(1j*(.013*x-.007*y))
    xy=radial_coordinates(shape,192,256)
    with pytest.raises(ValueError,match='memory'): RadialFourierOperator(xy,shape)
    op=RadialNUFFTOperator(xy,shape)
    assert op.estimated_memory_bytes<=134217728
    data=op.forward(image)
    # Independent exact sums at 37 fixed samples across the whole trajectory.
    indices=np.r_[128,np.random.default_rng(61).choice(len(xy),36,replace=False)]; px=x.ravel()-64; py=y.ravel()-64
    reference=np.array([np.sum(image.ravel()*np.exp(-2j*np.pi*(xy[j,0]*px+xy[j,1]*py))) for j in indices])
    assert np.linalg.norm(data[0,indices]-reference)/np.linalg.norm(reference)<5e-12
    assert not hasattr(op,'basis')
    # This image-recovery experiment is explicitly a closed approximate model.
    del op
    recovered,d=radial_nufft_cgls(xy,data,shape,max_iterations=2200,tolerance=1e-10,max_work=300_000_000_000)
    assert image_quality(image,recovered,1e-6)['passed']
    assert d['relative_data_residual']<1e-10


@backend
def test_large_square_coverage_with_jitter_recovers_random_complex_image():
    n=128; rng=np.random.default_rng(27); y,x=np.indices((n,n))
    xy=np.column_stack([x.ravel()-n//2,y.ravel()-n//2])/n
    xy=(xy+rng.uniform(-.1,.1,xy.shape)/n+.5)%1-.5
    image=rng.normal(size=(n,n))+1j*rng.normal(size=(n,n))
    op=RadialNUFFTOperator(xy,image.shape); data=op.forward(image)
    indices=np.arange(0,len(xy),max(1,len(xy)//37))
    reference=np.array([np.sum(image*np.exp(-2j*np.pi*(xy[j,0]*(x-n//2)+xy[j,1]*(y-n//2)))) for j in indices])
    assert np.linalg.norm(data[0,indices]-reference)/np.linalg.norm(reference)<5e-12
    del op
    recovered,d=radial_nufft_cgls(xy,data,image.shape,max_iterations=100,tolerance=1e-10)
    assert d['converged']
    assert image_quality(image,recovered,1e-8)['passed']


@backend
def test_small_data_residual_does_not_certify_undersampled_image():
    image=_make_nema_like_phantom(16); xy,data=radial_acquire(image,2,16)
    recovered,d=radial_nufft_cgls(xy,data,image.shape,tolerance=1e-10)
    assert d['converged']
    assert not image_quality(image,recovered,.1)['passed']


@backend
def test_work_iteration_zero_and_invalid_data_diagnostics():
    image=_make_nema_like_phantom(16); xy,data=radial_acquire(image,48,32)
    _,d=radial_nufft_cgls(xy,data,image.shape,max_iterations=1)
    assert not d['converged'] and d['stop_reason']=='max_iterations'
    op=RadialNUFFTOperator(xy,image.shape)
    cap=op.work+2*op.operation_work
    recovered,d=radial_nufft_cgls(xy,data,image.shape,max_work=cap)
    assert d['stop_reason']=='max_work' and d['estimated_work']==cap
    assert np.isfinite(recovered).all()
    zero,d=radial_nufft_cgls(xy,np.zeros_like(data),image.shape)
    assert d['converged'] and d['stop_reason']=='zero_data' and not np.any(zero)
    for bad in (data.ravel(),data*np.nan):
        with pytest.raises(ValueError,match='samples'): op.adjoint(bad)


@pytest.mark.parametrize('patch',[{'eps':0.},{'eps':True},{'eps':float('nan')},
    {'max_memory_bytes':1},{'max_work':1},{'max_work':True}])
def test_invalid_options_reject_before_native_plans(patch):
    with pytest.raises(ValueError): RadialNUFFTOperator([[0,0]],(16,16),**patch)


def test_missing_backend_is_explicit_not_gridding_fallback(monkeypatch):
    import mrqlab_recon.nufft as module
    real=module.importlib.import_module
    def missing(name):
        if name=='finufft': raise ImportError('test absent backend')
        return real(name)
    monkeypatch.setattr(module.importlib,'import_module',missing)
    with pytest.raises(ValueError,match=r'install mrqlab\[noncartesian\]'):
        RadialNUFFTOperator([[0,0]],(16,16))
    with pytest.raises(ValueError,match='one tenth'):
        radial_nufft_cgls([[0,0]],[[1]],(16,16),eps=1e-8,tolerance=1e-10)
