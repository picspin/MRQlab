"""Recompute the measurement-derived fixed-prior radial TSE uncertainty grid.

Evidence includes full scientific-record/payload and every scenario run hash.
A portable complete child can also be exported for generic CLI/API replay.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from mrqlab_api.scientific_records import create_scientific_record,read_portable,write_portable
from mrqlab_experiment.study_records import source_manifest,runtime_manifest


def evidence(parent,plan):
    plan={**plan,'execution':{**plan['execution'],'parent_record':parent}}
    record=create_scientific_record(plan);derived=json.loads(record['payload_json'])['derivation']
    cases=[]
    for point in derived['candidates']:
        rows=[]
        for row in point['scenarios']:
            run=row.get('run')
            rows.append({**{k:v for k,v in row.items() if k!='run'},
                'validation':run['validation'] if run else None,
                'samples_sha256':run['provenance']['sample_hash'] if run else None,
                'basis_sha256':run['provenance']['basis_hash'] if run else None})
        cases.append({**{k:v for k,v in point.items() if k!='scenarios'},'scenarios':rows})
    if not derived['validation']['parent_result_revalidated'] or derived['selected_index'] is not None:
        raise AssertionError('parent numeric revalidation or strict fixed-prior failure changed')
    if not cases[0]['scenarios'][0]['passed'] or any(r['passed'] for p in cases for r in p['scenarios'][1:]):
        raise AssertionError('nominal/corner control outcomes changed')
    result=dict(schema='mrqlab-calibrated-radial-evidence-1',sources=source_manifest(),runtime=runtime_manifest(),
        script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),parent_record_sha256=parent['record_sha256'],
        record_sha256=record['record_sha256'],payload_sha256=record['payload_sha256'],
        parent_revalidation=derived['parent_result_revalidation'],parameter_bindings=derived['parameter_bindings'],
        validation=derived['validation'],targets=derived['targets'],provenance=derived['provenance'],
        candidates=cases,scope=derived['scope'])
    return record,result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--verify',type=Path)
    parser.add_argument('--record-output',type=Path);args=parser.parse_args()
    if args.output.exists() or (args.record_output and args.record_output.exists()): parser.error('output already exists')
    root=Path(__file__).resolve().parents[1]
    parent=read_portable(root/'docs/research/examples/calibrated-radial-parent-record.json')
    plan=read_portable(root/'docs/research/examples/calibrated-radial-plan.json')
    record,result=evidence(parent,plan)
    if args.verify and result!=json.loads(args.verify.read_text()): raise ValueError('complete calibrated-radial evidence differs')
    if args.record_output: write_portable(record,args.record_output)
    with args.output.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    for p in result['candidates']:
        print('candidate',p['index'],'eligible',p['eligible'],'worst_component_nrmse',p.get('worst_component_nrmse'))
    print('complete record',result['record_sha256'],'validation',result['validation'])
    if args.verify: print('Independent complete fixed-prior evidence replay matches every record and scenario hash')
