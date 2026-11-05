import numpy as np
import pytest
from mrqlab_experiment.mrs_press import (coherence_mask,selected_pulse,finite_pulse_unitary,simulate_press_volume,run_press_basis)
from mrqlab_experiment.mrs_basis import spin_hamiltonian
from mrqlab_experiment.flow_imaging import selective_sinc


def test_coherence_projection_matches_independent_explicit_rf_phase_cycle():
    h,ops=spin_hamiltonian([-30.,10.],[[0.,7.],[7.,0.]])
    z=sum(a[2] for a in ops);rng=np.random.default_rng(17)
    rho=(rng.normal(size=h.shape)+1j*rng.normal(size=h.shape))*coherence_mask(z,-1)
    rf=selective_sinc(90.,duration_s=.001,thickness_m=.02,steps=32)
    u=finite_pulse_unitary(h,ops,rf,.003,flip=180.,phase=np.pi/2)
    expected=selected_pulse(rho,u,z,-1,1)
    independent=np.zeros_like(rho)
    for phase in np.arange(5)*2*np.pi/5:
        actual=finite_pulse_unitary(h,ops,rf,.003,flip=180.,phase=np.pi/2+phase)
        independent+=np.exp(2j*phase)*(actual@rho@actual.conj().T)/5
    assert expected==pytest.approx(independent,abs=3e-14)


@pytest.mark.parametrize('count',[1,2,3])
def test_whole_volume_projection_and_phase_cycle_agree(count):
    f=[-30.,10.,20.][:count]; j=np.ones((count,count))*7;np.fill_diagonal(j,0.)
    a=simulate_press_volume(f,j,grid_size=3,points=16,rf_steps=16)
    b=simulate_press_volume(f,j,grid_size=3,points=16,rf_steps=16,selection='phase_cycle')
    assert b['fid']==pytest.approx(a['fid'],abs=1e-13)
    assert b['spatial_response']==pytest.approx(a['spatial_response'],abs=1e-13)


def test_on_resonance_center_matches_ideal_singlet_and_complex_volume_integral():
    r=simulate_press_volume([0.],[[0.]],grid_size=17)
    p=r['provenance']; times=np.arange(256)*.0005
    assert r['center_fid']==pytest.approx(-1j*np.exp(-(p['echo_time_s']+times)/.15),abs=1e-13)
    assert np.sum(r['spatial_response'])*p['cell_volume_m3']==pytest.approx(r['fid_volume_m3'][0],abs=1e-18)
    assert r['fid']*p['nominal_volume_m3']==pytest.approx(r['fid_volume_m3'],abs=1e-20)
    assert r['centroid_m']==pytest.approx([0.,0.,0.],abs=1e-10)


def test_chemical_shift_displacement_matches_independent_rf_bandwidth_prediction():
    r=simulate_press_volume([-213.3],[[0.]],grid_size=33)
    from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
    shift=213.3/(GAMMA_BAR_HZ_T*r['provenance']['gradient_t_m'][1])
    assert r['centroid_m'][1:]==pytest.approx([shift,shift],abs=1e-7)
    assert r['centroid_m'][0]==pytest.approx(shift,abs=1e-5)


def test_space_rf_refinement_and_expanded_fov_are_measured_not_gain_fitted():
    a=simulate_press_volume([-213.3],[[0.]],grid_size=17,rf_steps=64)
    b=simulate_press_volume([-213.3],[[0.]],grid_size=25,rf_steps=64)
    c=simulate_press_volume([-213.3],[[0.]],grid_size=39,rf_steps=64,fov_scale=3.)
    rf128=simulate_press_volume([-213.3],[[0.]],grid_size=25,rf_steps=128)
    rf256=simulate_press_volume([-213.3],[[0.]],grid_size=25,rf_steps=256)
    assert np.linalg.norm(a['fid']-b['fid'])/np.linalg.norm(b['fid'])<.001
    assert np.linalg.norm(b['fid']-c['fid'])/np.linalg.norm(c['fid'])<.002
    first=np.linalg.norm(b['fid']-rf128['fid'])/np.linalg.norm(rf128['fid'])
    second=np.linalg.norm(rf128['fid']-rf256['fid'])/np.linalg.norm(rf256['fid'])
    assert first<.002 and second<first/3


def test_finer_grid_sample_full_fit_and_center_basis_mismatch_replay():
    r=run_press_basis(); bad=run_press_basis(basis_mode='center')
    assert r['validation']['passed'] and r['validation']['max_relative_amount_error']<.001
    assert not bad['validation']['passed'] and bad['validation']['max_relative_amount_error']>.5
    assert bad['fit']['relative_residual']>.02
    again=run_press_basis(**r['provenance']['replay'])
    assert np.array_equal(again['signal'],r['signal']) and again['provenance']==r['provenance']
    assert not run_press_basis(basis_j_hz=0.)['validation']['passed']


def test_resources_fail_before_rf_propagator_allocation(monkeypatch):
    import mrqlab_experiment.mrs_press as module
    def never(*args,**kwargs): raise AssertionError('should reject before RF allocation')
    monkeypatch.setattr(module,'finite_pulse_unitary',never)
    for patch in [{'max_work':1},{'max_memory_bytes':1}]:
        with pytest.raises(ValueError,match='preflight'): simulate_press_volume([-30.],[[0.]],**patch)
        with pytest.raises(ValueError,match='preflight'): run_press_basis(**patch)


@pytest.mark.parametrize('patch',[{'grid_size':4},{'grid_size':True},{'rf_steps':0},{'echo_s':.001},
    {'fov_scale':.5},{'dwell_s':.1},{'max_work':True}])
def test_invalid_spatial_sequence_or_budgets(patch):
    with pytest.raises(ValueError): simulate_press_volume([-30.],[[0.]],**patch)


def test_rf_discretization_target_failure_is_retained_without_relabelling():
    r=run_press_basis(target_rf_error=1e-5)
    assert not r['validation']['passed']
    assert r['validation']['max_relative_amount_error']<.001
    assert r['validation']['max_rf_error']>r['validation']['target_rf_error']


def test_independent_cli_portable_roundtrip_and_complex_fid_tamper_rejection(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys
    root=Path(__file__).resolve().parents[2]
    command=[sys.executable,str(root/'scripts/verify_press_volume.py')]
    first=tmp_path/'first.json';second=tmp_path/'second.json'
    subprocess.run(command+['--output',str(first)],check=True,capture_output=True,text=True)
    subprocess.run(command+['--output',str(second),'--verify',str(first)],check=True,capture_output=True,text=True)
    data=json.loads(first.read_text());data['volume_fit']['signal'][0]['imag']+=.001
    first.write_text(json.dumps(data));third=tmp_path/'must-not-exist.json'
    rejected=subprocess.run(command+['--output',str(third),'--verify',str(first)],capture_output=True,text=True)
    assert rejected.returncode!=0 and 'replay differs' in rejected.stderr
    assert not third.exists()
