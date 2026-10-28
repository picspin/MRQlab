# TSE echo-dependent imaging coverage

Audit baseline: 4dbbb76. This baseline does **not** implement spatial TSE PSF.

| Existing component and verification | Missing connection | This iteration |
|---|---|---|
| `spatial_imaging.py:run_spatial_imaging`; `test_spatial_clinical_simulation_reconstruction_validation_provenance` | Mean absolute train signal becomes a static image before independent FFT | Keep baseline intact; add explicit echo-resolved chain |
| `spatial.py:cartesian_indices/cartesian_acquire/cartesian_reconstruct`; `test_cartesian_complex_phantom_recovery` | Ordering does not change tissue weight | Reuse FFT conventions and reconstruction; bind each ky/kz line to echo |
| `family_templates.py:build_family_sequence(TSE3D)`; `tests/experiment/test_sequence_family_e2e.py` | Sparse ky train per centric kz, not complete arbitrary image grid | Segment all ky lines into exact-length trains per kz; reject incomplete trains |
| `templates.py:build_sequence(TSE)` | RF, CPMG shifts and 2 ms ADC windows already exist | Reuse authored train, replicate at TR boundaries with explicit line readout windows |
| `family_execution.py:simulate_family`, `_PartitionBackend`; `EPGBackend.apply/observe` | EPG periodic preparation and RF ramp exist, but downstream averages echoes | Sample exactly at each echo, retain tissue-specific signal and preparation cost |
| `family_search.py`, `clinical_search.py`, family recipes/result graph | Design, question, validation, provenance patterns already exist | Replayable research chain with design, timeline, physical provenance and budgets |

Scope: teaching/research ideal independent voxels, hard RF pulses, spoiled periodic
EPG and ideal Cartesian encoding. No scanner validation or clinical image-quality
certification. No B1 inhomogeneity, physical gradient timing, motion, parallel
imaging, finite RF/slice profiles or hardware export; milestones B/C stay parked.

## Implemented chain and replay

Entry: `mrqlab_experiment.tse_imaging.run_tse_imaging`. The original
`run_spatial_imaging` remains the historical mean-weight ideal acquisition chain.
The new chain uses the same family recipe, authored TSE3D template, periodic EPG
preparation, result provenance, FFT convention and Cartesian reconstruction.

For each tissue, sample the existing 2 ms ADC gate once at its start (the authored
echo center), using dwell=2 ms. Keep absolute EPG amplitude per echo, including
T1 periodic recovery, T2 decay and the authored refocusing-angle ramp. For ideal
180-degree CPMG the adjacent-echo ratio is exp(-echo_spacing/T2), verified against
the analytic expression. General RF ramps use EPG, not that exponential shortcut.
Magnitude-only transfer intentionally discards the EPG phase.

Ny must divide exactly into `echoes`-long trains. Traverse ky in linear or centric
order, segment that traversal into trains, and traverse kz centric. No padding,
dropped lines or silent partial train. Every TR has excitation, explicit
refocusing times/angles and one full kx line per echo. Each line records echo
index/time, ky/kz, ADC window, dwell, kx indices and both tissue weights. The
single periodic prepared spin train is reused at every TR: ideal spatial encoding
has no feedback on the spin state. The stored one-train SequenceIR is the EPG
kernel; the returned timeline is the complete image readout, not a scanner-ready
SequenceIR or executable gradient waveform. Existing sparse partition gradient
lobes are teaching units and are not converted into physical gradient designs.

The forward model is `sum_t FFT(mask_t) * M_t(ky,kz)`, constant along kx.
`PSF_t = inverseFFT(M_t)`. There is no single tissue-independent PSF for distinct
T2 values. Reconstruct the summed acquired k-space without gain fitting,
deconvolution or amplitude rescaling. Validate the forward model against direct
circular convolution as well as FFT convolution. The reference image uses the
same train-mean tissue amplitude as the baseline ideal weighting model.
`weighting='mean'` makes every echo constant per tissue and returns the same ideal
Cartesian recovery to 1e-12; it is retained as a regression test.

```python
import numpy as np
from mrqlab_experiment.tse_imaging import run_tse_imaging

y, x = np.indices((16, 16))
labels = (((y-8)**2 + (x-8)**2 < 20) | ((x == 3) & (y > 3))).astype(int)
r = run_tse_imaging(labels, echoes=8, order='centric', t2_s=(.04, .12))
replay = run_tse_imaging(**r['provenance']['replay'])
assert np.array_equal(r['image'], replay['image'])
```

Output includes clinical question, design, timing map, measured echo weights,
modulation, complex reconstructed image, PSFs, validation and replay provenance.
Provenance retains physical result graphs, kernel sequence, input/timeline/sample
hashes, acquisition and steady-preparation duration. The sample budget counts
image complex samples. Work is a conservative FFT-term proxy plus both tissue EPG
costs, not wall time or scanner cost. Duration includes the longest tissue
preparation (tissues coexist) plus all TRs. Integer budgets and timing/count
inconsistencies fail explicitly. EPG work budgets are enforced by the reused
family kernel and again on combined tissue and spatial cost. This does not
estimate scanner SAR, slew rate or gradient heating.

## Quantitative verification

16x16 known two-class phantom above, TE spacing 8 ms, TR 400 ms, ideal 180-degree
refocusing, T2=40/120 ms. Errors below compare echo-dependent reconstruction to
the ideal train-mean reference, with **no amplitude correction**.

| Echoes | ky order | Image NRMSE | PSF RMS radius, 40/120 ms (voxel) | Outside-half-mainlobe peak ratio, 40/120 ms |
|---|---|---|---|---|
| 2 | linear | 0.090168 | 0.793413 / 0.266420 | 0.099668 / 0.033321 |
| 2 | centric | 0.090168 | 0.209311 / 0.070285 | 0.063860 / 0.021350 |
| 4 | linear | 0.271741 | 1.098108 / 0.375839 | 0.140257 / 0.047097 |
| 4 | centric | 0.269555 | 1.292199 / 0.442289 | 0.127100 / 0.042863 |
| 8 | linear | 0.667117 | 1.475661 / 0.537797 | 0.253218 / 0.086792 |
| 8 | centric | 0.664187 | 1.519769 / 0.551543 | 0.236876 / 0.082338 |

PSF amplitude half-maximum widths are returned per axis as discrete contiguous
sample counts. In these small-grid examples they remain one voxel: subvoxel
broadening cannot be inferred from that integer metric. RMS radius includes
energy in the periodic-grid tails and thus measures spreading/ringing as well as
blur. The reported sidelobe metric is the maximum outside the half-amplitude
mainlobe box divided by peak, **not** a first-null sidelobe definition. Image NRMSE
includes changes in contrast/amplitude and artifacts; it is not a pure resolution
measure. Centric segmented trains do not guarantee globally monotonic low-pass
weighting or universally superior resolution. No clinical threshold is asserted:
`quality.passed` tests ideal-reference equality; its false result for echo weighting
is expected. `psf_prediction_quality.passed` tests forward-model consistency.

31 new tests in `tests/experiment/test_tse_imaging.py` cover both orderings,
2D/3D, 2/4/8 echoes, distinct T2, analytic decay, RF ramp, unique complete line
coverage, explicit timing and weights, replay hashes, direct convolution,
constant-weight recovery, discrete PSF metrics, and invalid designs/budgets.

Full validation in the new worktree:

- Python: `python -m pytest tests/ -q`: **542 passed**, one existing Starlette/httpx deprecation warning.
- Frontend: `npm test -- --cache=false`: **82 passed**, 12 files. Existing node_modules reused via a local ignored symlink; cache disabled proactively to avoid writing the shared dependency cache.
- TypeScript: `npx --no-install tsc --noEmit`: passed.
- `git diff --check`: passed (new files also checked with `git diff --no-index --check /dev/null FILE`).

## Remaining gaps

This is a full **teaching Cartesian acquisition timeline and echo-resolved image
forward model**, not full RF/gradient-resolved spatial spin evolution. Signal is
held at the echo-center amplitude over each 2 ms Fourier readout window; intraline
T2/off-resonance evolution is absent. No transient first-TR imaging: all trains
use the converged spoiled periodic state. No arbitrary incomplete train, optimized
2D ky-kz echo scheduling, scanner pulse export, B1 inhomogeneity, physical gradient
constraints, motion, parallel imaging, noise, clinical calibration or scanner
validation. Tissue PSFs are circular on the finite periodic FFT grid. No frontend
entry/API is added; that remains the later backlog item. Milestones B/C remain
parked. This work makes no clinical image-quality certification claim.
