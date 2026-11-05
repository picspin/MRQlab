"""Conditional velocity/pressure/finite-RF DIR evidence; preserve failed designs."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
from mrqlab_experiment.flow_study import FlowStudy,calibrate_pressure,run_flow_study
from mrqlab_experiment.study_records import source_manifest,runtime_manifest
from mrqlab_api.scientific_records import create_scientific_record,read_portable,write_portable


def independent_pressure_reference(study):
    """Finite-volume unsteady momentum solve; no Bessel/velocity generator."""
    spec=FlowStudy.model_validate(study);p=spec.priors;errors=[];fits=[]
    truth=np.array([100.,200*np.cos(.25),-200*np.sin(.25)])
    for n in [64,128,256]:
        dr=p.radius_m/n;r=(np.arange(n)+.5)*dr;faces=np.arange(n+1)*dr
        nu=p.viscosity_pa_s/p.density_kg_m3;omega=2*np.pi*p.frequency_hz
        lower=nu*faces[:-1]/(r*dr**2);upper=nu*faces[1:]/(r*dr**2);upper[-1]*=2
        laplacian=np.diag(-lower-upper)+np.diag(lower[1:],-1)+np.diag(upper[:-1],1)
        steady=np.linalg.solve(-laplacian,np.full(n,100/p.density_kg_m3))
        harmonic=np.linalg.solve(1j*omega*np.eye(n)-laplacian,np.full(n,200*np.exp(.25j)/p.density_kg_m3))
        d=spec.dataset.model_dump(mode='json');d.pop('raw_csv_base64');d.pop('raw_file_sha256')
        for row in d['measurements']:
            i=n//8 if row['measurement_id'].endswith('-0') else 5*n//8
            row['radius_m']=float(r[i]);row['velocity_m_s']=float(steady[i]+np.real(harmonic[i]*np.exp(1j*omega*row['time_s'])))
        derived=spec.model_dump(mode='json');derived['dataset']=d;model=FlowStudy.model_validate(derived)
        fit=calibrate_pressure(model.dataset,model.priors,model.targets)
        fits.append(fit['coefficients_pa_m']);errors.append(float(np.max(abs(np.asarray(fit['coefficients_pa_m'])-truth))))
        if not fit['passed']: raise AssertionError('independent momentum velocity data did not pass conditional holdout')
    if errors[-1]>.005 or not all(b<a/3 for a,b in zip(errors,errors[1:])): raise AssertionError('independent pressure reference did not refine')
    return dict(cells=[64,128,256],coefficients_pa_m=fits,max_coefficient_absolute_errors_pa_m=errors,truth_pa_m=truth.tolist())


def compact(result):
    return dict(validation=result['validation'],calibration=result['calibration'],selected_index=result['selected_index'],provenance=result['provenance'],
        candidates=[dict(index=p['index'],design=p['design'],eligible=p['eligible'],executed=p['executed'],reasons=p['reasons'],
            scenarios=[{k:s[k] for k in ['name','completed','passed','reasons','max_observation_refinement_error','numerical_refinement_passed'] if k in s} |
                (dict(refined_validation=s['refined']['validation']) if s['completed'] else {}) for s in p['scenarios']]) for p in result['candidates']])


def evidence():
    root=Path(__file__).resolve().parents[1];plan=read_portable(root/'docs/research/examples/measured-flow-plan.json')
    record=create_scientific_record(plan);result=json.loads(record['payload_json'])['flow_study'];study=plan['execution']['study']
    if not result['calibration']['passed'] or result['selected_index'] is not None: raise AssertionError('calibration/design statuses changed')
    if not all(s['completed'] and s['numerical_refinement_passed'] for p in result['candidates'] for s in p['scenarios']): raise AssertionError('default complete numerical refinement failed')
    reduced=json.loads(json.dumps(study));reduced['numerics']=dict(radial_rings=4,axial_spins=201,rf_steps=32);reduced['candidates']=[dict(inversion_time_s=.9)]
    cases={'default':result,'underresolved':run_flow_study(reduced)}
    if all(s['numerical_refinement_passed'] for s in cases['underresolved']['candidates'][0]['scenarios']): raise AssertionError('underresolved failure hidden')
    for name in ['holdout_failed','unidentifiable','budget_failed']:
        altered=json.loads(json.dumps(study))
        if name=='budget_failed': altered['budget']['max_total_work']=10000
        else:
            dataset=altered['dataset'];dataset.pop('raw_csv_base64');dataset.pop('raw_file_sha256')
            for row in dataset['measurements']:
                if name=='holdout_failed' and row['split']=='holdout': row['velocity_m_s']+=.05
                elif name=='unidentifiable': row.update(radius_m=altered['priors']['radius_m'],velocity_m_s=0.)
        cases[name]=run_flow_study(altered)
        if any(p['executed'] for p in cases[name]['candidates']): raise AssertionError('failed measurement/budget applied MR prior')
    return record,dict(schema='mrqlab-measured-flow-evidence-1',sources=source_manifest(),runtime=runtime_manifest(),
        script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),scientific_record_sha256=record['record_sha256'],scientific_payload_sha256=record['payload_sha256'],
        independent_momentum_pressure=independent_pressure_reference(study),cases={k:compact(v) for k,v in cases.items()},scope=result['scope'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--record-output',type=Path);parser.add_argument('--verify',type=Path);args=parser.parse_args()
    if args.output.exists() or (args.record_output and args.record_output.exists()): parser.error('output already exists')
    record,result=evidence()
    if args.verify and result!=read_portable(args.verify): raise ValueError('complete measured flow evidence differs')
    if args.record_output: write_portable(record,args.record_output)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(record_sha256=record['record_sha256'],cases={k:v['validation'] for k,v in result['cases'].items()}),indent=2))
