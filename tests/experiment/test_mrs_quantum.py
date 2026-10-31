import numpy as np
import pytest
from mrqlab_experiment.mrs_basis import spin_hamiltonian,spin_operators,_unitary
from mrqlab_experiment.mrs_quantum import simulate_quantum_fid,run_mrs_quantum
from mrqlab_physics.ops.quantum_relaxation import lindblad_generator,local_spin_bath,quantum_channel,periodic_density


def test_single_spin_matches_closed_t1_t2_detuning_and_independent_driven_bloch():
    ops=spin_operators(1);bath,equilibrium,_=local_spin_bath(ops,[.7],[.12],polarization=.04)
    h=2*np.pi*37*ops[0][2];rho=np.array([[.8,.1+.07j],[.1-.07j,.2]])
    duration=.023;out=(quantum_channel(lindblad_generator(h,bath),duration)@rho.reshape(-1,order='F')).reshape((2,2),order='F')
    assert out[0,0]==pytest.approx(.52+(.8-.52)*np.exp(-duration/.7),abs=1e-14)
    assert out[0,1]==pytest.approx(rho[0,1]*np.exp(-duration/.12-2j*np.pi*37*duration),abs=1e-14)
    assert lindblad_generator(h,bath)@equilibrium.reshape(-1,order='F')==pytest.approx(np.zeros(4),abs=1e-14)
    omega=130.;delta=2*np.pi*37;generator=np.array([[-1/.12,-delta,0,0],[delta,-1/.12,-omega,0],[0,omega,-1/.7,.04/.7],[0,0,0,0]])
    eigen,vectors=np.linalg.eig(generator);reference=(vectors*np.exp(eigen*duration))@np.linalg.inv(vectors)@np.array([.2,-.14,.6,1.])
    out=(quantum_channel(lindblad_generator(h+omega*ops[0][0],bath),duration)@rho.reshape(-1,order='F')).reshape((2,2),order='F')
    measured=np.array([2*out[0,1].real,-2*out[0,1].imag,(out[0,0]-out[1,1]).real])
    assert measured==pytest.approx(reference[:3].real,abs=1e-13)


def test_channel_is_trace_preserving_completely_positive_and_does_not_clip():
    h,ops=spin_hamiltonian([-100.,130.],[[0.,7.],[7.,0.]])
    bath,_,_=local_spin_bath(ops,[.4,1.2],[.08,.15],polarization=.03)
    channel=quantum_channel(lindblad_generator(h+55*ops[0][0],bath),.037)
    choi=np.zeros((16,16),complex)
    for a in range(4):
        for b in range(4):
            e=np.zeros((4,4));e[a,b]=1.
            image=(channel@e.reshape(-1,order='F')).reshape((4,4),order='F')
            choi[4*a:4*(a+1),4*b:4*(b+1)]=image
            assert np.trace(image)==pytest.approx(float(a==b),abs=1e-12)
    assert np.linalg.eigvalsh(choi).min()>-1e-12
    assert np.max(abs(choi-choi.conj().T))<1e-12


def test_uncoupled_local_bath_matches_independent_thermal_kraus_maps():
    _,ops=spin_hamiltonian([0.,0.],np.zeros((2,2)));t1=[.5,1.3];t2=[.09,.2];p=.04;time=.17
    bath,_,_=local_spin_bath(ops,t1,t2,polarization=p)
    vector=np.array([1.,1j,-.3,.4j]);vector/=np.linalg.norm(vector);rho=np.outer(vector,vector.conj())
    reference=rho.copy()
    for spin,(a,b) in enumerate(zip(t1,t2)):
        q=(1+p)/2;decay=np.exp(-time/a);gamma=1-decay
        local=[np.sqrt(q)*np.diag([1,np.sqrt(decay)]),np.sqrt(q)*np.array([[0,np.sqrt(gamma)],[0,0]]),
            np.sqrt(1-q)*np.diag([np.sqrt(decay),1]),np.sqrt(1-q)*np.array([[0,0],[np.sqrt(gamma),0]])]
        embedded=[np.kron(k,np.eye(2)) if spin==0 else np.kron(np.eye(2),k) for k in local]
        reference=sum(k@reference@k.conj().T for k in embedded)
        factor=np.exp(-time*(1/b-1/(2*a)));z=np.kron(np.diag([1.,-1.]),np.eye(2)) if spin==0 else np.kron(np.eye(2),np.diag([1.,-1.]))
        reference=(1+factor)/2*reference+(1-factor)/2*z@reference@z
    out=(quantum_channel(lindblad_generator(np.zeros((4,4)),bath),time)@rho.reshape(-1,order='F')).reshape((4,4),order='F')
    assert out==pytest.approx(reference,abs=1e-13)


def test_correlated_order_relaxes_with_constituent_rates_not_one_scalar_envelope():
    ops=spin_operators(2);bath,_,_=local_spin_bath(ops,[.5,1.3],[.09,.2])
    correlation=ops[0][0]@ops[1][2];time=.08
    out=(quantum_channel(lindblad_generator(np.zeros((4,4)),bath),time)@correlation.reshape(-1,order='F')).reshape((4,4),order='F')
    assert out==pytest.approx(correlation*np.exp(-time*(1/.09+1/1.3)),abs=1e-14)


def test_three_spin_bath_and_coherent_channel_preserve_full_density():
    h,ops=spin_hamiltonian([-70.,-25.,20.],[[0.,7.,2.],[7.,0.,10.],[2.,10.,0.]])
    bath,eq,_=local_spin_bath(ops,[.7,1.1,1.8],[.08,.1,.15],polarization=.02)
    generator=lindblad_generator(h,bath)
    assert np.max(abs(generator@eq.reshape(-1,order='F')))<1e-12
    u=_unitary(sum(a[0] for a in ops),.7);rho=u@eq@u.conj().T
    out=(quantum_channel(generator,.031)@rho.reshape(-1,order='F')).reshape((8,8),order='F')
    assert np.trace(out)==pytest.approx(1.,abs=1e-12)
    assert np.linalg.eigvalsh(out).min()>0


def test_periodic_solution_matches_explicit_long_cycle_iteration_and_trace():
    ops=spin_operators(1);bath,eq,_=local_spin_bath(ops,[.8],[.12])
    rf=quantum_channel(lindblad_generator(150*ops[0][0],bath),.01)
    free=quantum_channel(lindblad_generator(np.zeros((2,2)),bath),.2)
    cycle=free@np.diag([1.,0.,0.,1.])@rf
    steady,diagnostics=periodic_density(cycle,2);state=eq.reshape(-1,order='F')
    for _ in range(512): state=cycle@state
    assert steady==pytest.approx(state.reshape((2,2),order='F'),abs=1e-12)
    assert diagnostics['fixed_point_residual']<1e-12
    assert np.trace(steady)==pytest.approx(1.,abs=1e-14)
    with pytest.raises(ValueError,match='nonunique'): periodic_density(np.eye(4),2)


def test_hard_pulse_tr_limit_matches_independent_affine_bloch_cycle():
    t1=.8;t2=.12;p=.01;te=.03;tr=.3;dwell=.0005;points=32;angle=np.pi/3
    def free(t):
        out=np.diag([np.exp(-t/t2),np.exp(-t/t2),np.exp(-t/t1),1.]);out[2,3]=p*(1-np.exp(-t/t1));return out
    rx=np.eye(4);rx[1:3,1:3]=[[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]]
    ry=np.diag([-1.,1.,-1.,1.]);echo=free(te/4)@ry@free(te/2)@ry@free(te/4)@rx
    cycle=free(tr-te-points*dwell)@np.diag([0.,0.,1.,1.])@free(points*dwell)@echo
    initial=np.r_[np.linalg.solve(np.eye(3)-cycle[:3,:3],cycle[:3,3]),1.];at=echo@initial
    reference=(at[0]+1j*at[1])/p*np.exp(-np.arange(points)*dwell/t2)
    fid,record=simulate_quantum_fid([0.],[[0.]],t1_s=[t1],t2_s=[t2],echo_s=te,repetition_s=tr,
        dwell_s=dwell,points=points,rf_duration_s=1e-8,rf_steps=32,excitation_degrees=60.)
    assert fid==pytest.approx(reference,abs=2e-8)
    assert record['diagnostics']['cycle_return_error']<1e-12


@pytest.fixture(scope='module')
def quantum_run(): return run_mrs_quantum()


def test_matched_quantum_basis_uses_independent_finer_sample_and_all_physical_nodes(quantum_run):
    r=quantum_run
    assert r['validation']['passed'] and r['validation']['numerical_refinement_passed']
    assert r['fit']['amounts']==pytest.approx([.02,.008],rel=2e-4)
    assert len(r['simulations'])==8 and len(r['rf_refinement_errors'])==4
    assert r['provenance']['estimated_work']<=r['provenance']['planned_work']<=1500000000
    for row in r['simulations']:
        t=row['timing'];path=row['trajectory'];assert t['adc_end_s']+t['recovery_s']==pytest.approx(.6)
        assert t['adc_interval_s']==256*.0005
        assert row['diagnostics']['physical_state_passed']
        assert len(path['times_s'])==len(path['longitudinal'])==len(path['stages'])
        assert np.trace(path['start_density'])==pytest.approx(1.,abs=1e-12)


def test_equilibrium_and_wrong_t1_bases_fail_without_gain_calibration():
    equilibrium=run_mrs_quantum(basis_mode='equilibrium');wrong=run_mrs_quantum(basis_t1_scale=2.)
    assert not equilibrium['validation']['passed'] and equilibrium['validation']['max_relative_amount_error']>.5
    assert not wrong['validation']['passed'] and wrong['validation']['max_relative_amount_error']>.7
    assert wrong['fit']['relative_residual']<.02  # a good fit is not sufficient
    assert equilibrium['validation']['numerical_refinement_passed']


def test_short_tr_and_strict_rf_fail_distinct_gates_and_finite_dummies_are_explicit():
    short=run_mrs_quantum(repetition_s=.18);rf=run_mrs_quantum(target_rf_error=1e-6)
    assert not short['validation']['passed'] and short['validation']['min_signal_fraction']<.2
    assert short['validation']['numerical_refinement_passed']
    assert not rf['validation']['passed'] and not rf['validation']['numerical_refinement_passed']
    r=run_mrs_quantum(preparation='finite_dummies',dummy_scans=0)
    assert r['validation']['passed']
    assert r['simulations'][0]['diagnostics']['cycle_return_error']>1e-4
    assert r['simulations'][0]['diagnostics']['preparation']=='finite_dummies'


@pytest.mark.parametrize('patch',[dict(repetition_s=.1),dict(max_work=1),dict(max_memory_bytes=1),dict(rf_steps=True),
    dict(refine_rf_steps=32),dict(refine_rf_steps=256),dict(polarization=1.),dict(preparation='fake_reset'),
    dict(amounts=[1.,2.,3.]),dict(target_state_error=0.),dict(dummy_scans=-1),dict(points=10000),dict(dwell_s=.1)])
def test_invalid_complete_quantum_workflow_fails_closed(patch):
    with pytest.raises(ValueError): run_mrs_quantum(**patch)


def test_nonphysical_rates_and_malformed_liouvillian_are_rejected():
    with pytest.raises(ValueError,match='T2<=2'): local_spin_bath(spin_operators(1),[.1],[.21])
    with pytest.raises(ValueError,match='Hermitian'): lindblad_generator([[0,1],[0,0]],[])
    with pytest.raises(ValueError): quantum_channel(np.eye(9),.1)
