"""Reproduce pressure-flow/finite-RF/causal-gating evidence without scanner data.

Run in the locked project environment. Output must not exist. --verify compares
all scientific fields exactly against a saved run; timing is not part of this file.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
from mrqlab_experiment.pulsatile_flow import WomersleyPipe
from mrqlab_experiment.pulsatile_dir import run_pulsatile_dir
from mrqlab_experiment.study_records import source_manifest,runtime_manifest


def evidence():
    pipe=WomersleyPipe(mean_gradient_pa_m=0.)
    fv=[]
    for n in [32,64,128]:
        dr=pipe.radius/n; r=(np.arange(n)+.5)*dr; faces=np.arange(n+1)*dr
        a=pipe.nu*faces[:-1]/(r*dr**2); b=pipe.nu*faces[1:]/(r*dr**2); b[-1]*=2
        L=np.diag(-a-b)+np.diag(a[1:],-1)+np.diag(b[:-1],1)
        independent=np.linalg.solve(1j*pipe.omega*np.eye(n)-L,np.full(n,pipe.harmonic_acceleration))
        reference=pipe.coefficients(r)[1]
        fv.append(dict(cells=n,relative_velocity_error=float(np.linalg.norm(independent-reference)/np.linalg.norm(reference))))
    standard=run_pulsatile_dir()
    irregular=run_pulsatile_dir(r_peaks_s=[0.,.45,1.65],observation_end_s=2.8,radial_rings=4,axial_spins=201)
    absent=run_pulsatile_dir(r_peaks_s=[0.],observation_end_s=.5,radial_rings=4,axial_spins=201)
    refinements=[]
    for rings,axial,rf in [(4,201,128),(8,401,128),(16,801,256)]:
        r=run_pulsatile_dir(r_peaks_s=[0.],observation_end_s=1.2,radial_rings=rings,axial_spins=axial,rf_steps=rf)
        refinements.append(r)
    clipped=[]
    for cancelled in [.006,.905,.908]:
        clipped.append(run_pulsatile_dir(r_peaks_s=[0.,cancelled],observation_end_s=1.9,radial_rings=4,axial_spins=201))
    return dict(schema='mrqlab-pulsatile-dir-evidence-1',scope='authored pressure waveform, rigid laminar pipe; teaching/research only; no clinical/scanner validation',
        sources=source_manifest(),runtime=runtime_manifest(),script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        independent_finite_volume=fv,regular=standard,irregular=irregular,no_completed_readout=absent,
        quadrature_refinements=refinements,clipped_waveforms=clipped)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,required=True); parser.add_argument('--verify',type=Path); args=parser.parse_args()
    if args.output.exists(): parser.error('output already exists')
    result=evidence()
    if args.verify:
        expected=json.loads(args.verify.read_text())
        if expected!=result: raise ValueError('scientific replay differs from saved evidence')
        print('Complete evidence replay matches, including all candidate runs, interruptions, sources and runtime')
    with args.output.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False); stream.write('\n')
    print('Finite-volume checks:',result['independent_finite_volume'])
    for name in ['regular','irregular','no_completed_readout']:
        print(name,result[name]['validation'],result[name]['provenance']['estimated_work'])
