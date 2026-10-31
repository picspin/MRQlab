"""Independent full finite-ADC radial/coil/B0 reference evidence and replay."""
import argparse
from hashlib import sha256
from pathlib import Path
import json
import numpy as np
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from mrqlab_experiment.radial_tse import run_radial_tse
from mrqlab_experiment.study_records import source_manifest,runtime_manifest
from mrqlab_api.research import serializable
from mrqlab_api.scientific_records import create_scientific_record,write_portable,read_portable


def independent_bloch_adc(run):
    """Actual hard RF rotations/free Bloch/physical gradient intervals per train."""
    shape=np.shape(run['reference']);n=shape[-1];v=int(np.prod(shape));read=run['readout'];p=run['design']
    axes=[(np.arange(side)-side//2)*p['fov_m']/side for side in shape]
    grids=np.meshgrid(*axes,indexing='ij');xyz=np.array([grids[-1].ravel(),grids[-2].ravel(),grids[0].ravel() if len(shape)==3 else np.zeros(v)])
    field=np.asarray(read['field_hz']).ravel();sens=np.asarray(read['coil_sensitivities']).reshape(p['coil_count'],v);result=np.zeros_like(run['samples'])
    for tissue_index,tissue in enumerate(run['experiment']['tissue']):
        t1=tissue['t1'];t2=p['t2_s'][tissue_index];pd=tissue['proton_density'];z=0.;at=0.
        for rf in np.arange(p['echoes'])*p['echo_spacing_s']+p['echo_spacing_s']/2:
            z=pd+(z-pd)*np.exp(-(rf-at)/t1);z=-z;at=rf
        z0=pd+(z-pd)*np.exp(-(p['tr_s']-at)/t1)
        mask=np.asarray(run['reference_components'][tissue_index]).ravel()
        for train in run['timeline']:
            m=np.full(v,-1j*z0);mz=np.full(v,0.);time=0.
            def free(end,gradient=(0.,0.,0.)):
                nonlocal m,mz,time
                dt=end-time;assert dt>=-1e-14
                m=m*np.exp(-dt/t2+2j*np.pi*(field+GAMMA_BAR_HZ_T*(np.asarray(gradient)@xyz))*dt)
                mz=pd+(mz-pd)*np.exp(-dt/t1);time=end
            for rf,spoke in zip(train['refocusing_s'],train['spokes']):
                center=spoke['echo']*p['echo_spacing_s'];start=center-p['adc_duration_s']/2;end=center+p['adc_duration_s']/2
                if abs(spoke['adc_start_s']-train['excitation_s']-start)>1e-14: raise AssertionError('ADC timeline mismatch')
                free((spoke['echo']-.5)*p['echo_spacing_s']);m=-m.conj();mz=-mz
                free(start-p['prephaser_s']);free(start,spoke['prephaser_gradient_t_m'])
                for index in spoke['sample_indices']:
                    free(start+(index%p['points']+.5)*p['adc_duration_s']/p['points'],spoke['readout_gradient_t_m'])
                    result[:,index]+=np.sum(sens*mask*(1j*m),axis=1)
                free(end,spoke['readout_gradient_t_m']);free(end+p['prephaser_s'],spoke['rewinder_gradient_t_m'])
    return result


def digest(value): return sha256(json.dumps(serializable(value),sort_keys=True,allow_nan=False).encode()).hexdigest()


def restore(value):
    if isinstance(value,dict):
        if set(value)=={'real','imag'}: return complex(value['real'],value['imag'])
        return {k:restore(v) for k,v in value.items()}
    if isinstance(value,list): return [restore(v) for v in value]
    return value


def solver_summary(diag):
    history=diag['residual_history']
    return {**{k:v for k,v in diag.items() if k!='residual_history'},'residual_history_sha256':digest(history),
        'residual_history_count':len(history),'residual_first_last':history[:3]+history[-3:]}


def compact(run):
    return dict(replay=run['provenance']['replay'],complete_run_sha256=digest(run),validation=run['validation'],quality=run['quality'],
        solvers=[solver_summary(s) for s in run['solvers']],frozen_control_quality=run['static_control']['quality'],frozen_control_solver=solver_summary(run['static_control']['solver']),
        estimated_work=run['provenance']['estimated_work'],estimated_peak_memory_bytes=run['provenance']['estimated_peak_memory_bytes'],
        sample_hash=run['provenance']['sample_hash'],field_hash=run['provenance']['field_hash'],coil_hash=run['provenance']['coil_hash'],
        timeline_hash=run['provenance']['timeline_hash'],basis_hash=run['provenance']['basis_hash'],basis_singular_values=run['provenance']['basis_singular_values'],
        coil_count=run['readout']['coils'],peak_gradient_t_m=run['readout']['peak_gradient_t_m'],sample_shape=list(np.shape(run['samples'])))


def evidence():
    root=Path(__file__).resolve().parents[1];record=create_scientific_record(read_portable(root/'docs/research/examples/finite-adc-radial-plan.json'))
    payload=json.loads(record['payload_json']);runs={f'adc_{row["parameters"]["adc_duration_s"]}':restore(row['run']['result']) for row in payload['candidates'] if row['feasible']}
    if record['summary']['selected_index'] is not None or payload['candidates'][-1]['feasible']: raise AssertionError('work/timing failures must remain unselected')
    labels=runs['adc_0.002']['design']['labels']
    runs['larger_budget']=run_radial_tse(labels,readout_model='finite_adc',max_work=50000000000)
    runs['stricter_residual']=run_radial_tse(labels,readout_model='finite_adc',max_work=50000000000,inverse_tolerance=1e-12)
    runs['field_mismatch']=run_radial_tse(labels,readout_model='finite_adc',max_work=50000000000,basis_field_scale=0.)
    runs['complex_phase']=run_radial_tse(labels,readout_model='finite_adc',component_phase_rad=[.2,-.6])
    runs['stack_small']=run_radial_tse(np.stack([labels,1-np.asarray(labels)]),readout_model='finite_adc',spokes=8,points=16,control_iterations=20,inverse_max_iterations=40)
    checks={}
    for name in ['adc_0.002','complex_phase','stack_small']:
        exact=independent_bloch_adc(runs[name]);error=exact-runs[name]['samples']
        checks[name]=dict(max_absolute_error=float(np.max(abs(error))),relative_error=float(np.linalg.norm(error)/np.linalg.norm(exact)),
            complex_samples_compared=int(exact.size),reference_hash=digest(exact))
        if checks[name]['max_absolute_error']>2e-11: raise AssertionError('independent hard RF/Bloch/gradient/coil sample comparison failed')
    if not runs['stricter_residual']['validation']['passed'] or runs['larger_budget']['validation']['passed'] or runs['field_mismatch']['validation']['passed']:
        raise AssertionError('separate work, component and field failures changed')
    out=dict(schema='mrqlab-finite-adc-radial-evidence-1',sources=source_manifest(),runtime=runtime_manifest(),
        script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),cases={name:compact(run) for name,run in runs.items()},independent_bloch_adc=checks,
        scientific_record_sha256=record['record_sha256'],scientific_payload_sha256=record['payload_sha256'],search_summary=record['summary'],scope=runs['adc_0.002']['scope'])
    return record,serializable(out)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--record-output',type=Path);parser.add_argument('--verify',type=Path);args=parser.parse_args()
    if args.output.exists() or (args.record_output and args.record_output.exists()): parser.error('output already exists')
    record,result=evidence()
    if args.verify and result!=read_portable(args.verify): raise ValueError('complete finite-ADC radial evidence differs')
    if args.record_output: write_portable(record,args.record_output)
    with args.output.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    for name,row in result['cases'].items(): print(name,row['validation'],'work',row['estimated_work'],flush=True)
    print('record',record['record_sha256'],'independent Bloch',result['independent_bloch_adc'],flush=True)
    if args.verify: print('Independent full finite-ADC radial evidence and scientific search replay match')
