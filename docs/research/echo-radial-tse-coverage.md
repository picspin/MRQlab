# Echo-resolved radial TSE: design, inverse and constrained search

Parent `92be1d2`. Entry `run_radial_tse`, API kind `radial_tse`, research page
**Radial TSE / echo model**. Teaching/research only; B/C remain parked. No scanner
validation, clinical quality certification, submission content, push, PR or merge.

## Missing connection and model

The earlier non-Cartesian chain uses mean TSE echo amplitude. This addition
models the amplitude assigned to **each radial spoke**, then reconstructs images
at declared echoes. The mean-weight baseline and exact-DFT reference are retained.
A shared `prepare_tse_echo_train` now supplies the same periodic EPG echo centers
to Cartesian and radial TSE; all existing Cartesian TSE tests remain active.

The two declared tissue curves include the chassis T1/proton-density priors,
T2 and hard refocusing train. Each spoke's magnitude EPG weight is held constant
across an ideal 2 ms ADC. xy uses golden-angle radial coordinates in cycles/pixel;
kz is a centered Cartesian Fourier encoding. Each TR contains a complete echo
train at one kz. Forward/reverse ordering reassigns radial angles to chronological
echo slots. Timelines include excitation, refocusers, echo/spoke/kz indices,
ADC intervals, dwell and actual tissue weights. Periodic preparation is reused.

For known curves W and two unknown complex component images c, the model is:

`b[kz,m] = sum_j W[j,echo(m)] * Fourier(c[j])[kz,m]`.

The label phantom generates data and evaluates error/ROI contrast. **Labels and
spatial support never enter the inverse operator.** It solves for two independent
complex images. Arbitrary complex spatial phase/amplitude tests verify this.
This is a known-temporal-basis model, not unconstrained T2 estimation or a validated
patient tissue classification. Temporal priors are a real model assumption.

An untruncated SVD W=U S Vh changes numerical coordinates: mixed unknown images
are q=S Uᴴc, with temporal basis Vh; recovered physical components are U S⁻¹q.
Both modes are retained. This is an explicit lossless coordinate change, without
an image-dependent gain, post-hoc amplitude calibration, regularizer or spatial
reference in the solver. Rank-deficient temporal priors fail closed. Full temporal
rank does **not** establish spatial identifiability, as an undersampled regression
shows using tiny data residual and incorrect coefficient maps.

This use of echo evolution and a known temporal basis is motivated by primary
[radial variable-flip TSE research](https://pmc.ncbi.nlm.nih.gov/articles/PMC8678192/)
and [stack-of-stars TSE research](https://pmc.ncbi.nlm.nih.gov/articles/PMC10191119/).
Their slice profiles, reconstruction regularization, optimized waveforms,
measured phantom/patient data and clinical results are **not reproduced** here.
No external implementation or dataset is imported.

## Forward/adjoint, inverse and resource accounting

`EchoSubspaceOperator` combines a paired Fourier operator with per-sample
complex temporal weights; its adjoint conjugates the weights before each Fourier
adjoint. Exact DFT and optional FINUFFT 2.5.0 remain explicit different backends.
Neither a weighted adjoint nor approximate gridding is called an inverse.
Unregularized CGLS starts at zero and reports its fresh measured residual,
iterations, history, work stop and temporal/Fourier diagnostics.

Default 16×16 acquisition uses 96 spokes × 32 points, four echoes, 8 ms spacing,
400 ms TR and two T2 priors [40,120] ms. Targets are independent:

- Declared-echo complex image NRMSE ≤1e-6.
- Physical component-image NRMSE ≤1e-6 against the authored sample.
- Fresh relative data residual ≤1e-10.
- Absolute difference of **mean magnitudes** in the two label ROIs ≥0.005.
- RF energy proxy ≤200, prepared acquisition duration ≤100 s.

The RF proxy sums squared flip/180 over all hard RF events and actual trains.
It is not SAR or scanner RF energy. ROI magnitude contrast cannot be increased
merely by putting a different constant complex phase on each component.

Sample/duration and retained-buffer budgets precede trajectory allocation.
Fourier basis/native-plan estimates reserve memory for retained samples, echo
images and CG vectors. Work charges EPG preparation, the resource-estimation
prototype's actual setup, acquisition, joint inverse and a separately reserved
static-control inverse. The default joint solve has a 6000-iteration ceiling;
its static mismatch control has an explicit 1000-iteration ceiling. Returned
finite images can fail targets on work/iteration exhaustion. Invalid budgets
fail before the affected computation; no resolution is silently reduced.

This new API's work default/cap is **20/50 billion** proxy units; the older
non-Cartesian endpoint retains its 10-billion cap. Exact grids are bounded to
16×16, FINUFFT grids to 32×32, with at most four kz partitions and 24,576 samples.
These planning proxies are not hard RSS, native allocation or wall-time limits.
Large-grid/clinical recovery is not inferred from these small-grid results.

## Measured evidence and honest failures

The [saved evidence](examples/echo-radial-tse-evidence.json) contains every input,
target, solver/budget result, temporal curve and full-result hash. Complete hashes
cover complex samples, component/echo images, timeline and all physical provenance;
summary fields do not replace those computations during replay. Full complex
arrays are available through the API run/export record.

| Case | Complex echo image NRMSE | Component NRMSE | Data residual | RF proxy | Overall |
|---|---:|---:|---:|---:|---|
| Exact DFT, 180° constant | 5.25481e-8 | 6.01322e-7 | 9.59859e-11 | 102 | PASS |
| Exact DFT, 140°→110° | 5.76993e-8 | 7.20402e-7 | 9.86044e-11 | 52.6667 | PASS |
| Exact DFT, 100°→80° | 7.28915e-8 | **1.37485e-6** | 9.78496e-11 | 30.1646 | FAIL component target |
| Work capped at 4 billion | 0.00240920 | 0.0249212 | 7.83171e-7 | 102 | FAIL, work stop |
| Basis T2 changed to [30,120] ms | 0.658529 | 3.04963 | 0.00309400 | 102 | FAIL, model mismatch/work stop |
| FINUFFT, explicit 50-billion budget | 7.10683e-8 | 7.03796e-7 | 9.95462e-11 | 102 | PASS |
| Exact 2-partition stack-of-stars | 5.67312e-8 | 6.07402e-7 | 9.65805e-11 | **204** | FAIL RF target |

The matched exact case uses 4501 joint iterations, 15,806,026,350 total work units
and 51,888,128 estimated peak bytes. FINUFFT uses 4387 iterations and 26,565,612,142
work units: **above the default budget**, so its saved run explicitly raises the
budget to 50 billion. This is not a claim that FINUFFT is cheaper at 16×16.
The 3D example needs 31,551,215,214 units and has its own explicit larger budget.

The same actual echo-weighted samples are also fit with a single static Fourier
image. Its declared-echo image NRMSE is 9.14205 for the matched constant-angle
case. The inconsistent model and weak spatial modes can amplify that error during
unregularized iteration; this control is tied to its recorded 1000-step budget,
not an assertion that every static reconstruction has that exact error.

An independent full 3D complex voxel sum gives relative forward errors
**5.15e-16** (exact) and **2.16e-14** (FINUFFT). Tests additionally compare complete
adjoints, inner products, odd/even kz conventions, arbitrary non-unit complex
coefficient recovery from independent full-frequency data, rank failure, memory
rejection, budget stops and Cartesian/radial EPG equivalence. Full-frequency
lattice tests establish operator/inverse mathematics; they are not presented as
radial spatial-identifiability measurements. The radial results above are
conditional closed-model tests with known temporal priors.

## Optimization, delivery and replay

Search varies pulse timing/angles or echo ordering only. Tissue priors, basis
assumptions, sample truth, numerical resolution, targets and backend stay fixed.
The selection minimizes RF proxy **only among candidates passing every target**.
The 140°→110° candidate is selected; the even lower RF candidate remains failed.
If every executable candidate fails, `best=null`; all outcomes remain in the
response, frontend view and export. Feasibility is not called target acceptance.

The ninth frontend entry exposes the Fourier backend and pulse controls, actual
EPG curves, reference/reconstruction previews with a shared absolute scale,
and an explicitly separate color range for the extreme static mismatch control.
Previews show real parts; ROI contrast uses magnitude and full complex errors
are evaluated independently. Every figure labels its numeric color range; target/error numbers and complete
raw arrays remain available without the control suppressing image visibility. Editing controls
clears old results. Failed-only search results remain exportable and replayable.
The default three-candidate export was measured using actual Node JSON
serialization at **8,043,841 bytes**, exposing the inherited 5 MB import limit.
Research-record import now accepts up to **64 MiB**, with a real >5 MB JSON import
regression and a rejection before reading an oversized file. Larger records
still require the local API/script path; universal large-artifact storage and
streaming are not implemented. Native browser file-flow verification remains open.

Source/dependency manifests pin all package/API Python and lock files; live source
changes are rejected. Runtime includes Python, packages, FINUFFT and BLAS.
An independent process recomputed all seven cases and matched every saved field
and complete complex-result hash. A deliberately changed result hash was rejected
without creating output. Older scientific fixtures retain their own source
anchors; they have not been regenerated to pretend they were made by this code.

```sh
uv sync --locked --extra dev --extra noncartesian
python scripts/verify_radial_tse.py --output /tmp/echo-radial-tse-replay.json \
  --verify docs/research/examples/echo-radial-tse-evidence.json
```

The output path must be new. Exact replay needs the recorded source/environment;
arbitrary cross-platform SVD/BLAS equivalence is not certified.

Full verification: **805 Python passed** (one existing Starlette/httpx warning),
**101 frontend passed** in 14 files, TypeScript and production build passed.
Real HTTP/CORS run and all-candidate search replay matched full hashes. Production
assets are preserved at `/private/tmp/mrqlab-echo-radial-tse-92be1d2-20261030/out-verified`;
tracked generated output was restored and no `git clean` was used.

Actual browser clicking/visual inspection is **unverified**. A fresh browser
inventory again reported `The browser access host is unavailable`. Component
render tests, a static build and HTTP checks are not a completed browser test.
The previous Safari control timeout was not repeated, and no Codex service,
thread lock, user browser or production router was modified as a workaround.

Remaining physics/platform gaps: echo-window off-resonance/relaxation and actual
RF/gradient readout waveforms, slice profiles, B0/B1/coil effects, motion and flow
encoding, measured temporal priors and uncertainty propagation, noise and justified
regularization, arbitrary tissue distributions/T2 inference, large-grid radial
conditioning, universal persisted multimodal study records and browser file-flow
verification. This closes a declared two-curve echo-model connection, not the
entire non-Cartesian TSE or full lab-to-clinical platform objective.
