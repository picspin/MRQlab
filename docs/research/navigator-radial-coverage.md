# Data-navigated radial TSE: measured intervals to verified pulse selection

This extends `5432087` with actual data-based estimation of two global T2 curves
before spatial reconstruction. The prior stage's fixed-basis failures remain
unchanged historical evidence. The new study explicitly changes acquisition and
computation; it does not retroactively make the old four-echo/32-point experiment
pass. The parent example is **synthetic**, with authored T1/proton density. This
is teaching/research, not scanner validation or clinical quality certification.

## Acquired inputs and inference boundary

The unchanged [historical measured-TSE parent](examples/calibrated-radial-parent-record.json)
still supplies tissue/component identity and the same two calibrated T2 intervals
in seconds. Its full numerical study is revalidated from the original lossless
measurement request before those intervals are used. Its original record sources
are retained; this is not a relabelled replay of the older source/runtime envelope.

The [new plan](examples/navigator-radial-plan.json) uses six echoes, 8 ms spacing,
400 ms TR, **144 spokes and 33 points**, instead of four echoes, 96 spokes and
32 points. Current radial coordinates use a symmetric inclusive radial grid;
an even point count has no exact origin. The estimator selects only coordinates
exactly equal to `(0,0)`, never a nearest point or interpolated center. The
centered kz=0 plane supplies the global mixture for a stack. The complete spatial
example verified here is 2D 16×16; large/3D navigated inversion remains open.

The inference function accepts coordinates, raw complex samples, sample-to-echo
assignments, timing/flip design, T2 interval priors and the authored tissue
chassis. **Labels, reference images and true sample T2 are not its arguments.**
The same holds for the underlying spatial CGLS operator. In the simulation wrapper,
labels/sample T2 generate the acquisition and evaluate the result separately.

At least four exact-center repeats per echo are required. With the example
trajectory there are 24 per echo. Alternating repeats of the first four echoes
form the fit set. The remaining repeats and the entire fifth/sixth echoes form
the holdout set. Held-out values do not select T2, starts or optimization steps.
Within-echo consistency is an additional static-mixture check.

For each trial T2 pair, the existing periodic magnitude EPG model generates two
curves. Complex linear least squares eliminates their two unknown global DC
mixture coefficients; bounded finite-difference Gauss–Newton steps then update
only the two T2 parameters. Five fixed starts are independent of sample truth and
holdout data. The disjoint ordered intervals preserve component identity. The
fitted DC mixture coefficients are retained as **navigation nuisance parameters**;
they never scale the inverse images or replace unknown spatial coefficient maps.

The separation of linear and nonlinear parameters follows the general idea of
[Golub and Pereyra's separable least squares](https://epubs.siam.org/doi/abs/10.1137/0710036?journalCode=sjnaam).
EPG-based fitting of MRI relaxation information from k-space also has published
precedent in [ME-CAMBREC](https://pubmed.ncbi.nlm.nih.gov/24753216/).
Those methods motivate the approach; their experimental validation does not
validate this implementation or supply its measured priors. Our global
two-class navigator is much narrower than general voxelwise parameter mapping.

Acceptance requires fit and holdout relative residual <=1e-10, within-echo
repeat consistency <=1e-10, a locally full-rank projected T2 Jacobian and local
relative T2 standard uncertainty <=5%. Repeat variability or a declared acquisition
noise level supplies the conditional noise estimate; a numeric precision floor
prevents zero covariance. The example is noiseless: its tiny uncertainties
describe numerical/local model precision, not measurement accuracy or clinical
confidence. At active interval bounds the unconstrained local covariance is
still only a sensitivity diagnostic. Local rank/multiple starts do not prove
global uniqueness or a continuous robust optimum.

## Same-data comparison and independent references

The existing radial TSE chain produces the raw samples and a complete fixed
nominal-prior mismatch control. The navigator reads exactly those samples and
then runs unregularized temporal-basis CGLS with its estimated EPG curves. The
unknowns remain two unrestricted complex spatial maps. No image support,
regularization, reference image or fitted image gain is introduced. Exact DFT
remains the reference backend; this example is not a fast NUFFT result.

All original acquisition, EPG and static-control costs stay charged. Each
50-billion scenario allowance reserves 20 million for navigation, then divides
the rest between the original chain and the new CGLS solve. The original chain
also reserves its existing single-static-image mismatch control, so the two
component inverses do **not** receive equal remaining work. In particular the
180-degree nominal fixed-prior solve stops early despite a matching prior.
Do not attribute that nominal difference solely to T2 correction. The corner
controls additionally contain actual prior mismatch. Per-solve diagnostics and
the complete raw samples remain in every saved scenario.

An independent complex annihilating-filter calculation checks all five
180-degree scenarios. For equally spaced ideal-180 echoes, two exponential
poles obey `y[n+2] = (r1+r2)y[n+1] - r1*r2*y[n]`; linear least squares and a
quadratic root solve recover `T2=-ESP/log(r)`. This reference uses six measured
center values, not the EPG fitting algorithm or image labels. Tests additionally
generate analytic complex mixtures independently of the EPG acquisition.

## Preserved results and failed candidate

All ten nominal/corner scenarios execute under the original strict image and
component NRMSE <=1e-6 and spatial data residual <=1e-10 targets. Contrast remains
>=0.005, total relative RF <=200 and prepared duration <=100 s.

| Candidate | Scenario | Image NRMSE | Component NRMSE | Spatial data residual | All targets |
|---|---|---|---|---|---|
| 180 degrees | nominal | 8.06452e-8 | 4.15550e-7 | 9.92399e-11 | PASS |
| 180 degrees | corner-0 | 9.57804e-8 | 5.11268e-7 | 9.99080e-11 | PASS |
| 180 degrees | corner-1 | 1.26509e-7 | 6.75533e-7 | 9.98402e-11 | PASS |
| 180 degrees | corner-2 | 1.42084e-7 | 7.48956e-7 | **1.14990e-10** | **FAIL** |
| 180 degrees | corner-3 | 1.08678e-7 | 5.82699e-7 | 9.97326e-11 | PASS |
| 140 to 110 degrees | nominal | 4.76972e-8 | 2.38014e-7 | 8.26835e-11 | PASS |
| 140 to 110 degrees | corner-0 | 9.33104e-8 | 4.56466e-7 | 9.90503e-11 | PASS |
| 140 to 110 degrees | corner-1 | 7.45050e-8 | 3.62866e-7 | 9.94412e-11 | PASS |
| 140 to 110 degrees | corner-2 | 7.28082e-8 | 3.33566e-7 | 9.65356e-11 | PASS |
| 140 to 110 degrees | corner-3 | 5.59076e-8 | 2.12993e-7 | 9.59072e-11 | PASS |

The 180-degree corner-2 fails the spatial residual gate at its reserved work
stop, even though image/component errors pass. It is not eligible. The
140-to-110-degree candidate passes all five scenarios and is selected among this
finite grid only. Total preparation+acquisition RF proxies are **162.5** and
**82.23703703703704**; these are not SAR/hardware safety limits. Navigation
estimated each synthetic T2 pair to relative error below 2e-12. That is closed-
model noiseless recovery, not evidence of comparable physical accuracy.

The full grid reserves **501,000,000,000** work-proxy units including the parent
revalidation allowance, under an explicit 600-billion shared cap. Actual work
is **483,664,688,904**. Operator memory/retained result buffers are budgeted per
scenario; earlier operator plans are released before the second solve. Limits
remain planning proxies, not hard operating-system containment.

Corrupting only the held-out fifth/sixth echoes by 0.1% leaves the first-four fit
unchanged but yields holdout residual **0.000385195** and fails. Tests also reject
missing exact centers, an absent second component, noisy/inconsistent repeats,
overlapping intervals, insufficient withheld echoes, and exhausted work/evaluation
allowances. No failed navigation can qualify merely because its preview image
passes a separate image target.

## Records, frontend and reproducibility

The same strict `calibrated_radial_tse` execution adds explicit reconstruction
choice `navigator_t2`; the default remains `fixed_prior`. Measured parent identity,
full embedded historical parent, calibrated interval bindings and all scenario
results remain in the portable child. Its inner provenance stage is named
`data_navigated_uncertainty_search`. Old examples are not regenerated under the
new source fingerprint; replay them at their original anchors.

The parent record pane offers **载入中心导航示例（6 回波 / 33 点）**. This loads the
new acquisition and budget visibly into the editable JSON, preserves the strict
targets, and requires the user's research rationale. The child table labels the
data-estimated basis, navigator holdout status and complete scenario outcomes.
The plot includes a labelled fixed nominal-prior control on the same samples.
Displayed T2 is in ms; record bindings and estimates use seconds.

The [compact evidence](examples/navigator-radial-evidence.json) includes every
scenario's run/sample/basis/navigator hashes, independent Prony estimates,
targets, costs and failed controls. Reproduce in the locked environment with new
output paths:

```sh
.venv/bin/python scripts/verify_navigator_radial.py \
  --verify docs/research/examples/navigator-radial-evidence.json \
  --output /tmp/navigator-radial-evidence.json --record-output /tmp/navigator-radial.json
.venv/bin/python -m mrqlab_api.scientific_records --store /tmp/navigator-radial.sqlite3 \
  import /tmp/navigator-radial.json
.venv/bin/python -m mrqlab_api.scientific_records verify /tmp/navigator-radial.json
.venv/bin/python -m mrqlab_api.scientific_records --store /tmp/navigator-radial.sqlite3 \
  replay /tmp/navigator-radial.json --output /tmp/navigator-radial-replayed.json
```

The script and `replay` recompute the complete study; `import`/`verify` check
integrity only. The large complete record and build artifacts stay outside source
at `/private/tmp/mrqlab-navigator-radial-5432087-20261030/`; the repository stores
the plan and compact evidence alongside the unchanged parent.

Full regression: **856 Python passed**, one existing Starlette/httpx warning;
**113 frontend passed** in 16 files; TypeScript and production build passed.
The complete child identity is
`6f512d7e3f3cb041b8bc28ad9923c00fdab54b24f49e30fd9ac86fb23192a9c3`.
An independent evidence process reproduced every case and that complete record
byte-for-byte, including the independent Prony reference (maximum relative
agreement error 1.70109e-12). An empty SQLite store imported exactly the unchanged
parent and child; a separate generic CLI replay also produced byte-identical
complete JSON. Actual HTTP/CORS create, child/parent retrieval and full
computational replay through local port 8008 returned the same record/payload
identity, preserved the failed 180-degree candidate and selected candidate 1.
The full portable child is 13,696,363 bytes; its hashes include all complex data,
candidate runs and navigator diagnostics rather than only preview summaries.
The preceding stage's historical record/parent/evidence files were not rewritten.
Build outputs were preserved outside source and generated tracked files restored
without `git clean`; original handoff scratch and notes remain intact.

A fresh browser inventory still reports **The browser access host is
unavailable**. Actual rendered clicking, visual inspection and native file-picker/
download verification remain open. Component/HTTP checks and static generation
do not close that boundary; no Safari control or service/lock workaround was used.

## Remaining requirements

This closes one conditional two-global-T2 navigator path, not general measured
or voxelwise T2 inference. The strict repeated-center gate rejects noisy data;
noise-aware estimation, uncertainty propagation to images, continuous uncertainty
guarantees, broader/overlapping tissue distributions, phase/off-resonance/B1,
slice profile and within-ADC evolution, coils/trajectory calibration, full 3D
navigated inversion and clinical transfer remain open. Fixed T1/PD and a two-class
static sample remain substantive assumptions. Source/runtime replay does not
authenticate original measurements. Earlier flow/CEST/MRS fidelity and measured
calibration gaps, browser/native-file checks and platform persistence requirements
remain active. B/C stay parked, submission materials stay excluded, and no push,
PR, merge or workspace relocation is performed.
