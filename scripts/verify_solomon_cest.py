"""Reproduce signed Solomon relay CEST evidence; authored molecular priors only.

--verify performs complete independent recomputation against saved evidence.
Output files must not already exist. No clinical/scanner dataset is used.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
from mrqlab_physics.ops.dipolar_solomon import dipolar_pair_rates
from mrqlab_physics.ops.cest_saturation import _matrix_exp
from mrqlab_experiment.cest_solomon import run_cest_solomon
from mrqlab_experiment.study_records import source_manifest,runtime_manifest


def population_reference():
    rates=dipolar_pair_rates(shifts_ppm=(0.,0.)); K=np.zeros((4,4))
    for i,j,key in [(1,2,'w0_s1'),(0,3,'w2_s1'),(0,2,'w1_i_s1'),(1,3,'w1_i_s1'),(0,1,'w1_s_s1'),(2,3,'w1_s_s1')]:
        rate=rates[key];K[j,i]+=rate;K[i,j]+=rate;K[i,i]-=rate;K[j,j]-=rate
    zi=np.array([1.,1.,-1.,-1.]);zs=np.array([1.,-1.,1.,-1.]);p=np.ones(4)/4+.04*zi+.07*zs;t=.73
    independent=_matrix_exp(K,t)@p
    rho=rates['rho_i_s1'];sigma=rates['sigma_s1']
    total=(zi@p+zs@p)*np.exp(-(rho+sigma)*t);difference=(zi@p-zs@p)*np.exp(-(rho-sigma)*t)
    actual=np.array([zi@independent,zs@independent]);analytic=np.array([(total+difference)/2,(total-difference)/2])
    return dict(basis=['up/up','up/down','down/up','down/down'],duration_s=t,transition_generator=K.tolist(),
        population_initial=p.tolist(),population_final=independent.tolist(),solomon_analytic=analytic.tolist(),
        independent_longitudinal=actual.tolist(),max_absolute_error=float(abs(actual-analytic).max()))


def evidence():
    sensitivity=[run_cest_solomon(tau_c_s=tau) for tau in [1e-10,1e-9,1e-8]]
    powers=[run_cest_solomon(b1_uT=power) for power in [.1,1.,2.]]
    cw=run_cest_solomon(saturation_s=.4,offsets_ppm=[-3.5,3.5])
    pulsed=run_cest_solomon(saturation_s=.4,offsets_ppm=[-3.5,3.5],mode='pulsed',n_pulses=4,pulse_s=.1,gap_s=0.)
    try:
        run_cest_solomon(offsets_ppm=[-3.5,0.,3.5])
    except ValueError as exc: zero=dict(executed=False,reason=str(exc))
    else: raise AssertionError('SL zero-offset case must fail closed')
    return dict(schema='mrqlab-solomon-relay-evidence-1',scope='teaching/research; synthetic one-to-one proton pair, no scanner/clinical or molecular-cohort validation',
        sources=source_manifest(),runtime=runtime_manifest(),script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        independent_population_reference=population_reference(),molecular_prior_sensitivity=sensitivity,
        pulse_power_candidates=powers,selected_power_uT=powers[int(np.argmin([r['objective_loss'] for r in powers]))]['design']['b1_uT'],
        bridge_exchange_disabled=run_cest_solomon(bridge_exchange_s1=0.),distance_doubled=run_cest_solomon(distance_m=5e-10),
        cw=cw,pulsed_zero_gap=pulsed,pulsed_recovery_gap=run_cest_solomon(saturation_s=.55,offsets_ppm=[-3.5,3.5],mode='pulsed',n_pulses=4,pulse_s=.1,gap_s=.05),
        sl_zero_offset=zero,explicit_gaussian_zero=run_cest_solomon(offsets_ppm=[-3.5,0.,3.5],lineshape='gaussian'))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--verify',type=Path);args=parser.parse_args()
    if args.output.exists(): parser.error('output already exists')
    # Compare the portable JSON representation, including tuple-based pool arrays.
    result=json.loads(json.dumps(evidence(),allow_nan=False))
    if args.verify:
        if result!=json.loads(args.verify.read_text()): raise ValueError('complete scientific evidence replay differs')
        print('Complete independent evidence replay matches: spectra, rates, controls, candidates, sources and runtime')
    with args.output.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print('Independent population max error:',result['independent_population_reference']['max_absolute_error'])
    for run in result['molecular_prior_sensitivity']:
        print('tau',run['design']['tau_c_s'],'sigma',run['provenance']['dipolar_rates']['sigma_s1'],'relay',run['metrics']['relayed_noe_contrast'],'passed',run['validation']['passed'])
    print('Pulse candidates:',[(r['design']['b1_uT'],r['metrics']['relayed_noe_contrast'],r['validation']['passed']) for r in result['pulse_power_candidates']])
