"""Acceptance of research chains; independent references and replay checks."""
import json
import hashlib
import numpy as np
import pytest
from mrqlab_experiment import build_clinical_recipe, run_experiment, build_result_graph, compile_sequence
from mrqlab_experiment.family_recipes import FAMILY_RECIPES
from mrqlab_experiment.family_search import search_family_parameters, evaluate_family, peak_integrals
from mrqlab_experiment.family_execution import ssfp_steady_state, adc_map
from mrqlab_physics import Phantom, EngineOptions, ScannerModel, get_engine, BlochMcConnellPools
from mrqlab_physics.models import LiquidPoolSystem
from mrqlab_physics.backends.epg_x import EpgXBackend, apply_bloch_mcconnell
from mrqlab_physics.ops.cest_saturation import apply_cw_bloch_mcconnell_saturation, _matrix_exp
from mrqlab_physics.ops.types import Relax, RfOp
from mrqlab_sequence import build_sequence

PATCHES=(
 ({'tr':.3},{'tr':.6},{'refocusing_flip_angle':120.}),
 ({'inversion_time_s':.7},{'inversion_time_s':1.1},{'flip_angle':25.}),
 ({'diffusion_gradient_mt_m':10.},{'diffusion_gradient_mt_m':20.},{'diffusion_gradient_mt_m':35.}),
 ({'saturation_power_uT':.5},{'saturation_power_uT':1.},{'saturation_power_uT':3.}),
 ({'te':.01},{'te':.02},{'te':.05}),
)


@pytest.mark.parametrize('name,patches',tuple(zip(FAMILY_RECIPES,PATCHES)))
def test_family_clinical_design_simulation_search_validation_provenance(name,patches,tmp_path):
    graph=build_clinical_recipe(name); original=graph.model_dump(mode='json')
    result=search_family_parameters(graph,patches,max_duration_s=60,max_rf_energy_relative=1000)
    assert graph.model_dump(mode='json')==original
    assert result.best is not None
    assert result.best.objective_loss<result.baseline.objective_loss
    assert result.objective and result.clinical_question
    replay=graph.model_copy(deep=True)
    if name=='cest_multi_pool_z_spectrum': replay.sequence.metadata['cest'].update(result.best.parameters)
    else: replay.sequence.params.update(result.best.parameters)
    _,loss,metrics,provenance,duration,energy=evaluate_family(replay)
    assert loss==pytest.approx(result.best.objective_loss,abs=1e-12)
    assert metrics==result.best.measurements
    assert provenance==result.best.provenance
    assert energy==result.best.rf_energy_relative and duration==result.best.duration_s
    for point in (result.baseline,*result.candidates):
        assert point.elapsed_s>0 and np.isfinite(point.objective_loss)
        for prov in point.provenance:
            assert len(prov['experiment_hash'])==len(prov['plan_fingerprint'])==64
            assert prov['clinical_recipe_id']==name
            assert prov['scanner_profile']=='research-3t@1.0.0'
            assert prov['n_ops']>0 and prov['estimated_work']>0 and prov['assumptions']
    path=tmp_path/(name+'.json');path.write_text(result.model_dump_json(indent=2))
    assert json.loads(path.read_text())['best']['objective_loss']==result.best.objective_loss


@pytest.mark.parametrize('name',FAMILY_RECIPES)
def test_family_search_no_feasible_candidate(name):
    result=search_family_parameters(build_clinical_recipe(name),[{}],max_duration_s=.001,max_rf_energy_relative=.001)
    assert result.best is None


@pytest.mark.parametrize('patch',({'te_ms':10},{'te':float('nan')},{'te':True},{'tr':0}))
def test_family_search_invalid_parameters(patch):
    with pytest.raises(ValueError):
        search_family_parameters(build_clinical_recipe(FAMILY_RECIPES[0]),[patch],max_duration_s=60,max_rf_energy_relative=1000)


def test_tse_partition_encoding_and_authored_flip_ramp():
    g=build_clinical_recipe('brain_t1_3d_tse');seq=compile_sequence(g)
    assert seq.metadata['partitions']==4
    assert sorted({e['kz'] for e in seq.metadata['partition_encodings']})==[-2,-1,0,1]
    refocus=[e.value for e in seq.channel('rf_amp') if e.value!=90]
    assert refocus[:4]==pytest.approx([140,130,120,110])
    gz=seq.channel('gz')
    for encoding in seq.metadata['partition_encodings']:
        center=encoding['time_s']
        lobe=next(e for e in gz if abs(e.time-(center-.002))<1e-10)
        rewind=next(e for e in gz if abs(e.time-(center+.002))<1e-10)
        assert lobe.value*.001==pytest.approx(encoding['moment_teaching_s'])
        assert rewind.value==-lobe.value
    run=run_experiment(g)
    assert run.sim_result.meta['steady_preparation_trains']>1
    states={s.name:s for s in run.plan.parameters}
    assert states['partitions'].unit=='count' and states['refocusing_end_angle'].unit=='deg'


def test_tse_t1_weighting_disappears_for_equal_t1():
    g=build_clinical_recipe('brain_t1_3d_tse')
    assert evaluate_family(g)[2]['target_signal']>evaluate_family(g)[2]['reference_signal']
    a,b=g.tissue;g.tissue=(a,b.model_copy(update={'t1':a.t1}))
    assert evaluate_family(g)[1]==pytest.approx(0,abs=1e-12)


@pytest.mark.parametrize('t1,t2,angle',((1.,.08,40.),(.8,.12,25.),(1.5,.15,70.)))
def test_ssfp_matches_independent_exact_on_resonance_formula(t1,t2,angle):
    tr=.005;e1=np.exp(-tr/t1);e2=np.exp(-tr/t2);a=np.deg2rad(angle)
    # Closed-form balanced SSFP at TE=TR/2, pi RF phase advance.
    reference=(1-e1)*np.sin(a)*np.sqrt(e2)/(1-e1*e2-(e1-e2)*np.cos(a))
    assert abs(ssfp_steady_state(t1,t2,tr,angle))==pytest.approx(reference,rel=1e-12)
    g=build_clinical_recipe('vessel_wall_ssfp_darkblood');g.tissue=g.tissue[0].model_copy(update={'t1':t1,'t2':t2})
    g.sequence.params.update(repetitions=2048,double_inversion=0,flip_angle=angle)
    r=run_experiment(g)
    assert abs(r.sim_result.signal[-2])==pytest.approx(reference,rel=1e-6)


@pytest.mark.parametrize('offset',(-80.,30.,80.))
def test_ssfp_off_resonance_steady_fixed_point_matches_long_train(offset):
    g=build_clinical_recipe('vessel_wall_ssfp_darkblood');g.tissue=g.tissue[0]
    g.sequence.params.update(repetitions=2048,double_inversion=0);g.sample.off_resonance_hz=offset
    r=run_experiment(g)
    assert abs(r.sim_result.signal[-2])==pytest.approx(abs(ssfp_steady_state(1.,.08,.005,40.,offset)),rel=1e-6)


def test_double_inversion_null_and_inflow_boundary_and_legacy_retained():
    g=build_clinical_recipe('vessel_wall_ssfp_darkblood');g.tissue=g.tissue[1]
    ti=1.6*np.log(2);g.sequence.params.update(inversion_time_s=ti,blood_compartment=1)
    run=run_experiment(g)
    # Incoming blood sees just the first inversion; at TI it reaches zero.
    assert abs(run.sim_result.signal[0])<1e-12
    assert len([e for e in run.sequence.channel('rf_amp') if e.value==180])==2
    g.sequence.params['inflow_fraction']=0
    resident=run_experiment(g)
    expected=np.sin(np.deg2rad(40))*np.exp(-.0025/.18)
    assert abs(resident.sim_result.signal[0])==pytest.approx(expected,rel=1e-5)
    assert np.mean(abs(resident.sim_result.signal))>10*np.mean(abs(run.sim_result.signal))
    legacy=build_clinical_recipe('dark_blood_vessel_wall_tse')
    assert legacy.sequence.template=='TSE'


@pytest.mark.parametrize('gradient',(0.,10.,20.,30.,40.))
def test_dwi_waveform_integrated_b_signal_attenuation_and_adc(gradient):
    g=build_clinical_recipe('brain_epse_dwi');g.tissue=g.tissue[0]
    g.sequence.params['diffusion_gradient_mt_m']=gradient
    g.readout.products=('signal','k_trajectory')
    r=run_experiment(g);g.sequence.params['diffusion_gradient_mt_m']=0.;control=run_experiment(g)
    assert build_result_graph(r).observations[1].units['k']=='cycles/m'
    b=r.sim_result.meta['b_value_s_mm2']
    assert b==pytest.approx(r.sim_result.meta['b_reference_s_mm2'],rel=.0002)
    assert abs(r.sim_result.signal)==pytest.approx(abs(control.sim_result.signal)*np.exp(-b*.0006),rel=1e-10)
    assert np.isfinite(r.sim_result.signal).all()
    trajectory=r.sim_result.meta['epi_trajectory'];n=16
    assert trajectory['kx'][:n]==trajectory['kx'][n:2*n][::-1]
    if b>0:
        assert adc_map([0,b],np.array([abs(control.sim_result.signal),abs(r.sim_result.signal)]))==pytest.approx(np.full(r.sim_result.signal.size,.0006))


def test_voxelwise_multi_b_adc_map_and_failures():
    b=np.array([0,300,700,1200.]);truth=np.array([[.0005,.001],[.0015,.002]])
    s=2*np.exp(-b[:,None,None]*truth)
    assert adc_map(b,s)==pytest.approx(truth)
    for bad_b,bad_s in (([0,0],[1,1]),([0,500],[1,0]),([0,float('nan')],[1,.5])):
        with pytest.raises(ValueError): adc_map(bad_b,bad_s)


def system(n):
    density=np.array([1.]+[.02]*(n-1));rates=np.zeros((n,n))
    for j in range(1,n):rates[j,0]=20*j;rates[0,j]=rates[j,0]*density[j]/density[0]
    return LiquidPoolSystem(tuple([1.]*n),tuple([.08]+[.015]*(n-1)),tuple(density),tuple([0.]+[100.*j for j in range(1,n)]),tuple(map(tuple,rates)))


@pytest.mark.parametrize('n',(1,2,3,5))
def test_npool_exchange_conservation_equilibrium_rf_and_saturation(n):
    pools=system(n);backend=EpgXBackend(Phantom(liquid_pools=pools),2)
    assert backend.omega.shape==(3*n,5)
    assert pools.exchange.sum(axis=0)==pytest.approx(np.zeros(n),abs=1e-12)
    initial=backend.omega.copy();backend.apply(Relax(0,.1))
    assert backend.omega==pytest.approx(initial,abs=1e-12)
    backend.apply(RfOp(0,np.pi/2,0));assert abs(backend.observe())==pytest.approx(sum(pools.density))
    state=initial.copy();apply_cw_bloch_mcconnell_saturation(state,.2,100.,1.,pools)
    assert np.isfinite(state).all() and state[2,2].real<initial[2,2].real


def test_npool_two_pool_compatibility_and_nonzero_orders_no_recovery():
    old=BlochMcConnellPools(1.,.08,.9,1.2,.02,.1,2.,18.,400.)
    new=LiquidPoolSystem.from_two(old)
    rng=np.random.default_rng(4);state=rng.normal(size=(6,5)).astype(complex)
    a,b=state.copy(),state.copy()
    apply_bloch_mcconnell(a,.1,old);apply_bloch_mcconnell(b,.1,new)
    assert a==pytest.approx(b,abs=1e-12)
    a,b=state.copy(),state.copy()
    apply_cw_bloch_mcconnell_saturation(a,.4,400.,1.,old)
    apply_cw_bloch_mcconnell_saturation(b,.4,400.,1.,new)
    assert a==pytest.approx(b,abs=1e-12)
    zero=np.zeros((6,5),complex);apply_bloch_mcconnell(zero,.1,new)
    assert zero[:,[0,1,3,4]]==pytest.approx(np.zeros((6,4)))


def test_npool_invalid_exchange_fails_and_cest_imaging_remains_rejected():
    with pytest.raises(ValueError,match='balance'):
        LiquidPoolSystem((1.,1.),(.1,.1),(1.,.1),(0.,100.),((0.,2.),(3.,0.)))
    g=build_clinical_recipe('cest_multi_pool_z_spectrum');g.readout.products=('image',)
    with pytest.raises(ValueError,match='image'):run_experiment(g)
    g=build_clinical_recipe('cest_multi_pool_z_spectrum');g.engine.options['max_work']=1
    with pytest.raises(ValueError,match='max_work|work requires'):run_experiment(g)


def test_matrix_exp_defective_generator():
    a=np.array([[-1.,1.],[0.,-1.]])
    assert _matrix_exp(a,2.)==pytest.approx(np.exp(-2)*np.array([[1.,2.],[0.,1.]]),abs=1e-13)


def test_press_localization_water_reference_and_peak_quantification():
    g=build_clinical_recipe('brain_press_mrs');r=run_experiment(g)
    assert r.sequence.metadata['localization_axes']==['x','y','z']
    assert [e.value for e in r.sequence.channel('rf_amp')]==[90,180,180]
    # Arbitrarily strong out-of-voxel spin must be excluded by slab intersection.
    inside=g.model_copy(deep=True);inside.sample.isochromats=(dict(position_m=(0.,0.,0.),weight=1.),)
    outside=g.model_copy(deep=True);outside.sample.isochromats=(dict(position_m=(0.,0.,0.),weight=1.),dict(position_m=(.03,0.,0.),weight=1e6))
    assert run_experiment(inside).sim_result.signal==pytest.approx(run_experiment(outside).sim_result.signal)
    metrics=evaluate_family(g)[2]
    assert metrics['water_area']>0
    for k,v in metrics['relative_amounts'].items():
        # Finite-window teaching signal amounts; no clinical accuracy claim.
        assert v==pytest.approx(metrics['teaching_truth'][k],rel=.15)
    assert evaluate_family(g)[1]>.01 # expose finite-window / relaxation bias
    bad=g.model_copy(deep=True);bad.sample.isochromats=(dict(position_m=(.1,0.,0.)),)
    with pytest.raises(ValueError,match='no sample'):run_experiment(bad)


@pytest.mark.parametrize('name',FAMILY_RECIPES)
def test_direct_recipe_run_provenance_and_compartment_execution(name):
    graph=build_clinical_recipe(name);run=run_experiment(graph)
    observations=build_result_graph(run).observations
    digest=hashlib.sha256(json.dumps(run.experiment.model_dump(mode='json'),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    for obs in observations:
        assert obs.provenance.experiment_hash==digest
        assert obs.provenance.plan_fingerprint==run.plan.fingerprint
    if name in FAMILY_RECIPES[:3]:
        assert len(run.sim_result.meta['tissue_signals'])==2
        assert run.sim_result.signal==pytest.approx(np.mean(run.sim_result.meta['tissue_signals'],axis=0))
        if name=='brain_epse_dwi':
            a,b=run.sim_result.meta['tissue_signals'];value=run.sim_result.meta['b_value_s_mm2']
            assert abs(a)/abs(b)==pytest.approx(np.full(a.size,np.exp(value*(.001-.0006))))


@pytest.mark.parametrize('pulsed',(False,True))
def test_four_liquid_pool_cest_and_no_exchange_control(pulsed):
    graph=build_clinical_recipe('cest_multi_pool_z_spectrum')
    from mrqlab_experiment import TissueModel
    water,amide,amine=graph.tissue
    graph.tissue=(water.model_copy(update={'proton_density':.95,'pool_fraction':.95}),amide,amine,
                  TissueModel(id='upfield_liquid',t1=1.,t2=.02,proton_density=.01,pool_fraction=.01,chemical_shift_ppm=-3.5))
    rates=np.zeros((4,4))
    for j,k in ((1,30.),(2,100.),(3,15.)):
        rates[j,0]=k;rates[0,j]=k*graph.tissue[j].proton_density/.95
    cest=graph.sequence.metadata['cest'];cest['exchange_matrix_hz']=rates.tolist()
    if pulsed:
        cest.update(mode='pulsed',n_pulses=10,pulse_duration_s=.1,gap_duration_s=.1,saturation_duration_s=1.9)
    result=run_experiment(graph).sim_result
    assert np.isfinite(result.z_spectrum['Z']).all()
    assert np.all(result.z_spectrum['Z']>=0)
    assert 'N-liquid-pool EPG-X' in result.meta['assumptions']
    cest['exchange_matrix_hz']=np.zeros((4,4)).tolist()
    control=run_experiment(graph).sim_result
    assert np.linalg.norm(result.z_spectrum['Z']-control.z_spectrum['Z'])>.01


def test_npool_saturation_matches_independent_cartesian_rk4():
    pools=system(3);state=np.zeros((9,1),complex);state[2::3,0]=pools.density
    duration=.02;b1=.3;offset=150.
    apply_cw_bloch_mcconnell_saturation(state,duration,offset,b1,pools)
    # Independent explicit ODE with exchange written as source/destination flux.
    from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
    def derivative(m):
        out=np.zeros_like(m)
        for i in range(3):
            x,y,z=m[i];dw=2*np.pi*(offset-pools.offset_hz[i]);w=2*np.pi*GAMMA_BAR_HZ_T*b1*1e-6
            out[i]=(-x/pools.t2[i]+dw*y,-y/pools.t2[i]-dw*x+w*z,(pools.density[i]-z)/pools.t1[i]-w*y)
            for j in range(3):
                out[i]+=pools.rates[j][i]*m[j]-pools.rates[i][j]*m[i]
        return out
    m=np.zeros((3,3));m[:,2]=pools.density;dt=duration/2000
    for _ in range(2000):
        a=derivative(m);b=derivative(m+dt*a/2);c=derivative(m+dt*b/2);d=derivative(m+dt*c)
        m+=dt*(a+2*b+2*c+d)/6
    assert state[::3,0].real==pytest.approx(m[:,0],abs=1e-10)
    assert state[::3,0].imag==pytest.approx(m[:,1],abs=1e-10)
    assert state[2::3,0].real==pytest.approx(m[:,2],abs=1e-10)


def test_cest_budget_accounts_for_all_offsets_and_controls():
    graph=build_clinical_recipe('cest_multi_pool_z_spectrum')
    result=search_family_parameters(graph,[{'saturation_power_uT':1.}],max_duration_s=30,max_rf_energy_relative=1000)
    assert result.best is None # 2 acquisitions x (7 offsets + control) x 2 s = 32 s
    assert result.baseline.duration_s==32
    assert result.baseline.rf_energy_unit=='uT^2 s'


def test_family_rejects_forced_wrong_backend():
    graph=build_clinical_recipe('brain_t1_3d_tse');graph.engine.preferred='bloch'
    with pytest.raises(ValueError,match='declared backend'):run_experiment(graph)


def test_fully_connected_exchange_and_pool_permutation_invariance():
    density=np.array([.9,.07,.03]);flux=np.array([[0,.3,.2],[.3,0,.1],[.2,.1,0.]])
    rates=flux/density[:,None]
    pools=LiquidPoolSystem((1.,1.2,.8),(.08,.02,.01),tuple(density),(0.,300.,-200.),tuple(map(tuple,rates)))
    assert pools.exchange@density==pytest.approx(np.zeros(3),abs=1e-14)
    permutation=np.array([2,0,1])
    shuffled=LiquidPoolSystem(tuple(np.asarray(pools.t1)[permutation]),tuple(np.asarray(pools.t2)[permutation]),tuple(density[permutation]),
        tuple(np.asarray(pools.offset_hz)[permutation]),tuple(map(tuple,rates[np.ix_(permutation,permutation)])))
    a=np.zeros((9,1),complex);a[2::3,0]=density
    b=np.zeros((9,1),complex);b[2::3,0]=density[permutation]
    apply_cw_bloch_mcconnell_saturation(a,.5,300.,1.,pools)
    apply_cw_bloch_mcconnell_saturation(b,.5,300.,1.,shuffled)
    assert b.reshape(3,3)==pytest.approx(a.reshape(3,3)[permutation],abs=1e-12)


@pytest.mark.parametrize('template,params',(
    ('TSE3D',{'partitions':0}),('TSE3D',{'te':.001}),('TSE3D',{'refocusing_end_angle':200}),
    ('SSFP',{'tr':.005,'te':.004}),('SSFP',{'inflow_fraction':1.1}),
    ('EPSE',{'te':.03}),('EPSE',{'delta_s':-.1}),('PRESS',{'readout_s':2}),
))
def test_family_design_invalid_timing_or_strategy_rejected(template,params):
    with pytest.raises(ValueError):build_sequence(template,params)


def test_spectral_peak_windows_fail_closed_for_alias_and_insufficient_resolution():
    with pytest.raises(ValueError,match='Nyquist'):peak_integrals(np.ones(512)*(-1j),.001,{'aliased':600})
    with pytest.raises(ValueError,match='undersampled'):peak_integrals(np.ones(4)*(-1j),.001,{'water':0})


@pytest.mark.parametrize('name',FAMILY_RECIPES[:3])
def test_standard_tissue_observation_uses_family_physics(name):
    graph=build_clinical_recipe(name);graph.readout.products=('signal','tissue_contrast')
    run=run_experiment(graph);observations={o.id:o for o in build_result_graph(run).observations}
    assert np.asarray(observations['tissue_contrast'].data['tissue_signals'])==pytest.approx(np.asarray(run.sim_result.meta['tissue_signals']))
