"""Recompute PRESS teaching evidence, including every complex-map hash.

The API exports complete volumes; this repository fixture saves their hashes,
FID/basis/fit arrays and explicit inputs without duplicating all 3D maps.
--verify independently recomputes all cases before comparing portable JSON.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
from mrqlab_experiment.mrs_press import run_press_basis,simulate_press_volume
from mrqlab_experiment.study_records import source_manifest,runtime_manifest
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T


def portable(value):
    if isinstance(value,np.ndarray): return portable(value.tolist())
    if isinstance(value,np.generic): return portable(value.item())
    if isinstance(value,complex): return dict(real=value.real,imag=value.imag)
    if isinstance(value,dict): return {k:portable(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [portable(v) for v in value]
    return value


def digest(value):
    return sha256(json.dumps(portable(value),sort_keys=True,allow_nan=False).encode()).hexdigest()


def compact_run(result):
    compact={k:v for k,v in result.items() if k not in {'localization','water_localization'}}
    compact['complete_result_sha256']=digest(result)
    compact['localization']=[{k:v for k,v in r.items() if k!='spatial_response'} |
        {'complex_volume_sha256':digest(r['spatial_response'])} for r in result['localization']+[result['water_localization']]]
    return compact


def evidence():
    good=run_press_basis();center=run_press_basis(basis_mode='center');j=run_press_basis(basis_j_hz=0.)
    a=simulate_press_volume([-30.,10.],[[0.,7.],[7.,0.]],grid_size=5,rf_steps=32,points=32)
    b=simulate_press_volume([-30.,10.],[[0.,7.],[7.,0.]],grid_size=5,rf_steps=32,points=32,selection='phase_cycle')
    csd=simulate_press_volume([-213.3],[[0.]],grid_size=33)
    prediction=213.3/(GAMMA_BAR_HZ_T*csd['provenance']['gradient_t_m'][1])
    references=dict(phase_cycle_relative_fid_error=float(np.linalg.norm(a['fid']-b['fid'])/np.linalg.norm(a['fid'])),
        projection_complete_sha256=digest(a),phase_cycle_complete_sha256=digest(b),
        shift_centroid_m=csd['centroid_m'],bandwidth_predicted_yz_m=prediction,shift_complete_sha256=digest(csd))
    if not good['validation']['passed'] or center['validation']['passed'] or j['validation']['passed']:
        raise AssertionError('volume/control validation changed')
    if references['phase_cycle_relative_fid_error']>1e-12 or max(abs(np.array(csd['centroid_m'][1:])-prediction))>1e-7:
        raise AssertionError('independent phase-cycle or bandwidth reference failed')
    return portable(dict(schema='mrqlab-press-volume-evidence-1',scope=good['scope'],
        sources=source_manifest(),runtime=runtime_manifest(),script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        independent_references=references,volume_fit=compact_run(good),center_mismatch=compact_run(center),coupling_mismatch=compact_run(j)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--verify',type=Path);args=parser.parse_args()
    if args.output.exists(): parser.error('output already exists')
    result=evidence()
    if args.verify:
        if result!=json.loads(args.verify.read_text()): raise ValueError('complete PRESS evidence replay differs')
        print('Independent PRESS evidence replay matches: complex volume hashes, FIDs, fits, controls, sources and runtime')
    with args.output.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    for key in ['volume_fit','center_mismatch','coupling_mismatch']:
        print(key,result[key]['validation'])
