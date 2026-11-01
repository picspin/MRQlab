import copy
import numpy as np
import pytest
from mrqlab_experiment import build_preset,run_experiment,plan_experiment,validate_experiment
from mrqlab_experiment.models import TissueModel,PhysiologyModel
from mrqlab_experiment.contrast_relaxation import ContrastExposure,tissue_relaxation
from mrqlab_experiment.observations import build_result_graph
from mrqlab_experiment.objectives import evaluate_multi_tissue_contrast
from mrqlab_experiment.family_recipes import build_family_recipe
from mrqlab_experiment.tse_imaging import run_tse_imaging


def exposure(field=1.5,concentration=.2,**kwargs):
    return ContrastExposure(concentration_mmol_l=concentration,r1_l_mmol_s=4.,r2_l_mmol_s=5.,
        reference_b0_t=field,reference_temperature_k=310.,medium='synthetic water phantom',valid_concentration_max_mmol_l=1.,
        source_ref='synthetic:relaxivity-pilot',origin='synthetic',**kwargs)


def graph(backend='bloch',concentration=.2):
    g=build_preset('spin-echo');g.engine.preferred=backend
    g.tissue=TissueModel(id='water',t1=1.2,t2=.1,proton_density=.8,contrast_exposure=exposure(g.effective_scanner.b0_t,concentration))
    g.readout=g.readout.model_copy(update={'products':('signal',)})
    return g


def test_explicit_rate_units_baseline_retention_and_zero_concentration():
    g=graph();before=g.model_dump(mode='json');t1,t2,b=tissue_relaxation(g.tissue,g.effective_scanner.b0_t)
    assert t1==pytest.approx(1/(1/1.2+4*.2)) and t2==pytest.approx(1/(1/.1+5*.2))
    assert b['baseline_t1_s']==1.2 and b['exposure']['concentration_unit']=='mmol/L'
    assert g.model_dump(mode='json')==before
    zero=graph(concentration=0.);a,c,_=tissue_relaxation(zero.tissue,zero.effective_scanner.b0_t)
    assert a==1.2 and c==.1


@pytest.mark.parametrize('field,value',[
    ('concentration_mmol_l',-1.),('concentration_mmol_l',2.),('concentration_mmol_l',True),
    ('concentration_unit','mmol/kg'),('r1_l_mmol_s',float('nan')),('r2_l_mmol_s',float('inf')),
    ('reference_b0_t',0.),('reference_temperature_k',0.),('medium',' '),('source_ref',' '),('origin','unknown')])
def test_declared_relaxivity_rejects_unwired_units_values_and_extrapolation(field,value):
    d=exposure().model_dump(mode='json');d[field]=value
    with pytest.raises(ValueError): ContrastExposure.model_validate(d)


@pytest.mark.parametrize('change',[{'t2_star':.05},{'bound_pool':True},{'chemical_shift_ppm':3.5},{'t1':float('inf')}])
def test_unsupported_tissue_and_field_do_not_silently_ignore_contrast(change):
    g=graph();g.tissue=g.tissue.model_copy(update=change)
    with pytest.raises(ValueError): run_experiment(g)
    assert not validate_experiment(g).valid


def test_reference_field_and_legacy_unitless_concentration_fail_closed():
    g=graph();g.scanner.b0_t=3.
    with pytest.raises(ValueError,match='B0 differs'): run_experiment(g)
    g=graph();g.physiology=PhysiologyModel(contrast_agent_concentration=.2)
    with pytest.raises(ValueError,match='legacy physiology'): run_experiment(g)


def test_unphysical_effective_transverse_relaxation_is_rejected():
    t=graph().tissue
    t.contrast_exposure=exposure().model_copy(update={'r1_l_mmol_s':1000.,'r2_l_mmol_s':0.})
    with pytest.raises(ValueError,match='R2 >= R1/2'): tissue_relaxation(t,1.5)


@pytest.mark.parametrize('backend',['bloch','epg'])
def test_bloch_and_epg_signal_matches_independent_spin_echo_decay(backend):
    g=graph(backend)
    from mrqlab_experiment.compiler import compile_sequence
    sequence=compile_sequence(g)
    sequence.channels=[c for c in sequence.channels if c.name not in ['gx','gy','gz']]
    g.sequence=sequence;run=run_experiment(g)
    # Unencoded initial-equilibrium ideal hard 90/180 echo; no teaching shifts.
    from mrqlab_physics.kernel.scheduler import preflight_schedule
    from mrqlab_physics import EngineOptions
    options=EngineOptions(**dict(run.plan.options))
    times=np.array([w.start+i*options.dwell_time for w in preflight_schedule(run.sequence,options).adc_windows for i in range(w.count)])
    expected=.8*np.exp(-times*(10.+5.*.2))
    assert abs(run.sim_result.signal)==pytest.approx(expected,abs=2e-12)
    assert run.experiment.tissue.t1==1.2 and run.experiment.tissue.t2==.1
    provenance=build_result_graph(run).observations[0].provenance
    assert provenance.contrast_relaxation_bindings[0]['effective_t2_s']==pytest.approx(1/11.)
    assert run.plan.physics_status['contrast_relaxation'].startswith('static_linear')
    assert any(p.name=='tissue.water.effective_t1_s' and p.unit=='s' for p in run.plan.parameters)


def test_increased_concentration_changes_signal_and_objective_through_same_binding():
    zero=graph(concentration=0.);exposed=graph(concentration=.8)
    before=run_experiment(zero);after=run_experiment(exposed)
    assert np.max(abs(after.sim_result.signal))<np.max(abs(before.sim_result.signal))
    score=evaluate_multi_tissue_contrast(exposed)
    assert np.asarray(score['tissue_signals'][0])==pytest.approx(after.sim_result.signal,abs=1e-12)
    assert before.plan.fingerprint!=after.plan.fingerprint


def test_tse_periodic_echoes_use_effective_relaxation_without_mutating_baseline():
    g=build_family_recipe('brain_t1_3d_tse');g.tissue[0].contrast_exposure=exposure(3.,.2)
    before=g.model_dump(mode='json');labels=np.indices((16,16))[0]%2
    r=run_tse_imaging(labels,experiment=g,refocusing_angle=180.,refocusing_end_angle=180.)
    expected=np.exp(-.008*(1/.04+5*.2))
    assert r['tissue_echo_weights'][0,1:]/r['tissue_echo_weights'][0,:-1]==pytest.approx(expected,abs=2e-10)
    b=r['provenance']['physical'][0]['contrast_relaxation_bindings'][0]
    assert b['baseline_t2_s']==.04 and b['effective_t2_s']==pytest.approx(1/26.)
    # Independent ideal-180 repeated-train longitudinal recovery, not EPG.
    t1=1/(1/g.tissue[0].t1+4*.2);pd=g.tissue[0].proton_density;z=0.;at=0.
    for rf in (np.arange(4)+.5)*.008:
        z=pd+(z-pd)*np.exp(-(rf-at)/t1);z=-z;at=rf
    z0=pd+(z-pd)*np.exp(-(.4-at)/t1)
    assert r['tissue_echo_weights'][0]==pytest.approx(z0*np.exp(-np.arange(1,5)*.008*26),abs=2e-9)
    assert g.model_dump(mode='json')==before
    with pytest.raises(ValueError,match='radial/inverse'):
        from mrqlab_experiment.radial_tse import run_radial_tse
        run_radial_tse(labels,experiment=g)


def test_measured_t2_study_rejects_ambiguous_exposed_baseline():
    from mrqlab_experiment.lab_study import build_lab_study_example,LabStudy
    s=build_lab_study_example().model_dump(mode='json')
    s['experiment']['tissue'][0]['contrast_exposure']=exposure(3.).model_dump(mode='json')
    with pytest.raises(ValueError,match='contrast-free baseline'): LabStudy.model_validate(s)


def test_intrinsic_gaussian_diffusion_and_extrinsic_relaxation_reach_same_pgse_signal():
    from mrqlab_physics.kernel.scheduler import preflight_schedule
    from mrqlab_physics import EngineOptions
    g=build_family_recipe('brain_epse_dwi');g.tissue=g.tissue[0]
    g.tissue.contrast_exposure=exposure(3.,.2);run=run_experiment(g)
    opts=EngineOptions(**dict(run.plan.options));windows=preflight_schedule(run.sequence,opts).adc_windows
    times=np.array([w.start+i*opts.dwell_time for w in windows for i in range(w.count)])
    b=np.array(run.sim_result.meta['b_samples_s_mm2']);r2=1/g.tissue.t2+5*.2
    expected=g.tissue.proton_density*np.exp(-times*r2-b*g.tissue.diffusion_adc_mm2_s)
    assert abs(run.sim_result.signal)==pytest.approx(expected,abs=2e-12)
    assert 'diffusion' in run.plan.physics_status and 'contrast_relaxation' in run.plan.physics_status
    assert g.tissue.diffusion_adc_mm2_s==.0006


def test_liquid_water_relaxivity_and_declared_cest_exchange_bind_without_changing_rates():
    g=build_family_recipe('cest_multi_pool_z_spectrum');g.tissue[0].contrast_exposure=exposure(3.,.2)
    manual=g.model_copy(deep=True);water=manual.tissue[0]
    water.t1=1/(1/g.tissue[0].t1+4*.2);water.t2=1/(1/g.tissue[0].t2+5*.2);water.contrast_exposure=None
    actual=run_experiment(g);expected=run_experiment(manual)
    assert actual.sim_result.z_spectrum['Z']==pytest.approx(expected.sim_result.z_spectrum['Z'],abs=2e-12)
    assert actual.sequence.metadata['cest']['exchange_matrix_hz']==expected.sequence.metadata['cest']['exchange_matrix_hz']
    assert actual.sim_result.meta['contrast_relaxation_bindings'][0]['effective_t1_s']==water.t1
