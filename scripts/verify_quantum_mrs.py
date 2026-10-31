"""Recompute full quantum MRS records, independent Bloch and density-ODE limits."""
import argparse
from hashlib import sha256
from pathlib import Path
import json
import numpy as np
from mrqlab_experiment.mrs_basis import spin_hamiltonian
from mrqlab_experiment.mrs_quantum import simulate_quantum_fid,run_mrs_quantum
from mrqlab_physics.ops.quantum_relaxation import local_spin_bath,lindblad_generator,quantum_channel
from mrqlab_experiment.study_records import source_manifest,runtime_manifest
from mrqlab_api.research import serializable
from mrqlab_api.scientific_records import create_scientific_record,write_portable,read_portable


def digest(value): return sha256(json.dumps(serializable(value),sort_keys=True,allow_nan=False).encode()).hexdigest()


def independent_hard_bloch():
    t1=.8;t2=.12;p=.01;te=.03;tr=.3;points=32;dwell=.0005;angle=np.pi/3
    def free(t):
        a=np.diag([np.exp(-t/t2),np.exp(-t/t2),np.exp(-t/t1),1.]);a[2,3]=p*(1-np.exp(-t/t1));return a
    rx=np.eye(4);rx[1:3,1:3]=[[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]]
    ry=np.diag([-1.,1.,-1.,1.]);echo=free(te/4)@ry@free(te/2)@ry@free(te/4)@rx
    cycle=free(tr-te-points*dwell)@np.diag([0.,0.,1.,1.])@free(points*dwell)@echo
    initial=np.r_[np.linalg.solve(np.eye(3)-cycle[:3,:3],cycle[:3,3]),1.];r=echo@initial
    reference=(r[0]+1j*r[1])/p*np.exp(-np.arange(points)*dwell/t2);rows=[]
    for duration in [1e-6,1e-7,1e-8]:
        signal,record=simulate_quantum_fid([0.],[[0.]],t1_s=[t1],t2_s=[t2],echo_s=te,repetition_s=tr,points=points,
            dwell_s=dwell,rf_duration_s=duration,rf_steps=32,excitation_degrees=60.)
        rows.append(dict(rf_duration_s=duration,max_fid_error=float(np.max(abs(signal-reference))),
            cycle_return_error=record['diagnostics']['cycle_return_error']))
    if rows[-1]['max_fid_error']>2e-8 or not rows[-1]['max_fid_error']<rows[0]['max_fid_error']/90:
        raise AssertionError('independent affine Bloch hard-pulse/TR limit failed')
    return dict(initial_bloch=initial.tolist(),reference_fid=reference,refinement=rows)


def independent_density_ode():
    h,ops=spin_hamiltonian([-100.,70.],[[0.,7.],[7.,0.]])
    h=h+130*sum(a[0] for a in ops)+40*sum(a[1] for a in ops)
    t1=[.4,1.2];t2=[.08,.15];p=.03;time=.003
    bath,_,_=local_spin_bath(ops,t1,t2,polarization=p)
    v=np.array([1.,1j,-.3,.4j]);v/=np.linalg.norm(v);initial=np.outer(v,v.conj())
    exact=(quantum_channel(lindblad_generator(h,bath),time)@initial.reshape(-1,order='F')).reshape((4,4),order='F')
    # Direct Hilbert-space action; no vectorization, generator construction,
    # channel exponential or local_spin_bath operators in the ODE reference.
    def derivative(rho):
        out=-1j*(h@rho-rho@h)
        for axes,a,b in zip(ops,t1,t2):
            plus=axes[0]+1j*axes[1];minus=plus.conj().T
            for op,rate in [(plus,(1+p)/(2*a)),(minus,(1-p)/(2*a)),(axes[2],2*(1/b-1/(2*a)))]:
                product=op.conj().T@op
                out+=rate*(op@rho@op.conj().T-(product@rho+rho@product)/2)
        return out
    rows=[]
    for n in [128,256,512]:
        rho=initial.copy();dt=time/n
        for _ in range(n):
            a=derivative(rho);b=derivative(rho+dt*a/2);c=derivative(rho+dt*b/2);d=derivative(rho+dt*c)
            rho=rho+dt*(a+2*b+2*c+d)/6
        rows.append(dict(steps=n,max_density_error=float(np.max(abs(rho-exact)))))
    if rows[-1]['max_density_error']>1e-10 or rows[1]['max_density_error']>rows[0]['max_density_error']/14:
        raise AssertionError('independent direct density RK4 reference failed')
    return dict(refinement=rows,exact_final_density=exact,minimum_eigenvalue=float(np.linalg.eigvalsh(exact).min()))


def compact(run):
    return dict(replay=run['provenance']['replay'],complete_run_sha256=digest(run),validation=run['validation'],
        amounts=run['fit']['amounts'],fit_residual=run['fit']['relative_residual'],basis_condition=run['fit']['basis_condition'],
        signal=run['signal'],basis=run['basis'],prediction=run['fit']['prediction'],rf_refinement_errors=run['rf_refinement_errors'],
        quantum_diagnostics=run['quantum_diagnostics'],provenance=run['provenance'],
        trajectories=[dict(role=r['role'],component=r['component'],spin_specification=r['spin_specification'],diagnostics=r['diagnostics'],
            timing=r['timing'],state_hash=r['trajectory']['state_hash'],cycle_hash=r['cycle_hash'],
            start_density=r['trajectory']['start_density'],echo_density=r['trajectory']['echo_density'],end_density=r['trajectory']['end_density'],
            dummy_start_longitudinal=r['trajectory']['dummy_start_longitudinal'],dummy_distance_to_periodic=r['trajectory']['dummy_distance_to_periodic']) for r in run['simulations']])


def evidence():
    root=Path(__file__).resolve().parents[1];record=create_scientific_record(read_portable(root/'docs/research/examples/quantum-mrs-plan.json'))
    payload=json.loads(record['payload_json']);runs={f'tr_{p["parameters"]["repetition_s"]}':p['run']['result'] for p in payload['candidates'] if p['feasible']}
    if record['summary']['selected_index']!=1 or payload['candidates'][0]['run']['view']['validation']['passed'] or payload['candidates'][-1]['feasible']:
        raise AssertionError('finite search did not preserve retained-signal/timing failures')
    for name,patch in dict(equilibrium_basis=dict(basis_mode='equilibrium'),wrong_t1=dict(basis_t1_scale=2.),
        wrong_j=dict(basis_j_hz=0.),strict_rf=dict(target_rf_error=1e-6),finite_zero=dict(preparation='finite_dummies',dummy_scans=0),
        finite_one=dict(preparation='finite_dummies',dummy_scans=1),finite_eight=dict(preparation='finite_dummies',dummy_scans=8)).items():
        runs[name]=run_mrs_quantum(**patch)
    if runs['wrong_t1']['fit']['relative_residual']>.02 or runs['wrong_t1']['validation']['passed']:
        raise AssertionError('low-residual T1 amount bias must remain failed')
    out=dict(schema='mrqlab-quantum-tr-mrs-evidence-1',sources=source_manifest(),runtime=runtime_manifest(),
        script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),independent_hard_bloch=independent_hard_bloch(),
        independent_density_ode=independent_density_ode(),cases={name:compact(run) for name,run in runs.items()},
        scientific_record_sha256=record['record_sha256'],scientific_payload_sha256=record['payload_sha256'],search_summary=record['summary'],scope=runs['tr_0.6']['scope'])
    return record,serializable(out)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--record-output',type=Path);parser.add_argument('--verify',type=Path);args=parser.parse_args()
    if args.output.exists() or (args.record_output and args.record_output.exists()): parser.error('output already exists')
    record,result=evidence()
    if args.verify and result!=read_portable(args.verify): raise ValueError('complete quantum MRS evidence differs')
    if args.record_output: write_portable(record,args.record_output)
    with args.output.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    for name,row in result['cases'].items(): print(name,row['validation'],row['amounts'],flush=True)
    print('record',record['record_sha256'],'Bloch',result['independent_hard_bloch']['refinement'],'density ODE',result['independent_density_ode']['refinement'])
    if args.verify: print('Independent complete quantum MRS evidence and scientific search replay match')
