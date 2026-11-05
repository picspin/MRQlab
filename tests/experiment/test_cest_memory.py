import numpy as np
import pytest
from mrqlab_physics.ops.generalized_mt import semisolid_green,memory_weights,integrate_generalized_mt
from mrqlab_physics.ops.cest_saturation import _matrix_exp
from mrqlab_physics.ops.super_lorentzian import super_lorentzian_absorption_rate
from mrqlab_experiment.cest_memory import run_cest_memory,saturation_waveform,memory_generator
from mrqlab_experiment.cest_solomon import relay_pool_system
from mrqlab_physics.ops.dipolar_solomon import dipolar_pair_rates


def test_super_lorentzian_green_matches_independent_orientation_quadrature_and_tail():
    u=np.linspace(0,1,200001);t2=1e-5
    for ratio in [0.,.1,1.,10.,100.]:
        reference=np.trapezoid(np.exp(-ratio**2*(3*u*u-1)**2/8),u)
        assert semisolid_green(ratio*t2,t2)==pytest.approx(reference,abs=2e-10)
    # Independent local Gaussian asymptote around u=1/sqrt(3).
    assert semisolid_green(1.,t2)/(np.sqrt(2*np.pi/3)*t2)==pytest.approx(1.,rel=1e-7)
    assert semisolid_green(0.,t2)==pytest.approx(1.,abs=1e-14)


def test_generalized_lorentzian_converges_to_independent_complex_phase_bloch_exponentials():
    errors=[]
    for n in [128,256,512]:
        dt=.002/n;field=np.r_[np.full(n//4,3500*np.exp(.3j)),np.zeros(n//4),np.full(n//4,2500*np.exp(-.6j)),np.zeros(n//4)]
        left,right,_=memory_weights(n,dt,t2_s=.0007,offset_hz=143.,lineshape='lorentzian')
        free=np.array([[-.7,.7],[0,0.]]);zero=np.zeros((2,2))
        history,diag=integrate_generalized_mt(free,zero,zero,[1.,1.],field,dt,left,right,bound_index=0)
        state=np.array([0.,0.,1.,1.]);reference=[1.];cache={}
        for omega in field:
            if omega not in cache:
                delta=2*np.pi*143;g=np.array([[-1/.0007,delta,-omega.imag,0],[-delta,-1/.0007,omega.real,0],[omega.imag,-omega.real,-.7,.7],[0,0,0,0]])
                cache[omega]=_matrix_exp(g,dt)
            state=cache[omega]@state;reference.append(state[2])
        errors.append(float(np.max(abs(history[:,0]-reference))))
        assert diag['estimated_work']<=diag['planned_work'] and not diag['history_reset']
    assert errors[-1]<3e-5 and errors[1]<errors[0]/3.8 and errors[2]<errors[1]/3.8


def test_short_pi_pulse_inverts_semisolid_without_a_saturation_rate_substitute():
    duration=1e-8;n=512;dt=duration/n
    left,right,_=memory_weights(n,dt,t2_s=1e-5)
    free=np.array([[-1.,1.],[0,0.]]);zero=np.zeros((2,2))
    history,_=integrate_generalized_mt(free,zero,zero,[1.,1.],np.full(n,np.pi/duration),dt,left,right,bound_index=0)
    assert history[-1,0]<-.99999
    with pytest.raises(ValueError,match='nonzero'): super_lorentzian_absorption_rate(1.,0.,1e-5)


def test_full_coupled_lorentzian_limit_matches_independent_augmented_bloch_matrix():
    system=relay_pool_system();rates=dipolar_pair_rates();g,rx,ry=memory_generator(system,200.,rates,bound_t2_s=.0003)
    initial=np.zeros(17);initial[2:15:3]=system.density;initial[15]=.08;initial[-1]=1.
    omega=1500.+700j;augmented=np.zeros((19,19));a=g+omega.real*rx+omega.imag*ry
    augmented[:16,:16]=a[:16,:16];augmented[:16,-1]=a[:16,-1]
    delta=2*np.pi*200
    augmented[16:18,16:18]=[[-1/.0003,delta],[-delta,-1/.0003]]
    augmented[16,15]=-omega.imag;augmented[17,15]=omega.real
    augmented[15,16]=omega.imag;augmented[15,17]=-omega.real
    start=np.r_[initial[:16],0.,0.,1.]
    exact=_matrix_exp(augmented,.001)@start;errors=[]
    for n in [128,256,512]:
        left,right,_=memory_weights(n,.001/n,t2_s=.0003,offset_hz=200.,lineshape='lorentzian')
        history,_=integrate_generalized_mt(g,rx,ry,initial,np.full(n,omega),.001/n,left,right,bound_index=15)
        errors.append(float(np.max(abs(history[-1,:16]-exact[:16]))))
    assert errors[-1]<1e-5 and errors[1]<errors[0]/3.8 and errors[2]<errors[1]/3.8


def test_pulse_phase_memory_survives_gap_and_differs_from_resetting_each_pulse():
    n=512;dt=1e-6;field=np.r_[np.full(128,4000.),np.zeros(64),np.full(128,4000j),np.zeros(192)]
    a,b,_=memory_weights(n,dt,t2_s=.0003,offset_hz=200.,lineshape='gaussian')
    free=np.array([[-1.,1.],[0,0.]]);zero=np.zeros((2,2))
    full,_=integrate_generalized_mt(free,zero,zero,[1.,1.],field,dt,a,b,bound_index=0)
    restart=192;short_left,short_right,_=memory_weights(n-restart,dt,t2_s=.0003,offset_hz=200.,lineshape='gaussian')
    reset,_=integrate_generalized_mt(free,zero,zero,full[restart],field[restart:],dt,short_left,short_right,bound_index=0)
    assert abs(full[-1,0]-reset[-1,0])>.01


def test_waveform_keeps_exact_boundaries_peak_phase_and_rf_energy_under_refinement():
    field,wave=saturation_waveform(phase_cycle_rad=[0.,np.pi/2],steps_per_bin=12)
    fine,ref=saturation_waveform(phase_cycle_rad=[0.,np.pi/2],steps_per_bin=24)
    assert np.repeat(field,2)==pytest.approx(fine,abs=1e-14)
    assert ref['rf_energy_uT2_s']==pytest.approx(wave['rf_energy_uT2_s'],rel=1e-14)
    assert wave['elapsed_s']==pytest.approx(.2) and wave['peak_b1_uT']==pytest.approx(1.)
    assert wave['events'][1]['phase_rad']==pytest.approx(np.pi/2)
    with pytest.raises(ValueError,match='align'): saturation_waveform(gap_s=.04001)


@pytest.fixture(scope='module')
def memory_run(): return run_cest_memory(offsets_ppm=[-3.5,0.,3.5])


def test_joint_cest_relay_zero_offset_is_finite_and_convergence_separate_from_targets(memory_run):
    r=memory_run
    assert all(np.isfinite(z).all() for z in r['spectra'].values())
    assert r['validation']['numerical_refinement_passed'] and not r['validation']['passed']
    assert r['metrics']['amide_exchange_contrast']>.005 and r['metrics']['relayed_noe_contrast']<.005
    assert r['metrics']['mt_contrast_at_zero']>0
    assert abs(r['metrics']['unsaturated_water']-1.)<1e-8
    assert r['provenance']['estimated_work']<=r['provenance']['planned_work']<=32000000000
    assert r['provenance']['estimated_peak_memory_bytes']<=134217728
    assert len(r['trajectories']['full'])==3 and len(r['trajectories']['full'][0]['final_state'])==17
    for row in r['trajectories']['full']:
        witness=row['maximum_error_witness']
        assert abs(witness['coarse_value']-witness['refined_value'])==pytest.approx(row['refinement_error'],abs=1e-14)


def test_coarse_time_grid_is_explicit_failure_not_silently_relabelled_as_converged():
    r=run_cest_memory(offsets_ppm=[-3.5,0.,3.5],steps_per_bin=4)
    assert not r['validation']['numerical_refinement_passed'] and not r['validation']['passed']
    assert r['metrics']['max_normalized_trace_refinement_error']>.0002


def test_disconnect_bridge_removes_water_cross_relaxation_path():
    r=run_cest_memory(offsets_ppm=[-3.5,0.,3.5],bridge_exchange_s1=0.,b1_uT=.5,steps_per_bin=4)
    assert r['metrics']['relayed_noe_contrast']==pytest.approx(0.,abs=1e-12)


@pytest.mark.parametrize('patch',[{'max_work':1},{'max_memory_bytes':1},{'steps_per_bin':True},
    {'bound_to_water_hz':1000.,'bound_t2_s':.001},{'lineshape':'clamped_sl'},{'offsets_ppm':[-3.5,3.5]},
    {'gap_s':.04001},{'rf_bins':128},{'target_refinement_error':0.},{'phase_cycle_rad':[]}])
def test_invalid_regime_and_full_grid_budget_rejected_before_computation(patch):
    with pytest.raises(ValueError): run_cest_memory(**patch)
