import numpy as np
import pytest
from mrqlab_experiment.pulsatile_flow import WomersleyPipe,bessel_j,pipe_reservoir
from mrqlab_experiment.causal_gating import plan_prospective_readouts
from mrqlab_experiment.pulsatile_dir import run_pulsatile_dir
from mrqlab_experiment.flow_imaging import MovingBlochEnsemble,GAMMA


@pytest.mark.parametrize('order',[0,1])
@pytest.mark.parametrize('z',[1.+1j,8.-8j,.001j])
def test_bessel_series_matches_independent_integral(order,z):
    theta=np.linspace(0,np.pi,8193)
    reference=np.trapezoid(np.cos(order*theta-z*np.sin(theta)),theta)/np.pi
    assert bessel_j(order,z)==pytest.approx(reference,rel=2e-12,abs=2e-12)


def test_velocity_satisfies_no_slip_and_steady_poiseuille_flux():
    pipe=WomersleyPipe(oscillating_gradient_pa_m=0.)
    r=np.linspace(0,pipe.radius,21)
    expected=100.*(pipe.radius**2-r*r)/(4*.0035)
    for t in [0.,.31,2.3]:
        assert pipe.velocity(r,t)==pytest.approx(expected,abs=1e-14)
        assert pipe.velocity(pipe.radius,t)==pytest.approx(0.,abs=1e-15)
        assert pipe.volume_flow_m3_s(t)==pytest.approx(np.pi*pipe.radius**4*100/(8*.0035),rel=1e-14)


def test_harmonic_solution_matches_independent_finite_volume_momentum_solve():
    pipe=WomersleyPipe(mean_gradient_pa_m=0.)
    errors=[]
    for n in [32,64,128]:
        dr=pipe.radius/n; r=(np.arange(n)+.5)*dr; faces=np.arange(n+1)*dr
        lower=pipe.nu*faces[:-1]/(r*dr**2); upper=pipe.nu*faces[1:]/(r*dr**2)
        upper[-1]*=2 # no-slip wall lies half a cell from final center
        L=np.diag(-lower-upper)+np.diag(lower[1:],-1)+np.diag(upper[:-1],1)
        independent=np.linalg.solve(1j*pipe.omega*np.eye(n)-L,np.full(n,pipe.harmonic_acceleration))
        analytic=pipe.coefficients(r)[1]
        errors.append(np.linalg.norm(independent-analytic)/np.linalg.norm(analytic))
    assert errors[-1]<1e-4
    assert errors[1]<errors[0]/3 and errors[2]<errors[1]/3


def test_cross_section_quadrature_converges_to_analytic_flux_and_allows_backflow():
    pipe=WomersleyPipe(mean_gradient_pa_m=20.,oscillating_gradient_pa_m=300.)
    errors=[]
    for n in [8,16,32]:
        r=pipe.radius*np.sqrt((np.arange(n)+.5)/n)
        errors.append(abs(np.pi*pipe.radius**2*pipe.velocity(r,.37).mean()-pipe.volume_flow_m3_s(.37)))
    assert errors[1]<errors[0]/3 and errors[2]<errors[1]/3
    times=np.linspace(0,1,100)
    assert min(pipe.volume_flow_m3_s(t) for t in times)<0


def test_motion_displacement_gradient_integral_and_finite_rf_rk4_reference():
    pipe=WomersleyPipe(); radius=np.array([.0003,.0017]); motion=pipe.motion(radius)
    z=np.array([.0001,-.001]); a=.123; b=.731
    times=np.linspace(a,b,20001)
    positions=np.array([motion.positions(z,t) for t in times])
    assert motion.position_integral(z,a,b)==pytest.approx(np.trapezoid(positions,times,axis=0),abs=1e-11)
    assert (motion.displacement(b+1e-6)-motion.displacement(b-1e-6))/(2e-6)==pytest.approx(pipe.velocity(radius,b),abs=1e-10)
    spins=MovingBlochEnsemble(z,0.,motion=motion,off_hz=13.); spins.hard_rf(90.); spins.advance(a)
    before=spins.state[:,0]+1j*spins.state[:,1]; g=.003
    expected=before*np.exp(-(b-a)/.15)*np.exp(1j*(2*np.pi*13*(b-a)+GAMMA*g*motion.position_integral(z,a,b)))
    spins.advance(b-a,gz_t_m=g)
    assert spins.state[:,0]+1j*spins.state[:,1]==pytest.approx(expected,abs=2e-12)
    # Independent RK4 Bloch ODE with the analytic time-varying trajectory.
    duration=.002; b1=3.+2j; g=.001; state=np.array([0.,0.,1.]); dt=duration/2048
    def derivative(t,s):
        omega=np.array([GAMMA*b1.real*1e-6,GAMMA*b1.imag*1e-6,GAMMA*g*motion.positions(z,t)[0]+2*np.pi*17])
        return np.cross(omega,s)+np.array([-s[0]/.08,-s[1]/.08,(1-s[2])/1.2])
    for i in range(2048):
        t=i*dt; k1=derivative(t,state); k2=derivative(t+dt/2,state+dt*k1/2)
        k3=derivative(t+dt/2,state+dt*k2/2); k4=derivative(t+dt,state+dt*k3)
        state+=dt*(k1+2*k2+2*k3+k4)/6
    errors=[]
    for steps in [32,64,128]:
        spins=MovingBlochEnsemble(z[:1],0.,motion=pipe.motion(radius[:1]),t1_s=1.2,t2_s=.08,off_hz=17.)
        for _ in range(steps): spins.advance(duration/steps,b1_uT=b1,gz_t_m=g)
        errors.append(np.linalg.norm(spins.state[0]-state))
    assert errors[-1]<2e-6
    assert errors[1]<errors[0]/3 and errors[2]<errors[1]/3


def test_reservoir_bounds_cover_reverse_and_forward_flow_without_wrapping():
    pipe=WomersleyPipe(mean_gradient_pa_m=20.,oscillating_gradient_pa_m=300.)
    z,motion,w,r=pipe_reservoir(pipe,end_s=3.,thickness_m=.005,radial_rings=8,axial_spins=401)
    assert np.all(w>0)
    for time in np.linspace(0,3,101):
        positions=motion.positions(z,time).reshape(8,401)
        assert np.all(positions[:,0]<-.0025) and np.all(positions[:,-1]>.0025)


def test_causal_decisions_are_prefix_invariant_and_last_trigger_can_complete():
    a=plan_prospective_readouts([0.,1.2],delay_s=.9,observation_end_s=2.3)
    b=plan_prospective_readouts([0.,1.2,1.65,2.85],delay_s=.9,observation_end_s=4.)
    keys=['decision_s','scheduled','rr_estimate_s','previous_rr_s','history_rr_s','preparation_s','readout_s']
    assert [{k:g[k] for k in keys} for g in a]==[{k:g[k] for k in keys} for g in b[:2]]
    assert a[-1]['accepted'] and a[-1]['previous_rr_s']==1.2
    assert b[1]['scheduled'] and not b[1]['accepted'] and b[1]['cancelled_s']==1.65
    assert not b[2]['scheduled'] and b[2]['rejection']=='previous_rr_outside_range'


def test_interrupted_preparation_evolves_state_and_cannot_be_silently_dropped():
    r=run_pulsatile_dir(r_peaks_s=[0.,.45,1.65],observation_end_s=2.8,radial_rings=4,axial_spins=201)
    no_first=run_pulsatile_dir(r_peaks_s=[1.65],observation_end_s=2.8,radial_rings=4,axial_spins=201)
    assert len(r['executions'])==2 and len(r['readouts'])==1
    assert r['executions'][0]['tissues']['blood']['stage']=='inversion_recovery'
    assert r['provenance']['actual_hard_rf_count']==2
    assert abs(r['readouts'][0]['tissues']['blood']['mean_mz']-no_first['readouts'][0]['tissues']['blood']['mean_mz'])>.05
    assert not r['validation']['passed'] and r['validation']['interrupted_fraction']==.5
    assert run_pulsatile_dir(**r['provenance']['replay'])==r


@pytest.mark.parametrize('cancel,stage',[(.006,'selective_reinversion'),(.905,'excitation'),(.908,'rephaser')])
def test_partial_rf_and_rephaser_are_clipped_at_arriving_trigger(cancel,stage):
    r=run_pulsatile_dir(r_peaks_s=[0.,cancel],observation_end_s=1.9,radial_rings=4,axial_spins=201)
    first=r['executions'][0]['tissues']['blood']
    assert first['stage']==stage and first['end_s']==pytest.approx(cancel,abs=1e-13)
    assert r['gates'][0]['scheduled'] and not r['gates'][0]['accepted']
    assert first['finite_rf_energy_uT2_s']>0
    assert r['provenance']['estimated_work']<=r['provenance']['planned_work']


def test_no_completed_readout_is_explicit_failure_with_no_invented_measurements():
    r=run_pulsatile_dir(r_peaks_s=[0.],observation_end_s=.5,radial_rings=4,axial_spins=201)
    assert not r['readouts'] and not r['validation']['passed']
    assert 'max_abs_blood_mz' not in r['validation'] and 'min_abs_wall_mz' not in r['validation']
    assert r['objective_loss']==3. and r['gates'][0]['rejection']=='observation_ended'


@pytest.mark.parametrize('patch',[{'max_work':1},{'observation_end_s':2.},{'radius_m':0.},
    {'radial_rings':True},{'rf_steps':0},{'mean_gradient_pa_m':float('nan')},
    {'observation_end_s':31.},{'frequency_hz':1000.},{'initial_rr_s':0.}])
def test_invalid_pulsatile_designs_and_preflight_budgets(patch):
    with pytest.raises(ValueError): run_pulsatile_dir(**patch)


def test_zero_harmonic_motion_matches_existing_constant_velocity_bloch():
    pipe=WomersleyPipe(oscillating_gradient_pa_m=0.); radii=np.array([0.,.001,.0018]); z=np.array([.0001,0.,-.002])
    a=MovingBlochEnsemble(z,0.,motion=pipe.motion(radii))
    b=MovingBlochEnsemble(z,pipe.velocity(radii,0.))
    z[:]=99. # neither ensemble retains an alias to external initial positions
    for _ in range(50):
        a.advance(.0001,b1_uT=2.+1j,gz_t_m=.003)
        b.advance(.0001,b1_uT=2.+1j,gz_t_m=.003)
    assert a.positions()==pytest.approx(b.positions(),abs=1e-14)
    assert a.state==pytest.approx(b.state,abs=1e-12)


def test_finite_rf_and_volume_quadrature_refinement_retain_target_failure():
    results=[run_pulsatile_dir(r_peaks_s=[0.],observation_end_s=1.2,radial_rings=n,axial_spins=m,rf_steps=k)
             for n,m,k in [(4,201,128),(8,401,128),(16,801,256)]]
    blood=[r['readouts'][0]['tissues']['blood']['mean_mz'] for r in results]
    wall=[r['readouts'][0]['tissues']['wall']['mean_mz'] for r in results]
    assert abs(blood[-1]-blood[-2])<.002 and abs(wall[-1]-wall[-2])<1e-4
    assert all(not r['validation']['passed'] for r in results)



def test_declared_laminar_domain_and_causal_prior_are_enforced():
    with pytest.raises(ValueError,match='Reynolds'):
        WomersleyPipe(radius_m=.005,frequency_hz=.1,mean_gradient_pa_m=2000.)
    with pytest.raises(ValueError,match='initial RR'):
        plan_prospective_readouts([0.],delay_s=.9,observation_end_s=2.,initial_rr_s=2.)
