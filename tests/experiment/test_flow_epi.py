import numpy as np
import pytest
from mrqlab_experiment.flow_epi import SpatialMovingEnsemble,epi_waveform,run_flow_epi,_project
from mrqlab_experiment.pulsatile_flow import WomersleyPipe
from mrqlab_experiment.flow_imaging import GAMMA
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T


def test_actual_sampled_gradient_moments_venc_and_epi_grid_are_independent_integrals():
    w=epi_waveform();at=0.;m0=np.zeros(3);m1=np.zeros(3);encoding=0.;grid=[]
    for c in w['commands']:
        dt=c['duration_s'];g=np.array(c['gradient_t_m']);m0+=g*dt;m1+=g*((at+dt)**2-at**2)/2
        if c['kind']=='velocity_encoding': encoding+=g[2]*((at+dt)**2-at**2)/2
        at+=dt
        if c['adc'] is not None:
            y,x=c['adc'];grid.append(-GAMMA_BAR_HZ_T*m0[:2]-np.array([x-8,y-8])/.012)
    assert np.max(abs(np.asarray(grid)))<1e-8 and m0==pytest.approx([0,0,0],abs=1e-19)
    assert 2*encoding*GAMMA*.05==pytest.approx(np.pi,rel=1e-13)
    assert w['peak_gradient_t_m']<.04 and w['nominal_slew_t_m_s']<150
    assert len(w['adc'])==256 and w['duration_s']==pytest.approx(.036)
    assert w['adc'][0]['index']==[0,0] and w['adc'][16]['index']==[1,15]


def test_every_complex_adc_matches_independent_constant_velocity_bloch_solution():
    pipe=WomersleyPipe(oscillating_gradient_pa_m=0.)
    radius=np.array([0.,.001,.0018]);z=np.array([-.002,.001,.0025]);xy=np.array([[.0002,-.001],[.0012,.0001],[-.0008,.0017]])
    v=pipe.velocity(radius,0.);spins=SpatialMovingEnsemble(z,xy,motion=pipe.motion(radius),off_hz=7.,t2_s=.15)
    initial=np.array([1+.3j,-.2+.7j,.5-.1j]);spins.state[:,0]=initial.real;spins.state[:,1]=initial.imag
    time=0.;area=np.zeros(3);first=np.zeros(3);errors=[]
    for c in epi_waveform()['commands']:
        dt=c['duration_s'];g=np.array(c['gradient_t_m']);area+=g*dt;first+=g*(time*dt+dt*dt/2);time+=dt
        spins.advance(dt,gx_t_m=g[0],gy_t_m=g[1],gz_t_m=g[2])
        if c['adc'] is not None:
            reference=initial*np.exp(-time/.15)*np.exp(1j*(2*np.pi*7*time+GAMMA*(xy@area[:2]+z*area[2]+v*first[2])))
            actual=spins.state[:,0]+1j*spins.state[:,1];errors.append(np.max(abs(actual-reference)))
    assert max(errors)<2e-12
    assert spins.positions()==pytest.approx(z+v*time,abs=1e-14)


def test_accelerating_gradient_phase_matches_independent_time_quadrature():
    pipe=WomersleyPipe();r=np.array([.0003,.0017]);z=np.array([.0001,-.001]);xy=np.zeros((2,2))
    spins=SpatialMovingEnsemble(z,xy,motion=pipe.motion(r));spins.state[:,0]=1.
    commands=epi_waveform()['commands'][:34];motion=pipe.motion(r)
    for c in commands: spins.advance(c['duration_s'],gz_t_m=c['gradient_t_m'][2])
    errors=[]
    for count in [33,129]:
        reference_phase=np.zeros(2);at=0.
        for c in commands:
            dt=c['duration_s'];g=c['gradient_t_m'][2]
            t=np.linspace(at,at+dt,count);positions=z+np.array([motion.displacement(s) for s in t])
            reference_phase+=GAMMA*g*np.trapezoid(positions,t,axis=0);at+=dt
        errors.append(np.max(abs(spins.state[:,0]+1j*spins.state[:,1]-np.exp(-at/.15+1j*reference_phase))))
    assert errors[-1]<1e-9 and errors[-1]<errors[0]/8


def test_receive_cell_overlap_integrates_fixed_volume_without_fitted_normalization():
    dz=.0008;thickness=.005
    for offset in [0.,.000123,.00071]:
        z=np.arange(-20,21)*dz+offset
        spins=SpatialMovingEnsemble(z,np.zeros((len(z),2)))
        item=dict(spins=spins,cell_width_m=np.full(len(z),dz),pixel_ids=np.zeros(len(z),int),pixels=np.array([0]))
        longitudinal,count=_project(item,1,thickness,longitudinal=True)
        assert longitudinal[0,0]==pytest.approx(1.,abs=1e-14) and count>=3
        spins.state[:,2]=0.;spins.state[:,0]=.3;spins.state[:,1]=-.4
        transverse,_=_project(item,1,thickness)
        assert transverse[0,0]==pytest.approx(.3-.4j,abs=1e-14)


@pytest.fixture(scope='module')
def default_run(): return run_flow_epi(axial_spins=201)


def test_actual_kspace_inverts_without_gain_fit_and_exposes_failed_targets(default_run):
    r=default_run
    assert len(r['images'])==2 and len(r['velocity_pairs'])==1
    for image in r['images']:
        # Independent direct inverse Fourier sum, not the implementation's FFT.
        k=image['kspace'];n=len(k);coord=np.arange(n)-n//2
        reference=np.array([[np.sum(k*np.exp(2j*np.pi*(coord[None,:]*x+coord[:,None]*y)/n))/n**2 for x in coord] for y in coord])
        assert image['image']==pytest.approx(reference,abs=2e-14)
    assert not r['validation']['passed']
    assert r['validation']['max_frozen_image_error']>.05
    assert r['provenance']['estimated_work']<=r['provenance']['planned_work']<=200000000
    assert r['provenance']['estimated_peak_memory_bytes']<=134217728
    assert run_flow_epi(**r['provenance']['replay'])['provenance']==r['provenance']


def test_no_dir_steady_flow_is_labelled_control_and_recovers_moment_velocity():
    r=run_flow_epi(preparation='none',oscillating_gradient_pa_m=0.)
    p=r['velocity_pairs'][0]
    assert p['velocity_rmse_m_s']<.0005 and p['observed_blood_fraction']==1.
    assert not r['validation']['passed'] and r['validation']['max_abs_blood_mz']>.9
    assert r['design']['preparation']=='none'
    assert p['instantaneous_reference_m_s']==pytest.approx(p['gradient_moment_reference_m_s'],abs=1e-12)


def test_mid_epi_interruption_keeps_partial_adc_and_never_fills_missing_samples():
    r=run_flow_epi(r_peaks_s=[0.,.917],observation_end_s=1.4,axial_spins=201)
    first=r['executions'][0]['tissues']['blood']
    assert 0<len(first['samples'])<256 and not first['completed'] and first['end_s']==pytest.approx(.917)
    assert all(a['time_s']<=.917+1e-14 for a in first['samples'])
    assert not r['images'] and not r['velocity_pairs'] and not r['validation']['passed']
    assert 'max_velocity_rmse_m_s' not in r['validation']
    assert first['image'] is None and first['kspace'] is None


def test_no_pair_has_no_invented_velocity_or_observation_beyond_horizon():
    r=run_flow_epi(r_peaks_s=[0.],observation_end_s=1.1,axial_spins=201)
    assert len(r['images'])==1 and not r['velocity_pairs'] and not r['validation']['passed']
    assert 'max_velocity_rmse_m_s' not in r['validation']
    empty=run_flow_epi(r_peaks_s=[0.],observation_end_s=.5,axial_spins=201)
    assert not empty['images'] and not empty['velocity_pairs']
    assert empty['executions'][0]['tissues']['blood']['end_s']==pytest.approx(.5)


def test_future_triggers_do_not_change_scheduling_or_encoding_polarity():
    a=run_flow_epi(r_peaks_s=[0.,1.2],observation_end_s=2.4,axial_spins=201)
    b=run_flow_epi(r_peaks_s=[0.,1.2,1.8],observation_end_s=2.9,axial_spins=201)
    keys=['decision_s','preparation_s','scheduled','rr_estimate_s','readout_s']
    assert [{k:g[k] for k in keys} for g in a['gates']]==[{k:g[k] for k in keys} for g in b['gates'][:2]]
    assert [row['encoding_sign'] for row in a['executions']]==[row['encoding_sign'] for row in b['executions'][:2]]


def test_velocity_alias_is_reported_not_unwrapped_to_match_reference():
    r=run_flow_epi(preparation='none',mean_gradient_pa_m=400.,oscillating_gradient_pa_m=0.,axial_spins=801)
    assert r['velocity_pairs'][0]['reference_exceeds_venc'] and not r['validation']['passed']
    assert np.max(abs(r['velocity_pairs'][0]['velocity_m_s']))<=.05+1e-14


@pytest.mark.parametrize('patch',[{'max_work':1},{'max_memory_bytes':1},{'rf_steps':True},{'matrix_size':9},
    {'dwell_s':1e-6},{'venc_m_s':.001},{'ramp_steps':0},{'preparation':'ideal-reset'},
    {'fov_m':.005},{'signal_floor':0.},{'observation_end_s':11.}])
def test_bad_geometry_budget_or_physical_design_rejected(patch):
    with pytest.raises(ValueError): run_flow_epi(**patch)
