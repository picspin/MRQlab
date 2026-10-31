import numpy as np
import pytest
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from mrqlab_recon.readout_encoding import ReadoutEncodingOperator,readout_cgls
from mrqlab_experiment.radial_tse import run_radial_tse


def phantom():
    y,x=np.indices((16,16));return (((x-8)**2+(y-8)**2<20)|((x==3)&(y>3))).astype(int)


@pytest.mark.parametrize('shape',[(4,4),(2,4,4),(3,4,4)])
def test_complete_complex_forward_adjoint_and_inner_product_against_independent_voxel_sums(shape):
    rng=np.random.default_rng(71);m=61;k=rng.uniform(-.45,.45,(m,len(shape)));times=rng.uniform(-.002,.002,m)
    field=rng.uniform(-150,150,shape);coils=rng.normal(size=(2,*shape))+1j*rng.normal(size=(2,*shape))
    weights=rng.normal(size=(2,m))+1j*rng.normal(size=(2,m));x=rng.normal(size=(2,*shape))+1j*rng.normal(size=(2,*shape));b=rng.normal(size=(2,m))+1j*rng.normal(size=(2,m))
    op=ReadoutEncodingOperator(k,shape,weights,times,field,coils)
    reference=np.zeros((2,m),complex);adjoint=np.zeros_like(x)
    for index in np.ndindex(shape):
        position=np.array(index)-np.array(shape)//2
        phase=np.exp(-2j*np.pi*(k@position)+2j*np.pi*field[index]*times)
        for c in range(2):
            for j in range(2):
                a=coils[(c,*index)]*weights[j]*phase
                reference[c]+=a*x[(j,*index)];adjoint[(j,*index)]+=np.vdot(a,b[c])
    forward=op.forward(x);back=op.adjoint(b)
    assert forward==pytest.approx(reference,abs=2e-13)
    assert back==pytest.approx(adjoint,abs=2e-13)
    assert np.vdot(forward,b)==pytest.approx(np.vdot(x,back),abs=2e-12)


def test_independent_dense_lstsq_recovers_arbitrary_complex_maps_without_spatial_truth():
    rng=np.random.default_rng(41);shape=(4,4);m=150;k=rng.uniform(-.5,.5,(m,2));times=rng.uniform(-.002,.002,m)
    field=rng.uniform(-130,130,shape);coils=rng.normal(size=(2,*shape))+1j*rng.normal(size=(2,*shape));weights=rng.normal(size=(2,m))+1j*rng.normal(size=(2,m))
    positions=np.stack(np.meshgrid(np.arange(4)-2,np.arange(4)-2,indexing='ij'),axis=-1).reshape(16,2)
    matrix=np.vstack([np.hstack([w[:,None]*coil.ravel()*np.exp(-2j*np.pi*(k@positions.T)+2j*np.pi*times[:,None]*field.ravel()) for w in weights]) for coil in coils])
    truth=rng.normal(size=32)+1j*rng.normal(size=32);data=(matrix@truth).reshape(2,m)
    ref=np.linalg.lstsq(matrix,data.ravel(),rcond=None)[0]
    recovered,diag=readout_cgls(k,data,shape,weights,times,field,coils,max_iterations=300,tolerance=1e-12)
    assert recovered.ravel()==pytest.approx(ref,abs=1e-10)
    assert recovered.ravel()==pytest.approx(truth,abs=1e-10)
    assert diag['converged'] and not diag['gain_fit'] and diag['regularization']==0
    assert 'not supplied' in diag['operator']['spatial_support']


@pytest.fixture(scope='module')
def finite_run(): return run_radial_tse(phantom(),readout_model='finite_adc',component_phase_rad=[.2,-.6])


def independent_bloch_adc(run):
    """Actual hard RF rotations/free Bloch/physical gradient intervals per train."""
    shape=run['reference'].shape;n=shape[-1];v=int(np.prod(shape));read=run['readout'];p=run['design']
    axes=[(np.arange(side)-side//2)*p['fov_m']/side for side in shape]
    grids=np.meshgrid(*axes,indexing='ij');xyz=np.array([grids[-1].ravel(),grids[-2].ravel(),grids[0].ravel() if len(shape)==3 else np.zeros(v)])
    field=read['field_hz'].ravel();sens=read['coil_sensitivities'].reshape(p['coil_count'],v);result=np.zeros_like(run['samples'])
    for tissue_index,tissue in enumerate(run['experiment']['tissue']):
        t1=tissue['t1'];t2=p['t2_s'][tissue_index];pd=tissue['proton_density'];z=0.;at=0.
        for rf in np.arange(p['echoes'])*p['echo_spacing_s']+p['echo_spacing_s']/2:
            z=pd+(z-pd)*np.exp(-(rf-at)/t1);z=-z;at=rf
        z0=pd+(z-pd)*np.exp(-(p['tr_s']-at)/t1)
        mask=run['reference_components'][tissue_index].ravel()
        for train in run['timeline']:
            m=np.full(v,-1j*z0);mz=np.full(v,0.);time=0.
            def free(end,gradient=(0.,0.,0.)):
                nonlocal m,mz,time
                dt=end-time;assert dt>=-1e-14
                m=m*np.exp(-dt/t2+2j*np.pi*(field+GAMMA_BAR_HZ_T*(np.asarray(gradient)@xyz))*dt)
                mz=pd+(mz-pd)*np.exp(-dt/t1);time=end
            for rf,spoke in zip(train['refocusing_s'],train['spokes']):
                center=spoke['echo']*p['echo_spacing_s'];start=center-p['adc_duration_s']/2;end=center+p['adc_duration_s']/2
                assert spoke['adc_start_s']==pytest.approx(train['excitation_s']+start,abs=1e-14)
                free((spoke['echo']-.5)*p['echo_spacing_s']);m=-m.conj();mz=-mz
                free(start-p['prephaser_s']);free(start,spoke['prephaser_gradient_t_m'])
                for index in spoke['sample_indices']:
                    free(start+(index%p['points']+.5)*p['adc_duration_s']/p['points'],spoke['readout_gradient_t_m'])
                    result[:,index]+=np.sum(sens*mask*(1j*m),axis=1)
                free(end,spoke['readout_gradient_t_m']);free(end+p['prephaser_s'],spoke['rewinder_gradient_t_m'])
    return result


def test_all_raw_samples_match_independent_rotations_gradient_bloch_and_receive_sum(finite_run):
    expected=independent_bloch_adc(finite_run)
    assert finite_run['samples']==pytest.approx(expected,abs=2e-11)
    assert finite_run['readout']['coils']==2 and finite_run['samples'].shape==(2,3072)
    assert finite_run['readout']['offsets_s'].min()<0<finite_run['readout']['offsets_s'].max()
    for train in finite_run['timeline']:
        for s in train['spokes']:
            moment=finite_run['design']['prephaser_s']*(np.array(s['prephaser_gradient_t_m'])+np.array(s['rewinder_gradient_t_m']))+finite_run['design']['adc_duration_s']*np.array(s['readout_gradient_t_m'])
            assert moment==pytest.approx(np.zeros(3),abs=1e-20)


def test_default_budget_and_frozen_adc_control_remain_failed(finite_run):
    r=finite_run;assert not r['validation']['passed']
    assert r['solvers'][0]['stop_reason']=='max_work' and not r['solvers'][0]['converged']
    assert r['static_control']['quality']['nrmse']>.2
    assert r['provenance']['estimated_work']<=20000000000
    assert r['provenance']['estimated_peak_memory_bytes']<=134217728


def test_three_dimensional_kz_gradient_and_field_samples_match_bloch_reference():
    labels=np.stack([phantom(),1-phantom()]);r=run_radial_tse(labels,readout_model='finite_adc',spokes=8,points=16,control_iterations=20,inverse_max_iterations=40)
    assert r['samples']==pytest.approx(independent_bloch_adc(r),abs=2e-11)
    assert r['readout']['coordinates_array_order'].shape==(256,3)
    assert not r['validation']['passed']


def test_stricter_data_residual_and_explicit_larger_budget_recover_unscaled_components():
    r=run_radial_tse(phantom(),readout_model='finite_adc',max_work=50000000000,inverse_tolerance=1e-12)
    assert r['validation']['passed'] and r['validation']['coefficient_error']<1e-6
    assert r['quality']['nrmse']<1e-6 and r['solvers'][0]['relative_data_residual']<=1e-12
    replay=run_radial_tse(**r['provenance']['replay'])
    assert replay['provenance']==r['provenance'] and replay['solvers']==r['solvers']


def test_omitted_field_is_visible_model_failure_with_same_acquired_samples():
    a=run_radial_tse(phantom(),readout_model='finite_adc',spokes=16,control_iterations=20)
    b=run_radial_tse(phantom(),readout_model='finite_adc',spokes=16,control_iterations=20,basis_field_scale=0.)
    assert np.array_equal(a['samples'],b['samples'])
    assert not b['validation']['passed'] and b['quality']['nrmse']>.05


@pytest.mark.parametrize('patch',[dict(backend='finufft'),dict(refocusing_angle=140.),dict(adc_duration_s=.008),dict(max_work=1),dict(max_memory_bytes=1),
    dict(coil_count=True),dict(max_samples=1),dict(max_gradient_t_m=.00001),dict(field_hz=[[0.]]),dict(coils_ri=[1.]),dict(basis_t2_s=[.04,.04])])
def test_invalid_or_unsupported_finite_readout_fails_closed(patch):
    with pytest.raises(ValueError): run_radial_tse(phantom(),readout_model='finite_adc',**patch)


def test_echo_center_mode_does_not_silently_ignore_custom_field_or_readout():
    with pytest.raises(ValueError,match='require'): run_radial_tse(phantom(),field_scale_hz=0.)


def test_operator_rejects_invisible_coils_memory_and_complex_coordinates_before_allocation():
    k=np.zeros((4,2));w=np.array([[1.,2.,3.,4.]])
    for patch in [dict(coils=np.zeros((1,2,2))),dict(max_memory_bytes=1),dict(coordinates=k+1j)]:
        args=dict(coordinates=k,spatial_shape=(2,2),weights=w,offsets_s=np.zeros(4),field_hz=np.zeros((2,2)),coils=np.ones((1,2,2)));args.update(patch)
        with pytest.raises(ValueError): ReadoutEncodingOperator(**args)
