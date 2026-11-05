"""Recompute every measured-prior navigator scenario and an independent Prony check."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
from mrqlab_api.scientific_records import create_scientific_record,read_portable,write_portable
from mrqlab_experiment.study_records import source_manifest,runtime_manifest
from mrqlab_experiment.navigator_radial import estimate_tse_navigator


def evidence(parent,plan):
    record=create_scientific_record({**plan,'execution':{**plan['execution'],'parent_record':parent}})
    derived=json.loads(record['payload_json'])['derivation'];cases=[]
    for point in derived['candidates']:
        rows=[]
        for row in point['scenarios']:
            run=row.get('run')
            if run is None: raise AssertionError('a planned navigator scenario did not execute')
            fit=run['navigator_fit']
            item={k:v for k,v in row.items() if k!='run'}
            item.update(validation=run['validation'],fixed_prior_validation=run['fixed_prior_control']['validation'],
                samples_sha256=run['provenance']['sample_hash'],basis_sha256=run['provenance']['basis_hash'],
                navigator={k:fit[k] for k in ['passed','reasons','t2_s','t2_std_s','max_relative_t2_std','relative_fit_residual',
                    'relative_holdout_residual','relative_repeat_residual','fit_echoes','withheld_echoes',
                    'projected_jacobian_singular_values','evaluations','estimated_work','navigator_hash']})
            if point['design']['refocusing_angle']==180. and point['design']['refocusing_end_angle']==180.:
                # Independent six-echo complex annihilating-filter reference.
                y=np.array([complex(v['real'],v['imag']) for v in fit['observed_center_means']])
                matrix=np.column_stack([y[1:-1],-y[:-2]])
                recurrence=np.linalg.lstsq(matrix,y[2:],rcond=None)[0]
                roots=np.roots([1.,-recurrence[0],recurrence[1]])
                if max(abs(roots.imag))>1e-7 or not np.all((roots.real>0)&(roots.real<1)):
                    raise AssertionError('independent complex Prony poles are invalid')
                t2=np.sort(-point['design']['echo_spacing_s']/np.log(roots.real))
                error=float(np.max(abs(t2/fit['t2_s']-1)))
                if error>1e-6: raise AssertionError('independent Prony global T2 disagrees')
                item.update(prony_t2_s=t2.tolist(),prony_relative_error=error)
            rows.append(item)
        cases.append({**{k:v for k,v in point.items() if k!='scenarios'},'scenarios':rows})
    if not derived['validation']['parent_result_revalidated'] or len(cases)!=2 or any(len(p['scenarios'])!=5 for p in cases):
        raise AssertionError('complete parent-bound two-candidate grid required')
    # Model-mismatch control: corrupt only the withheld late echoes. Neither
    # sample T2 nor a reference image is passed to the estimator.
    run=derived['candidates'][0]['scenarios'][0]['run']
    samples=np.array([[complex(v['real'],v['imag']) for v in plane] for plane in run['samples']])
    ids=np.array(run['echo_for_sample']);samples[:,ids>=4]*=1.001
    negative=estimate_tse_navigator(run['coordinates'],samples,ids,echoes=6,echo_spacing_s=.008,tr_s=.4,
        t2_bounds_s=[b['stress_interval_s'] for b in derived['parameter_bindings']])
    if negative['passed'] or negative['relative_holdout_residual']<1e-4:
        raise AssertionError('withheld-echo mismatch must fail')
    result=dict(schema='mrqlab-navigator-radial-evidence-1',sources=source_manifest(),runtime=runtime_manifest(),
        script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),record_sha256=record['record_sha256'],
        payload_sha256=record['payload_sha256'],parent_record_sha256=parent['record_sha256'],
        parent_revalidation=derived['parent_result_revalidation'],parameter_bindings=derived['parameter_bindings'],
        validation=derived['validation'],targets=derived['targets'],provenance=derived['provenance'],candidates=cases,
        withheld_mismatch_control={k:negative[k] for k in ['passed','reasons','t2_s','relative_fit_residual','relative_holdout_residual']},
        scope=derived['scope'])
    return record,result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--verify',type=Path);parser.add_argument('--record-output',type=Path);args=parser.parse_args()
    if args.output.exists() or (args.record_output and args.record_output.exists()): parser.error('output already exists')
    root=Path(__file__).resolve().parents[1]
    record,result=evidence(read_portable(root/'docs/research/examples/calibrated-radial-parent-record.json'),
        read_portable(root/'docs/research/examples/navigator-radial-plan.json'))
    if args.verify and result!=read_portable(args.verify): raise ValueError('complete navigator evidence differs')
    if args.record_output: write_portable(record,args.record_output)
    with args.output.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    for point in result['candidates']:
        print('candidate',point['index'],'eligible',point['eligible'],'worst component',point.get('worst_component_nrmse'))
    print('record',result['record_sha256'],'validation',result['validation'])
    if args.verify: print('Independent navigator grid, Prony reference and complete record replay match')
