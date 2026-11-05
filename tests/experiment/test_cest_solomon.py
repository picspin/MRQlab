import numpy as np
import pytest
from mrqlab_physics.models import LiquidPoolSystem
from mrqlab_physics.ops.dipolar_solomon import dipolar_pair_rates,add_solomon_pair
from mrqlab_physics.ops.cest_saturation import _matrix_exp
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from mrqlab_physics.ops.super_lorentzian import super_lorentzian_absorption_rate
from mrqlab_experiment.cest_mt_noe import joint_generator
from mrqlab_experiment.cest_solomon import relay_pool_system,relay_generator,run_cest_solomon


def initial(system,bound=.08):
    s=np.zeros(3*system.count+2); s[2:3*system.count:3]=system.density; s[-2]=bound; s[-1]=1.; return s


def test_rates_have_distance_sixth_power_and_signed_fast_slow_limits():
    fast=dipolar_pair_rates(tau_c_s=1e-12,shifts_ppm=(0.,0.))
    assert fast['sigma_s1']/fast['rho_i_s1']==pytest.approx(.5,rel=1e-5)
    slow=dipolar_pair_rates(tau_c_s=1e-7,shifts_ppm=(0.,0.))
    assert slow['sigma_s1']/slow['rho_i_s1']==pytest.approx(-1.,abs=.001)
    a=dipolar_pair_rates(); b=dipolar_pair_rates(distance_m=5e-10)
    for name in ['rho_i_s1','rho_s_s1','sigma_s1','w0_s1','w2_s1','w1_i_s1','w1_s_s1']:
        assert a[name]/b[name]==pytest.approx(64.,rel=2e-15)
    assert a['rho_i_s1']*a['rho_s_s1']>=a['sigma_s1']**2


def test_pair_solomon_block_matches_independent_four_population_transition_network():
    rates=dipolar_pair_rates(shifts_ppm=(0.,0.))
    K=np.zeros((4,4))
    # Basis up/up, up/down, down/up, down/down. All rates are bidirectional.
    links=[(1,2,rates['w0_s1']),(0,3,rates['w2_s1']),
           (0,2,rates['w1_i_s1']),(1,3,rates['w1_i_s1']),
           (0,1,rates['w1_s_s1']),(2,3,rates['w1_s_s1'])]
    for i,j,k in links:
        K[j,i]+=k; K[i,j]+=k; K[i,i]-=k; K[j,j]-=k
    zi=np.array([1.,1.,-1.,-1.]); zs=np.array([1.,-1.,1.,-1.])
    p=np.ones(4)/4+.04*zi+.07*zs
    system=LiquidPoolSystem((1e30,1e30),(1e30,1e30),(1.,1.),(0.,0.),((0.,0.),(0.,0.)))
    g=add_solomon_pair(np.zeros((7,7)),system,0,1,rates)
    state=np.array([0.,0.,1+zi@p,0.,0.,1+zs@p,1.]); t=.73
    result=_matrix_exp(g,t)@state
    independent=_matrix_exp(K,t)@p
    assert [result[2]-1,result[5]-1]==pytest.approx([zi@independent,zs@independent],abs=1e-14)
    rho=rates['rho_i_s1']; sigma=rates['sigma_s1']
    total=(zi@p+zs@p)*np.exp(-(rho+sigma)*t)
    difference=(zi@p-zs@p)*np.exp(-(rho-sigma)*t)
    assert result[2]-1==pytest.approx((total+difference)/2,abs=1e-14)


def test_joint_equilibrium_no_direct_donor_exchange_and_zero_pair_regression():
    system=relay_pool_system(); rates=dipolar_pair_rates(); state=initial(system)
    assert not np.any(np.asarray(system.rates)[4]) and not np.any(np.asarray(system.rates)[:,4])
    g=relay_generator(system,120.,0.,rates)
    assert g@state==pytest.approx(np.zeros_like(state),abs=1e-14)
    zero={**rates,'rho_i_s1':0.,'rho_s_s1':0.,'sigma_s1':0.}
    assert relay_generator(system,120.,.5,zero)==pytest.approx(joint_generator(system,120.,.5),abs=0.)


def test_full_generator_matches_independent_cartesian_rk4():
    system=relay_pool_system(); rates=dipolar_pair_rates(); hz=150.; b1=.5; duration=.003
    state=initial(system); expected=_matrix_exp(relay_generator(system,hz,b1,rates),duration)@state
    w1=2*np.pi*GAMMA_BAR_HZ_T*b1*1e-6
    absorption=super_lorentzian_absorption_rate(b1,hz,12e-6)
    def derivative(s):
        m=s[:15].reshape(5,3); out=np.zeros_like(s)
        for i in range(5):
            x,y,z=m[i]; delta=2*np.pi*(hz-system.offset_hz[i])
            out[3*i:3*i+3]=[-x/system.t2[i]+delta*y,-delta*x-y/system.t2[i]+w1*z,-w1*y+(system.density[i]-z)/system.t1[i]]
            for j in range(5): out[3*i:3*i+3]+=system.rates[j][i]*m[j]-system.rates[i][j]*m[i]
        out[:3]-=.08*20*m[0]; out[2]+=20*s[15]
        out[15]=(.08-s[15])+.08*20*m[0,2]-20*s[15]-absorption*s[15]
        for i,j,rho in [(3,4,rates['rho_i_s1']),(4,3,rates['rho_s_s1'])]:
            out[3*i:3*i+2]-=rho/2*m[i,:2]
            out[3*i+2]-=rho*(m[i,2]-system.density[i])+rates['sigma_s1']*(m[j,2]-system.density[j])
        return out
    dt=duration/2048
    for _ in range(2048):
        k1=derivative(state);k2=derivative(state+dt*k1/2);k3=derivative(state+dt*k2/2);k4=derivative(state+dt*k3)
        state+=dt*(k1+2*k2+2*k3+k4)/6
    assert state==pytest.approx(expected,abs=3e-11)


def test_signed_relay_controls_targets_and_complete_replay():
    slow=run_cest_solomon(); fast=run_cest_solomon(tau_c_s=1e-10)
    assert slow['metrics']['relayed_noe_contrast']>.005 and slow['validation']['passed']
    assert fast['metrics']['relayed_noe_contrast']<0 and not fast['validation']['passed']
    assert slow['metrics']['unsaturated_water']==pytest.approx(1.,abs=2e-11)
    assert run_cest_solomon(**slow['provenance']['replay'])==slow
    assert not run_cest_solomon(target_min_relay_contrast=.9)['validation']['passed']


def test_breaking_bridge_exchange_removes_water_cross_relaxation_effect():
    r=run_cest_solomon(bridge_exchange_s1=0.)
    assert r['spectra']['full']==pytest.approx(r['spectra']['no_cross'],abs=2e-12)
    assert abs(r['metrics']['relayed_noe_contrast'])<2e-12


def test_no_cross_control_keeps_self_relaxation_and_thermal_source():
    system=relay_pool_system(); rates=dipolar_pair_rates()
    full=relay_generator(system,120.,.5,rates); control=relay_generator(system,120.,.5,rates,cross_relaxation=False)
    assert np.diag(full)==pytest.approx(np.diag(control),abs=0.)
    assert full[11,14]==-rates['sigma_s1'] and control[11,14]==0.
    assert control@initial(system) == pytest.approx(joint_generator(system,120.,.5)@initial(system),abs=2e-14)


def test_cw_pulsed_zero_gap_and_recovery_gap_effects():
    cw=run_cest_solomon(saturation_s=.4,offsets_ppm=[-3.5,3.5])
    pulsed=run_cest_solomon(saturation_s=.4,mode='pulsed',n_pulses=4,pulse_s=.1,gap_s=0.,offsets_ppm=[-3.5,3.5])
    for name in cw['spectra']: assert pulsed['spectra'][name]==pytest.approx(cw['spectra'][name],abs=2e-11)
    gap=run_cest_solomon(saturation_s=.55,mode='pulsed',n_pulses=4,pulse_s=.1,gap_s=.05,offsets_ppm=[-3.5,3.5])
    assert np.linalg.norm(np.array(gap['spectra']['full'])-cw['spectra']['full'])>1e-3


def test_sl_zero_offset_still_fails_and_gaussian_is_explicit_different_model():
    with pytest.raises(ValueError): run_cest_solomon(offsets_ppm=[-3.5,0.,3.5])
    r=run_cest_solomon(offsets_ppm=[-3.5,0.,3.5],lineshape='gaussian')
    assert np.isfinite(r['spectra']['full']).all() and r['provenance']['bound_lineshape']=='gaussian'


@pytest.mark.parametrize('patch',[{'distance_m':0.},{'tau_c_s':0.},{'tau_c_s':1e-6,'distance_m':1e-10},
    {'b0_t':float('nan')},{'shifts_ppm':(1.,float('inf'))}])
def test_invalid_dipolar_parameters_fail(patch):
    with pytest.raises(ValueError): dipolar_pair_rates(**patch)


@pytest.mark.parametrize('patch',[{'pair_fraction':0.},{'bridge_exchange_s1':-1.},{'max_work':1},
    {'max_duration_s':.1},{'donor_shift_ppm':3.5},{'target_min_relay_contrast':0.}])
def test_invalid_design_or_budget_fails(patch):
    with pytest.raises(ValueError): run_cest_solomon(**patch)


def test_pair_generator_rejects_unequal_densities_and_indefinite_relaxation():
    system=LiquidPoolSystem((1.,1.),(.1,.1),(1.,.5),(0.,0.),((0.,0.),(0.,0.)))
    with pytest.raises(ValueError,match='equal equilibrium'):
        add_solomon_pair(np.zeros((7,7)),system,0,1,dipolar_pair_rates())
    equal=LiquidPoolSystem((1.,1.),(.1,.1),(1.,1.),(0.,0.),((0.,0.),(0.,0.)))
    invalid={**dipolar_pair_rates(),'rho_i_s1':0.,'rho_s_s1':0.,'sigma_s1':1e-8}
    with pytest.raises(ValueError,match='semidefinite'):
        add_solomon_pair(np.zeros((7,7)),equal,0,1,invalid)


def test_pair_compilation_is_invariant_under_liquid_permutation():
    system=relay_pool_system(); rates=dipolar_pair_rates(); order=[0,4,2,1,3]
    permuted=LiquidPoolSystem(*(tuple(np.array(getattr(system,k))[order]) for k in ['t1','t2','density','offset_hz']),
        tuple(map(tuple,np.array(system.rates)[np.ix_(order,order)])))
    reference=relay_generator(system,150.,.5,rates)
    changed=add_solomon_pair(joint_generator(permuted,150.,.5),permuted,order.index(3),order.index(4),rates)
    a=_matrix_exp(reference,.17)@initial(system); b=_matrix_exp(changed,.17)@initial(permuted)
    assert b[2]==pytest.approx(a[2],abs=2e-12)


def test_live_source_edit_refuses_recording_with_stale_import(monkeypatch):
    import mrqlab_experiment.cest_solomon as module
    sources=module._source_files(); sources[next(iter(sources))]='0'*64
    monkeypatch.setattr(module,'_source_files',lambda:sources)
    with pytest.raises(ValueError,match='restart'):
        run_cest_solomon()


def test_high_field_domain_and_donor_metric_offset_are_required():
    with pytest.raises(ValueError): dipolar_pair_rates(b0_t=1e-6)
    with pytest.raises(ValueError,match='donor-resonant'): run_cest_solomon(offsets_ppm=[-2.,3.5])


def test_cli_roundtrip_compares_portable_pool_arrays_and_rejects_tampering(tmp_path):
    import json,subprocess,sys
    from pathlib import Path
    script=Path(__file__).resolve().parents[2]/'scripts/verify_solomon_cest.py'
    original=tmp_path/'evidence.json'; replay=tmp_path/'replay.json'
    def run(*args):
        return subprocess.run([sys.executable,str(script),*map(str,args)],capture_output=True,text=True,timeout=30)
    first=run('--output',original)
    assert first.returncode==0,first.stderr
    second=run('--output',replay,'--verify',original)
    assert second.returncode==0,second.stderr
    assert json.loads(original.read_text())==json.loads(replay.read_text())
    data=json.loads(original.read_text()); data['molecular_prior_sensitivity'][0]['spectra']['full'][0]+=.01
    tampered=tmp_path/'tampered.json'; tampered.write_text(json.dumps(data))
    absent=tmp_path/'must-not-exist.json'
    failed=run('--output',absent,'--verify',tampered)
    assert failed.returncode!=0 and 'evidence replay differs' in failed.stderr
    assert not absent.exists()
