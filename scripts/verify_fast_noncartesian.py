"""Reproduce fast Fourier evidence; no scanner data or image gain fit.

PYTHONPATH=packages/recon:packages/mrqlab_experiment:packages/physics:packages/sequence-ir:services/api python scripts/verify_fast_noncartesian.py --output /tmp/nufft-evidence.json
An existing output is never overwritten. Timings are observations, not gates.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import time
import numpy as np
from mrqlab_recon.nufft import RadialNUFFTOperator, radial_nufft_cgls
from mrqlab_recon.spatial import radial_acquire, radial_coordinates
from mrqlab_recon.trajectories import _make_nema_like_phantom
from mrqlab_experiment.study_records import source_manifest


def relative(a,b): return float(np.linalg.norm(a-b)/np.linalg.norm(b))


def run_case(name,image,xy,limits,independent_full=False):
    started=time.perf_counter(); op=RadialNUFFTOperator(xy,image.shape)
    data=op.forward(image); acquire_s=time.perf_counter()-started
    estimate=op.estimated_memory_bytes; backend=op.diagnostics(); del op
    y,x=np.indices(image.shape); n=image.shape[-1]
    rng=np.random.default_rng(61)
    indices=np.unique(np.r_[len(xy)//2,rng.choice(len(xy),36,replace=False)])
    ref=np.array([np.sum(image*np.exp(-2j*np.pi*(xy[j,0]*(x-n//2)+xy[j,1]*(y-n//2)))) for j in indices])
    check=dict(samples=len(indices),relative_error=relative(data[0,indices],ref),absolute_l2_error=float(np.linalg.norm(data[0,indices]-ref)))
    if independent_full:
        exact_xy,exact=radial_acquire(image,48,32)
        assert np.array_equal(exact_xy,xy)
        check['full_dft_relative_error']=relative(data,exact); data=exact
    results=[]
    for limit in limits:
        started=time.perf_counter()
        rec,d=radial_nufft_cgls(xy,data,image.shape,max_iterations=limit,tolerance=1e-10,max_work=300_000_000_000)
        error=relative(rec,image)
        results.append(dict(requested_iterations=limit,iterations=d['iterations'],stop_reason=d['stop_reason'],
            data_converged=d['converged'],relative_data_residual=d['relative_data_residual'],
            image_nrmse=error,image_target=1e-6,image_target_passed=error<=1e-6,
            estimated_work=d['estimated_work'],elapsed_s=time.perf_counter()-started))
    return dict(name=name,shape=list(image.shape),samples=len(xy),input_sha256=sha256(image.tobytes()+xy.tobytes()).hexdigest(),
        acquisition='independent direct DFT' if independent_full else 'same FINUFFT model; closed-model inverse, independent subset sums only',
        independent_check=check,operator=backend,estimated_memory_bytes=estimate,acquire_elapsed_s=acquire_s,solves=results)


def evidence():
    y,x=np.indices((16,16)); image=2.7*_make_nema_like_phantom(16)*np.exp(1j*(x*.13-y*.07))
    small=run_case('direct DFT complex radial reference',image,radial_coordinates(image.shape,48,32),[1500],True)
    y,x=np.indices((128,128)); image=2.7*np.exp(-((x-64)**2+(y-64)**2)/180)*np.exp(1j*(.013*x-.007*y))
    radial=run_case('smooth radial 128',image,radial_coordinates(image.shape,192,256),[300,2200])
    rng=np.random.default_rng(27); xy=np.column_stack([x.ravel()-64,y.ravel()-64])/128
    xy=(xy+rng.uniform(-.1,.1,xy.shape)/128+.5)%1-.5
    image=rng.normal(size=(128,128))+1j*rng.normal(size=(128,128))
    jitter=run_case('square-coverage jittered lattice 128',image,xy,[100])
    return dict(schema='mrqlab-fast-nufft-evidence-1',scope='teaching/research, no scanner or clinical certification; no gain fit or regularization',
        source_manifest=source_manifest(),script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        runtime=dict(python=platform.python_version(),numpy=np.__version__,platform=platform.platform()),cases=[small,radial,jitter],
        limits=['large-grid inverse uses closed-model samples with independent exact subset checks',
                'radial case is smooth, not evidence of arbitrary-image identifiability',
                'time and planning memory/work proxies are not hard resource guarantees',
                'coil/noise/trajectory/off-resonance/echo-weighted TSE remain absent'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    if args.output.exists(): parser.error('output already exists')
    result=evidence()
    with args.output.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False); stream.write('\n')
    for case in result['cases']:
        print(case['name'],case['independent_check'])
        for solve in case['solves']: print(solve)
