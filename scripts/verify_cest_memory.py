"""Recompute finite-history CEST and independent Bloch/Green-function references."""
import argparse
from pathlib import Path
from hashlib import sha256
import json
import numpy as np
from mrqlab_experiment.cest_memory import run_cest_memory,memory_generator
from mrqlab_experiment.cest_solomon import relay_pool_system
from mrqlab_physics.ops.generalized_mt import memory_weights,integrate_generalized_mt,semisolid_green
from mrqlab_physics.ops.cest_saturation import _matrix_exp
from mrqlab_physics.ops.dipolar_solomon import dipolar_pair_rates
from mrqlab_experiment.study_records import source_manifest,runtime_manifest
from mrqlab_api.research import serializable
from mrqlab_api.scientific_records import create_scientific_record,read_portable,write_portable


def digest(x): return sha256(json.dumps(serializable(x),sort_keys=True,allow_nan=False).encode()).hexdigest()


def compact(run):
    return dict(replay=run['provenance']['replay'],complete_run_sha256=digest(run),metrics=run['metrics'],validation=run['validation'],
        spectra=run['spectra'],bound_spectra=run['bound_spectra'],memory_diagnostics=run['memory_diagnostics'],
        waveform=run['provenance']['waveform'],estimated_work=run['provenance']['estimated_work'],planned_work=run['provenance']['planned_work'],
        estimated_peak_memory_bytes=run['provenance']['estimated_peak_memory_bytes'],
        histories={name:[{k:row[k] for k in ['offset_ppm','refinement_error','maximum_error_witness','coarse_history_hash','refined_history_hash','generator_hash']} for row in rows] for name,rows in run['trajectories'].items()})


def coupled_lorentzian_reference():
    system=relay_pool_system();rates=dipolar_pair_rates();g,rx,ry=memory_generator(system,200.,rates,bound_t2_s=.0003)
    initial=np.zeros(17);initial[2:15:3]=system.density;initial[15]=.08;initial[-1]=1.;omega=1500.+700j
    full=np.zeros((19,19));a=g+omega.real*rx+omega.imag*ry;full[:16,:16]=a[:16,:16];full[:16,-1]=a[:16,-1]
    delta=2*np.pi*200;full[16:18,16:18]=[[-1/.0003,delta],[-delta,-1/.0003]]
    full[16,15]=-omega.imag;full[17,15]=omega.real;full[15,16]=omega.imag;full[15,17]=-omega.real
    exact=_matrix_exp(full,.001)@np.r_[initial[:16],0.,0.,1.];result=[]
    for n in [128,256,512]:
        left,right,_=memory_weights(n,.001/n,t2_s=.0003,offset_hz=200.,lineshape='lorentzian')
        states,_=integrate_generalized_mt(g,rx,ry,initial,np.full(n,omega),.001/n,left,right,bound_index=15)
        result.append(dict(steps=n,max_state_error=float(np.max(abs(states[-1,:16]-exact[:16])))))
    if result[-1]['max_state_error']>1e-5 or any(result[i]['max_state_error']>=result[i-1]['max_state_error']/3.8 for i in [1,2]):
        raise AssertionError('independent augmented Bloch limit failed second-order convergence')
    return result


def hard_pulse_reference():
    n=512;dt=1e-8/n;left,right,_=memory_weights(n,dt,t2_s=1e-5)
    free=np.array([[-1.,1.],[0,0.]]);zero=np.zeros((2,2))
    history,_=integrate_generalized_mt(free,zero,zero,[1.,1.],np.full(n,np.pi/1e-8),dt,left,right,bound_index=0)
    if history[-1,0]>-.99999: raise AssertionError('finite-memory hard-pulse inversion limit failed')
    return dict(pulse_s=1e-8,t2_s=1e-5,final_z=float(history[-1,0]),hard_rotation_reference=-1.)


def evidence(plan):
    record=create_scientific_record(plan);payload=json.loads(record['payload_json'])
    runs={f'power_{i}':p['run']['result'] for i,p in enumerate(payload['candidates']) if p['feasible']}
    if record['summary']['selected_index'] is not None: raise AssertionError('failed efficacy/convergence candidates cannot create an optimum')
    extras=dict(coarse=run_cest_memory(steps_per_bin=4),
        fast_signed=run_cest_memory(offsets_ppm=[-3.5,0.,3.5],tau_c_s=1e-10),
        disconnected=run_cest_memory(offsets_ppm=[-3.5,0.,3.5],bridge_exchange_s1=0.,b1_uT=.5),
        phase_cycled=run_cest_memory(offsets_ppm=[-3.5,0.,3.5],phase_cycle_rad=[0.,np.pi/2],b1_uT=.5))
    if extras['coarse']['validation']['numerical_refinement_passed'] or extras['fast_signed']['metrics']['relayed_noe_contrast']>=0:
        raise AssertionError('coarse-grid and signed contrast failures must stay explicit')
    if abs(extras['disconnected']['metrics']['relayed_noe_contrast'])>1e-12: raise AssertionError('disconnected relay leaked into water')
    result=dict(schema='mrqlab-finite-memory-cest-evidence-1',sources=source_manifest(),runtime=runtime_manifest(),
        script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),coupled_lorentzian=coupled_lorentzian_reference(),
        hard_pulse=hard_pulse_reference(),long_lag_green=dict(value=float(semisolid_green(1.,1e-5)),asymptote=float(np.sqrt(2*np.pi/3)*1e-5)),
        cases={k:compact(v) for k,v in {**runs,**extras}.items()},scientific_record_sha256=record['record_sha256'],
        scientific_payload_sha256=record['payload_sha256'],search_summary=record['summary'],scope=runs['power_1']['scope'])
    return record,serializable(result)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--verify',type=Path);parser.add_argument('--record-output',type=Path);args=parser.parse_args()
    if args.output.exists() or (args.record_output and args.record_output.exists()): parser.error('output already exists')
    root=Path(__file__).resolve().parents[1];record,result=evidence(read_portable(root/'docs/research/examples/cest-memory-plan.json'))
    if args.verify and result!=read_portable(args.verify): raise ValueError('complete finite-memory CEST evidence differs')
    if args.record_output: write_portable(record,args.record_output)
    with args.output.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    for name,run in result['cases'].items(): print(name,run['metrics'],run['validation'],flush=True)
    print('complete record',record['record_sha256'],'independent Bloch reference',result['coupled_lorentzian'])
    if args.verify: print('Independent full finite-memory CEST evidence and scientific search replay match')
