"""Recompute echo-resolved radial TSE evidence and every complete-result hash.

Saved evidence retains all replay inputs and hashes of the complete complex data,
not just summary metrics. Full volumes/samples are available through the API.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
from mrqlab_experiment.radial_tse import run_radial_tse
from mrqlab_experiment.study_records import source_manifest,runtime_manifest
from mrqlab_recon.echo_subspace import EchoSubspaceOperator


def portable(value):
    if isinstance(value,np.ndarray): return portable(value.tolist())
    if isinstance(value,np.generic): return portable(value.item())
    if isinstance(value,complex): return dict(real=value.real,imag=value.imag)
    if isinstance(value,dict): return {k:portable(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [portable(v) for v in value]
    return value


def digest(value):
    return sha256(json.dumps(portable(value),sort_keys=True,allow_nan=False).encode()).hexdigest()


def independent_reference():
    """Full explicit 3D voxel sum, without FFT, radial acquisition or op basis."""
    rng=np.random.default_rng(83);shape=(3,4,4);xy=rng.uniform(-.5,.5,(31,2))
    weights=rng.normal(size=(2,31))+1j*rng.normal(size=(2,31))
    images=2.7*(rng.normal(size=(2,*shape))+1j*rng.normal(size=(2,*shape)))
    samples=np.zeros((shape[0],len(xy)),complex)
    for iz in range(shape[0]):
        for m,(kx,ky) in enumerate(xy):
            for k in range(2):
                for z,y,x in np.ndindex(shape):
                    phase=kx*(x-2)+ky*(y-2)+(iz-1)*(z-1)/3
                    samples[iz,m]+=weights[k,m]*images[k,z,y,x]*np.exp(-2j*np.pi*phase)
    exact=EchoSubspaceOperator(xy,shape,weights);fast=EchoSubspaceOperator(xy,shape,weights,backend='finufft')
    error=float(np.linalg.norm(exact.forward(images)-samples)/np.linalg.norm(samples))
    native_error=float(np.linalg.norm(fast.forward(images)-samples)/np.linalg.norm(samples))
    if max(error,native_error)>1e-11: raise AssertionError('independent complex voxel reference failed')
    return dict(exact_relative_error=error,finufft_relative_error=native_error,
        independent_samples_sha256=digest(samples),coordinates=xy,weights=weights,images_sha256=digest(images))


def compact(result):
    solver=result['solvers'][0];history=solver['residual_history']
    return dict(inputs=result['provenance']['replay'],validation=result['validation'],quality=result['quality'],
        complete_result_sha256=digest(result),sample_sha256=result['provenance']['sample_hash'],
        image_sha256=digest(result['image']),component_sha256=digest(result['reconstructed_components']),
        estimated_work=result['provenance']['estimated_work'],estimated_peak_memory_bytes=result['provenance']['estimated_peak_memory_bytes'],
        tissue_echo_weights=result['tissue_echo_weights'],temporal_basis=result['temporal_basis'],
        basis_singular_values=result['provenance']['basis_singular_values'],
        solver={k:v for k,v in solver.items() if k!='residual_history'},
        residual_history_sha256=digest(history),residual_history_endpoints=[history[0],history[-1]],
        static_control_quality=result['static_control']['quality'],static_solver_stop=result['static_control']['solver']['stop_reason'])


def evidence():
    y,x=np.indices((16,16));p=(((x-8)**2+(y-8)**2<20)|((x==3)&(y>3))).astype(int)
    cases={}
    for name,patch in [('matched',{}),('lower_rf',dict(refocusing_angle=140.,refocusing_end_angle=110.)),
        ('lowest_rf_component_failure',dict(refocusing_angle=100.,refocusing_end_angle=80.)),
        ('work_stop',dict(max_work=4000000000)),('t2_basis_mismatch',dict(basis_t2_s=[.03,.12])),
        ('finufft',dict(backend='finufft',max_work=50000000000))]:
        cases[name]=compact(run_radial_tse(p,**patch))
    cases['stack_of_stars_rf_failure']=compact(run_radial_tse(np.stack([p,1-p]),max_work=50000000000))
    if not cases['matched']['validation']['passed'] or not cases['lower_rf']['validation']['passed'] or not cases['finufft']['validation']['passed']:
        raise AssertionError('matched recovery no longer passes')
    for name in ['lowest_rf_component_failure','work_stop','t2_basis_mismatch','stack_of_stars_rf_failure']:
        if cases[name]['validation']['passed']: raise AssertionError('known failure disappeared: '+name)
    eligible=[name for name in ['matched','lower_rf','lowest_rf_component_failure'] if cases[name]['validation']['passed']]
    selected=min(eligible,key=lambda name:cases[name]['validation']['rf_energy_relative'])
    return portable(dict(schema='mrqlab-echo-radial-tse-evidence-1',scope='teaching/research; fixed known EPG priors; no measured clinical/scanner validation',
        sources=source_manifest(),runtime=runtime_manifest(),script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        independent_reference=independent_reference(),runs=cases,selected_pulse_case=selected))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--verify',type=Path);args=parser.parse_args()
    if args.output.exists(): parser.error('output already exists')
    result=evidence()
    if args.verify and result!=json.loads(args.verify.read_text()): raise ValueError('complete echo-radial TSE evidence replay differs')
    with args.output.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print('Independent voxel reference:',result['independent_reference']['exact_relative_error'],result['independent_reference']['finufft_relative_error'])
    for name,r in result['runs'].items(): print(name,r['validation'])
    print('Selected passing pulse:',result['selected_pulse_case'])
    if args.verify: print('Independent full scientific evidence replay matches, including complex result hashes')
