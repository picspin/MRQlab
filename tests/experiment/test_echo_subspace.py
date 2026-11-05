import importlib.util
import numpy as np
import pytest
from mrqlab_recon.echo_subspace import EchoSubspaceOperator, echo_subspace_cgls

HAS_NUFFT=importlib.util.find_spec('finufft') is not None
BACKENDS=['exact']+(['finufft'] if HAS_NUFFT else [])


def independent_matrix(xy,shape,weights):
    """Explicit physical voxel/kz sum, without package Fourier/FFT helpers."""
    nz=shape[0] if len(shape)==3 else 1
    coords=list(np.ndindex(shape));out=np.empty((nz*len(xy),len(weights)*len(coords)),complex)
    for zfreq in range(nz):
        for m,(kx,ky) in enumerate(xy):
            for k in range(len(weights)):
                for index,coord in enumerate(coords):
                    z,y,x=coord if len(shape)==3 else (0,*coord)
                    phase=kx*(x-shape[-1]//2)+ky*(y-shape[-2]//2)
                    if len(shape)==3: phase+=(zfreq-nz//2)*(z-nz//2)/nz
                    out[zfreq*len(xy)+m,k*len(coords)+index]=weights[k,m]*np.exp(-2j*np.pi*phase)
    return out


@pytest.mark.parametrize('backend',BACKENDS)
@pytest.mark.parametrize('shape',[(5,5),(2,5,5),(3,4,4)])
def test_full_complex_forward_adjoint_and_pair_match_independent_voxel_sums(backend,shape):
    rng=np.random.default_rng(791);xy=rng.uniform(-.5,.5,(31,2));w=rng.normal(size=(2,31))+1j*rng.normal(size=(2,31))
    op=EchoSubspaceOperator(xy,shape,w,backend=backend)
    c=2.3*(rng.normal(size=op.shape)+1j*rng.normal(size=op.shape))
    b=rng.normal(size=op.sample_shape)+1j*rng.normal(size=op.sample_shape)
    a=independent_matrix(xy,shape,w)
    assert op.forward(c).ravel()==pytest.approx(a@c.ravel(),abs=1e-10)
    assert op.adjoint(b).ravel()==pytest.approx(a.conj().T@b.ravel(),abs=1e-10)
    assert np.vdot(op.forward(c),b)==pytest.approx(np.vdot(c,op.adjoint(b)),abs=1e-9)


@pytest.mark.parametrize('backend',BACKENDS)
@pytest.mark.parametrize('shape',[(5,5),(3,4,4)])
def test_unscaled_complex_inverse_from_independent_full_frequency_echo_data(backend,shape):
    n=shape[-1];yy,xx=np.meshgrid((np.arange(n)-n//2)/n,(np.arange(n)-n//2)/n,indexing='ij')
    xy=np.tile(np.column_stack([xx.ravel(),yy.ravel()]),(3,1))
    w=np.repeat(np.array([[1.,.7,.4],[.4,.8,1.]]),n*n,axis=1)
    rng=np.random.default_rng(64);c=3.7*(rng.normal(size=(2,*shape))+1j*rng.normal(size=(2,*shape)))
    samples=(independent_matrix(xy,shape,w)@c.ravel()).reshape((-1,len(xy)))
    result,d=echo_subspace_cgls(xy,samples,shape,w,backend=backend)
    assert result==pytest.approx(c,abs=1e-9)
    assert d['converged'] and not d['gain_fit'] and d['regularization']==0.
    assert d['operator']['spatial_support']=='not supplied'


def test_temporal_rank_alone_does_not_prove_spatial_identifiability():
    xy=np.zeros((30,2));w=np.array([np.linspace(.1,1,30),np.linspace(1,.1,30)])
    c=np.zeros((2,5,5),complex);c[0,1,2]=3.4;c[1,3,2]=-1.2j
    b=(independent_matrix(xy,(5,5),w)@c.ravel()).reshape(1,-1)
    result,d=echo_subspace_cgls(xy,b,(5,5),w)
    assert d['converged'] and np.linalg.norm(result-c)/np.linalg.norm(c)>.9


def test_work_stop_and_preallocation_memory_rejection(monkeypatch):
    import mrqlab_recon.echo_subspace as module
    xy=np.random.default_rng(8).uniform(-.5,.5,(50,2));w=np.array([np.linspace(.1,1,50),np.linspace(1,.1,50)])
    c=np.ones((2,5,5),complex);op=EchoSubspaceOperator(xy,(5,5),w);samples=op.forward(c)
    r,d=echo_subspace_cgls(xy,samples,(5,5),w,max_work=15000)
    assert d['stop_reason']=='max_work' and not d['converged'] and np.isfinite(r).all()
    def never(*args,**kwargs): raise AssertionError('Fourier allocation must not happen')
    monkeypatch.setattr(module,'RadialFourierOperator',never)
    with pytest.raises(ValueError,match='memory'): EchoSubspaceOperator(xy,(5,5),w,max_memory_bytes=1)


@pytest.mark.parametrize('patch',[{'weights':np.ones((2,50))},{'weights':np.ones((2,3))},
    {'backend':'unknown'},{'max_work':True},{'max_memory_bytes':True}])
def test_invalid_operator_inputs(patch):
    kwargs=dict(xy=np.zeros((50,2)),spatial_shape=(5,5),weights=np.array([np.linspace(.1,1,50),np.linspace(1,.1,50)]))
    with pytest.raises(ValueError): EchoSubspaceOperator(**(kwargs|patch))
