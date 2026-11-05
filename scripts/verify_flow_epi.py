"""Recompute causal motion-encoded EPI, controls and complete scientific search."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
from mrqlab_experiment.flow_epi import run_flow_epi,epi_waveform,SpatialMovingEnsemble
from mrqlab_experiment.pulsatile_flow import WomersleyPipe
from mrqlab_experiment.flow_imaging import GAMMA
from mrqlab_experiment.study_records import source_manifest,runtime_manifest
from mrqlab_api.research import serializable
from mrqlab_api.scientific_records import create_scientific_record,write_portable,read_portable


def digest(value): return sha256(json.dumps(serializable(value),sort_keys=True,allow_nan=False).encode()).hexdigest()


def compact(run):
    return dict(replay=run['provenance']['replay'],run_sha256=digest(run),validation=run['validation'],
        work=run['provenance']['estimated_work'],planned_work=run['provenance']['planned_work'],
        memory=run['provenance']['estimated_peak_memory_bytes'],readout_status=run['readout_status'],
        final_state_hashes=run['provenance']['final_state_hashes'],waveform_sha256=run['provenance']['waveform']['gradient_hash'],
        complete_images=[dict(trigger=i['trigger'],image_sha256=digest(i['image']),kspace_sha256=digest(i['kspace']),
            frozen_reference_sha256=digest(i['frozen_reference']),quality=i['quality']) for i in run['images']],
        velocity_pairs=[{**{k:v for k,v in p.items() if k not in ['velocity_m_s','valid_mask','gradient_moment_reference_m_s','instantaneous_reference_m_s']},
            'complete_pair_sha256':digest(p)} for p in run['velocity_pairs']],
        executions=[dict(gate=r['gate'],encoding_sign=r['encoding_sign'],tissues={name:dict(stage=t['stage'],end_s=t['end_s'],
            actual_samples_sha256=digest(t['samples']),actual_commands_sha256=digest(t['applied_readout_commands']),
            state_hash=t['state_hash'],positions_hash=t['positions_hash'],finite_rf_energy_uT2_s=t['finite_rf_energy_uT2_s']) for name,t in r['tissues'].items()}) for r in run['executions']])


def independent_adc_reference():
    pipe=WomersleyPipe(oscillating_gradient_pa_m=0.);r=np.array([0.,.001,.0018]);v=pipe.velocity(r,0.)
    z=np.array([-.002,.001,.0025]);xy=np.array([[.0002,-.001],[.0012,.0001],[-.0008,.0017]])
    initial=np.array([1+.3j,-.2+.7j,.5-.1j]);s=SpatialMovingEnsemble(z,xy,motion=pipe.motion(r),off_hz=7.)
    s.state[:,0]=initial.real;s.state[:,1]=initial.imag
    at=0.;m0=np.zeros(3);m1=np.zeros(3);errors=[]
    for c in epi_waveform()['commands']:
        dt=c['duration_s'];g=np.array(c['gradient_t_m']);m0+=g*dt;m1+=g*(at*dt+dt*dt/2);at+=dt
        s.advance(dt,gx_t_m=g[0],gy_t_m=g[1],gz_t_m=g[2])
        if c['adc'] is not None:
            analytic=initial*np.exp(-at/.15)*np.exp(1j*(2*np.pi*7*at+GAMMA*(xy@m0[:2]+z*m0[2]+v*m1[2])))
            errors.append(float(np.max(abs(s.state[:,0]+1j*s.state[:,1]-analytic))))
    if max(errors)>2e-12: raise AssertionError('independent complex point-ADC reference failed')
    return dict(adc_count=len(errors),max_absolute_complex_error=max(errors),reference='independent constant-velocity Cartesian Bloch exponential with actual gradient moments')


def evidence(plan):
    runs=dict(regular=run_flow_epi(),steady_no_dir=run_flow_epi(preparation='none',oscillating_gradient_pa_m=0.),
        interrupted_epi=run_flow_epi(r_peaks_s=[0.,.917],observation_end_s=1.4),
        single_image=run_flow_epi(r_peaks_s=[0.],observation_end_s=1.1),
        no_image=run_flow_epi(r_peaks_s=[0.],observation_end_s=.5),
        alias_no_dir=run_flow_epi(preparation='none',mean_gradient_pa_m=400.,oscillating_gradient_pa_m=0.,axial_spins=801))
    # Offline refinement declares its larger allowance. The browser/API retains
    # the 200-million per-run limit; no default target is relaxed for refinement.
    refinements=[run_flow_epi(axial_spins=axial,rf_steps=rf,ramp_steps=ramp,max_work=400000000) for axial,rf,ramp in [(201,64,8),(401,128,8),(801,128,16)]]
    record=create_scientific_record(plan)
    if record['summary']['selected_index'] is not None or record['summary']['model_reported_passed']:
        raise AssertionError('default failed search must not manufacture a selection')
    if runs['steady_no_dir']['velocity_pairs'][0]['velocity_rmse_m_s']>.0005:
        raise AssertionError('steady no-DIR phase-encoding reference failed')
    if not 0<len(runs['interrupted_epi']['executions'][0]['tissues']['blood']['samples'])<256:
        raise AssertionError('interrupted EPI must retain a genuinely partial raw acquisition')
    if runs['no_image']['images'] or runs['single_image']['velocity_pairs']:
        raise AssertionError('missing samples or opposite encoding must not produce invented measurements')
    w=epi_waveform()
    result=dict(schema='mrqlab-causal-flow-epi-evidence-1',sources=source_manifest(),runtime=runtime_manifest(),
        script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),independent_adc=independent_adc_reference(),
        gradient_moments=dict(duration_s=w['duration_s'],m0_t_s_m=w['m0_t_s_m'],delta_m1_t_s2_m=w['delta_encoding_m1_t_s2_m'],
            venc_m_s=w['venc_m_s'],peak_gradient_t_m=w['peak_gradient_t_m'],nominal_slew_t_m_s=w['nominal_slew_t_m_s']),
        cases={k:compact(v) for k,v in runs.items()},refinements=[compact(v) for v in refinements],
        scientific_record_sha256=record['record_sha256'],scientific_payload_sha256=record['payload_sha256'],
        search_summary=record['summary'],scope=runs['regular']['scope'])
    return record,serializable(result)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--verify',type=Path);parser.add_argument('--record-output',type=Path);args=parser.parse_args()
    if args.output.exists() or (args.record_output and args.record_output.exists()): parser.error('output already exists')
    root=Path(__file__).resolve().parents[1];record,result=evidence(read_portable(root/'docs/research/examples/flow-epi-plan.json'))
    if args.verify and result!=read_portable(args.verify): raise ValueError('complete flow EPI evidence differs')
    if args.record_output: write_portable(record,args.record_output)
    with args.output.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    for key,value in result['cases'].items(): print(key,value['validation'],flush=True)
    print('complete record',record['record_sha256'],'independent ADC',result['independent_adc'])
    if args.verify: print('Independent complete flow-EPI evidence, failed search and all acquisition hashes match')
