# Fast non-Cartesian inverse: matrix-free Fourier plans

Parent anchor `3b518f5`. Research/teaching only; no scanner validation, clinical
quality certification, hardware/export path or Milestone B/C unlock.

## What is connected

`mrqlab_recon.nufft.RadialNUFFTOperator` implements a CPU FINUFFT type-2 forward
and type-1 adjoint pair. `radial_nufft_cgls` performs an actual iterative inverse;
a type-1 transform alone is not an inverse. This distinction and the unnormalized
sums follow the [FINUFFT mathematical definitions](https://finufft.readthedocs.io/en/stable/math.html).
The existing exact-DFT CGLS remains the independent small-grid reference.
The legacy `nufft_reconstruct` name still denotes approximate nearest-neighbor
gridding; its docstring now states that limitation.

Array axes are `(z,y,x)` or `(y,x)`; trajectory columns are `(kx,ky)` in
cycles/pixel. FINUFFT receives `(2πky,2πkx)` and centered modes, forward sign -1,
adjoint sign +1, complex128, oversampling 2, FFTW estimate and one CPU thread.
Cartesian kz retains the centered FFT and its adjoint factor `nz`. The coordinate,
mode-order and reusable-plan conventions follow the
[Python interface](https://finufft.readthedocs.io/en/stable/python.html) and
[CPU options](https://finufft.readthedocs.io/en/stable/opts.html).

The new `reconstruction='nufft_cgls'` runs the family tissue simulation, fast
Fourier acquisition, inverse, absolute image validation and replay through
`run_spatial_imaging` and `/research/run`. The Research page exposes an explicit
reconstruction selector. The API permits up to 64×64, 4 Cartesian-kz partitions,
24,576 samples and its existing 10-billion work-proxy cap. The lower-level Python
operator supports larger grids subject to its budgets. The 128×128 radial study
below deliberately requests a larger work budget; it is not an API default.

No image gain fitting, density compensation, preconditioner, regularizer or image
prior is used. The family chain still uses mean TSE echo amplitude; this change
does not implement echo-dependent non-Cartesian TSE acquisition.

## Installation and replay

The optional backend is pinned to FINUFFT **2.5.0**:

```sh
uv sync --locked --extra dev --extra noncartesian
python -m pytest tests/ -q
```

The base installation keeps the exact DFT and gridding paths. Selecting FINUFFT
without the optional dependency fails explicitly; there is no silent fallback.
`uv.lock` also now contains the pre-existing required cryptography dependency
and its cffi/pycparser dependencies, which the inherited lock omitted. Existing
locked versions were preserved.

```python
from mrqlab_experiment.spatial_imaging import run_spatial_imaging
result = run_spatial_imaging('noncartesian', labels, encoding='radial',
    reconstruction='nufft_cgls', spokes=48, points=32,
    inverse_tolerance=1e-11, nufft_eps=1e-13, max_work=10_000_000_000)
replayed = run_spatial_imaging(**result['provenance']['replay'])
assert replayed['provenance'] == result['provenance']
```

Both acquisition and solver retain backend version, transform tolerance, dtype,
thread count, ordering, oversampling, normalization and budget model. Replay
retains numerical parameters and raw sample hashes; the API pins source and
checks result hashes. The portable measured-TSE record runtime now includes the
optional FINUFFT version or `not installed`. Historical example
`tse-lab-study-record.json` remains pinned to its original `3b518f5` source and
Python environment; use that anchor to replay it. It has not been relabeled as a
new-source result.

## Accuracy, budget and failure semantics

Transform `eps` is an accuracy request, not an image error bound. The inverse
requires `eps <= tolerance/10`. Every solve starts at zero and reports iterations,
recursive history, a fresh final measured data residual, convergence and stop
reason. A finite returned image may fail its target. A small residual may also
coexist with an incorrect undersampled image.

The operator allocates reusable plans instead of an M×N² Fourier basis. Before
native plans are created it checks a conservative memory allowance (two plans,
sorting, CG vectors, padded grids, 32 MiB native overhead) and work reservation.
A versioned FFT/spreading proxy charges setup, all transforms and final residual;
the experiment includes acquisition work. These proxies are **estimates**, not
hard native allocator/RSS, FLOP, execution-time or scanner-cost guarantees.
Native allocations and platform-dependent planning remain an explicit limitation.

## Reproducible evidence

Run from this source anchor and locked environment; the output path must be new:

```sh
PYTHONPATH=packages/recon:packages/mrqlab_experiment:packages/physics:packages/sequence-ir:services/api \
  python scripts/verify_fast_noncartesian.py --output /tmp/fast-nufft-evidence.json
```

The [saved evidence](examples/fast-noncartesian-evidence.json) includes source and
script hashes, input hashes, runtime, exact-subset checks, all targets and stop
reasons. Timings are machine observations and are not acceptance gates. An independent
process rerun matched all numerical results, targets, input/source/script hashes
and runtime exactly, with timing fields excluded.

| Case | Data origin | Iterations | Image NRMSE (target ≤1e-6) | Measured relative data residual (target ≤1e-10) | Result |
|---|---|---:|---:|---:|---|
| 16×16 phase/amplitude phantom, radial 48×32 | Full independent direct DFT | 912 | 4.63e-9 | 7.63e-11 | Both pass |
| 128×128 smooth complex Gaussian, radial 192×256 | Same FINUFFT model, independent 37-sample sum check | 300 | 1.0234e-6 | 4.73e-9 | Both fail; iteration limit |
| Same 128 radial case, limit raised to 2200 | Same as above | 1912 | 1.84e-7 | 1.00e-10 (below requested threshold) | Both pass |
| 128×128 random complex image, jittered square lattice | Same FINUFFT model, independent 37-sample sum check | 17 | 2.97e-11 | 2.68e-11 | Both pass |

The small case's full independent acquisition difference is 1.04e-14. The large
cases' exact-subset relative differences are 1.25e-13 and 8.73e-14. Smooth radial
image recovery is a closed approximate-model test, not independent full-data
validation or evidence for arbitrary radial-image identifiability. The square
lattice covers frequencies absent from radial disk sampling, and is a different
trajectory. Its faster convergence is not a radial performance claim.

The 128 radial planning memory estimate is 117,440,512 bytes; the dense DFT basis
estimate exceeds the existing 128 MiB cap and is rejected. Its long solve used
158,321,459,200 work-proxy units and about 11.1 seconds on this machine. This is
outside the bounded web API budget and remains a lower-level Python experiment.

Tests additionally compare full forward and adjoint results against direct DFT
for 16/17 grids, odd/even kz, displaced impulses, random complex arrays and
unscaled complex phantom recovery. They exercise undersampling false confidence,
work/iteration limits, zero data, unavailable dependency, invalid precision,
API real backend/replay, larger-grid gates and frontend method selection.

## Verification and remaining gaps

Locked Python 3.12.14 / NumPy 2.5.2 / FINUFFT 2.5.0: **688 passed**, one existing
Starlette/httpx deprecation warning. Frontend: **96 passed** (14 files), TypeScript
and production build pass. Browser production flow used a real API: select
FINUFFT → simulate → image target passed → replay result hash matched. The QA
port 3001 was rejected by existing CORS; the final check used the already allowed
port-3000 origin. No CORS permissions were expanded. Native file download/import
was not retested in this phase.

Remaining: radial conditioning/preconditioning, noisy-data regularization and
selection, coil sensitivities/parallel imaging, off-resonance, trajectory and
gradient calibration, full echo-dependent non-Cartesian TSE, independent full
large-grid acquisition validation, hard native resource containment and cross-
platform replay tolerances. These remain gaps in the complete platform goal;
this phase does not certify scanner or clinical reconstruction quality.


## Echo-resolved continuation

The separate [echo-radial TSE stage](echo-radial-tse-coverage.md) now retains
per-spoke EPG echo weights and reconstructs two unknown temporal-basis images
with paired direct/FINUFFT operators. It adds constrained pulse search and records
model-mismatch, work-stop and RF-target failures. The mean-echo family chain
described above remains unchanged. Full echo-window timing, measured priors,
coils/noise/trajectory calibration and general T2 inference are still gaps.
