"""Independent relaxation/CPMG/direct-DFT evidence for controlled image/signal pairs."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import numpy as np
from fastapi import HTTPException
from mrqlab_experiment.study_records import source_manifest,runtime_manifest
from mrqlab_experiment.linked_readout import verify_linked_readout
from mrqlab_api.scientific_records import create_scientific_record,read_portable,write_portable


def independent_cpmg_dft(run):
    r=run['result'];p=run['replay_request']['parameters'];labels=np.asarray(p['labels']);shape=labels.shape;dims=len(shape);n=labels.size
    weights=[];rates=[]
    for index,t in enumerate(p['experiment']['tissue']):
        e=t['contrast_exposure'];r1=1/t['t1']+e['r1_l_mmol_s']*e['concentration_mmol_l'];r2=1/p['t2_s'][index]+e['r2_l_mmol_s']*e['concentration_mmol_l']
        z=0.;at=0.;pd=t['proton_density']
        for time in (np.arange(p['echoes'])+.5)*p['echo_spacing_s']:
            z=pd+(z-pd)*np.exp(-(time-at)*r1);z=-z;at=time
        before=pd+(z-pd)*np.exp(-(p['tr_s']-at)*r1)
        weights.append(before*np.exp(-np.arange(1,p['echoes']+1)*p['echo_spacing_s']*r2));rates.append(dict(r1_s_inv=r1,r2_s_inv=r2))
    weights=np.asarray(weights);nz,ny,nx=(1,*shape) if dims==2 else shape
    ys=list(range(ny))
    if p['order']=='centric': ys.sort(key=lambda y:(abs(y-ny//2),y))
    zs=sorted(range(nz),key=lambda z:(abs(z-nz//2),z));indices=[];echos=[];times=[];train=0
    for z in zs:
        for start in range(0,ny,p['echoes']):
            for echo,y in enumerate(ys[start:start+p['echoes']]):
                for x in range(nx):
                    indices.append([z,y,x][-dims:]);echos.append(echo);times.append(train*p['tr_s']+(echo+1)*p['echo_spacing_s']+x*.002/nx)
            train+=1
    indices=np.asarray(indices);coords=(indices-np.array(shape)//2)/np.array(shape)
    positions=np.indices(shape).reshape(dims,-1).T-np.array(shape)//2
    fourier=np.exp(-2j*np.pi*(coords@positions.T));masks=np.array([(labels==j).ravel() for j in range(2)])
    predicted=np.sum((fourier@masks.T)*weights[:,echos].T,axis=1)
    pair=r['linked_readout'];s=pair['signal_vector'];measured=np.array(s['values']['real'])+1j*np.array(s['values']['imag'])
    direct_inverse=(fourier.conj().T@measured/n).reshape(shape)
    encoded=np.array(pair['image']['values']['real'])+1j*np.array(pair['image']['values']['imag'])
    checks=dict(complete_samples=int(n),effective_rates=rates,max_echo_error=float(np.max(abs(np.array(r['tissue_echo_weights'])-weights))),
        max_sample_absolute_error=float(np.max(abs(measured-predicted))),max_sample_error_per_voxel=float(np.max(abs(measured-predicted))/n),
        max_image_direct_inverse_error=float(np.max(abs(direct_inverse.ravel()-encoded))),
        max_schedule_time_error_s=float(np.max(abs(np.array(s['sample_times_s'])-times))),
        normalized_coordinates_equal=bool(np.array_equal(coords,np.asarray(s['normalized_coordinates']))),pair_check=verify_linked_readout(pair))
    # The inherited EPG periodic-state stopping tolerance is 1e-9 per state.
    if checks['max_echo_error']>2e-9 or checks['max_sample_error_per_voxel']>2e-9 or checks['max_image_direct_inverse_error']>1e-11:
        raise AssertionError('independent relaxation/CPMG/Fourier reference failed')
    if checks['max_schedule_time_error_s']>1e-12 or not checks['normalized_coordinates_equal']: raise AssertionError('acquisition-order axes differ from independently constructed schedule')
    return checks


def evidence():
    root=Path(__file__).resolve().parents[1];plan=read_portable(root/'docs/research/examples/contrast-tse-plan.json');parent=create_scientific_record(plan)
    cases={};child=None
    for c in [0.,.05,.2,.5,1.]:
        updates=[dict(field='rf.refocusing_start_deg',value=180.),dict(field='rf.refocusing_end_deg',value=180.),dict(field='tissue.concentration_mmol_l',tissue_id='gray_matter',value=c)]
        request=dict(context=plan['context'],execution=dict(type='edited_tse',parent_record_sha256=parent['record_sha256'],parent_record=parent,updates=updates))
        record=create_scientific_record(request);payload=json.loads(record['payload_json']);run=payload['run']
        cases[str(c)]=dict(record_sha256=record['record_sha256'],result_sha256=run['result_hash'],pair_sha256=run['result']['linked_readout']['pair_sha256'],
            image_quality=run['result']['quality'],psf_quality=run['result']['psf_prediction_quality'],independent=independent_cpmg_dft(run),
            contrast_bindings=[p['contrast_relaxation_bindings'] for p in run['result']['provenance']['physical']])
        if c==.5: child=record
    small3d=deepcopy(plan);y,x=np.indices((8,8));labels=((x-4)**2+(y-4)**2<6).astype(int)
    small3d['execution']['parameters'].update(labels=np.stack([labels,1-labels]).tolist(),refocusing_angle=180.,refocusing_end_angle=180.)
    volume=create_scientific_record(small3d);cases['3d']=dict(record_sha256=volume['record_sha256'],independent=independent_cpmg_dft(json.loads(volume['payload_json'])))
    failures={}
    for name in ['field_mismatch','above_valid_concentration','legacy_unbound_concentration']:
        altered=deepcopy(plan);graph=altered['execution']['parameters']['experiment']
        if name=='field_mismatch': graph['tissue'][1]['contrast_exposure']['reference_b0_t']=1.5
        elif name=='above_valid_concentration': graph['tissue'][1]['contrast_exposure']['concentration_mmol_l']=2.
        else: graph['physiology']=dict(contrast_agent_concentration=.1)
        try: create_scientific_record(altered)
        except (ValueError,HTTPException) as exc: failures[name]=str(exc)
        else: raise AssertionError('unsupported exposure was silently accepted: '+name)
    assert child is not None
    # Raw historical graph hashes distinguish 62500.0 from 62500 in metadata;
    # capture each request exactly rather than relabel their record identities.
    browser_plan=json.loads(subprocess.run(['node','-e','let s="";process.stdin.on("data",c=>s+=c);process.stdin.on("end",()=>process.stdout.write(JSON.stringify(JSON.parse(s))))'],input=json.dumps(plan),text=True,capture_output=True,check=True).stdout)
    browser_parent=create_scientific_record(browser_plan)
    child_request=json.loads(child['request_json']);browser_child=create_scientific_record(dict(context=browser_plan['context'],execution=dict(type='edited_tse',
        parent_record_sha256=browser_parent['record_sha256'],parent_record=browser_parent,updates=child_request['execution']['updates'])))
    native_run=json.loads(browser_child['payload_json'])['run'];python_run=json.loads(child['payload_json'])['run']
    if native_run['result']['linked_readout']!=python_run['result']['linked_readout']: raise AssertionError('paired physical outputs changed through browser numeric transport')
    return parent,child,dict(schema='mrqlab-contrast-image-signal-evidence-1',sources=source_manifest(),runtime=runtime_manifest(),
        script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),parent_record_sha256=parent['record_sha256'],child_record_sha256=child['record_sha256'],
        cases=cases,rejected_cases=failures,browser_numeric_boundary=dict(parent_record_sha256=browser_parent['record_sha256'],child_record_sha256=browser_child['record_sha256'],
            complete_pair_identical=True,pair_sha256=native_run['result']['linked_readout']['pair_sha256'],python_run_result_hash=python_run['result_hash'],browser_run_result_hash=native_run['result_hash'],
            convention='original raw JSON graph/plan/result hashes retain numeric-token distinctions in free metadata; lossless scientific requests replay each exact record; image/signal pair uses typed binary64 canonicalization'),
        scope='synthetic static dilute relaxivity and ideal echo-held Cartesian TSE; complete image/signal pair, conditional typed edits and replay; no clinical/scanner or concentration-estimation claim')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--record-output',type=Path);parser.add_argument('--parent-output',type=Path);parser.add_argument('--verify',type=Path);args=parser.parse_args()
    if any(p and p.exists() for p in [args.output,args.record_output,args.parent_output]): parser.error('output already exists')
    parent,child,result=evidence()
    if args.verify and result!=read_portable(args.verify): raise ValueError('complete contrast/image/signal evidence differs')
    if args.parent_output: write_portable(parent,args.parent_output)
    if args.record_output: write_portable(child,args.record_output)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(parent=parent['record_sha256'],child=child['record_sha256'],cases=list(result['cases'])),indent=2))
