# Held-out CPMG T2 → waveform image optimization

`measured_waveform_image` derives a finite RF image-target search from a direct
`measured_tse` scientific parent. It verifies the parent envelope and embedded
lab record, requires the same source/runtime, reserves the parent's declared
lab-work budget against `max_parent_work`, and numerically reruns the complete
lab study. The recomputed result hash must match. The waveform's two named
tissues must match the lab tissue IDs exactly; fitted T2 values are bound by ID,
not by an assumed list position.

Only when calibration **and independent holdout** pass are the fitted nominal
T2 values and the four joint rectangular uncertainty corners passed into the
waveform image search. Each T2 case carries the original finite B0/B1 scenarios,
RF candidate grid, fixed signal/image targets, and coarse/refined numerical
checks. The entire five-case grid is preflighted against one shared total voxel-
step budget before any waveform candidate is integrated. A candidate is
eligible only if it passes every declared T2/B0/B1 and refinement scenario;
the minimum edited-block RF energy proxy wins. A failed holdout, a failed
preflight, insufficient shared budget, or all-failed candidates give no selected
image or fallback. Invalid individual RF candidates remain explicitly marked
not executed; a completed assessment of the grid does not mean every candidate
was executable.

Parent TSE design-search completeness is reported separately; an independently
validated calibration is not equated with a successful TSE design. The fitted
receiver amplitude is a nuisance and is **never** applied as image gain. T1,
proton density, B0, B1, labels, geometry and waveform design remain authored.
The lab record's declared origin, source reference, original-file SHA256 when
present, and dataset fingerprint are retained. Every nested image/signal pair
has per-tissue T2 binding to the parent fit, uncertainty interval, used corner,
source declaration and lab hash; other properties are marked authored. A
`measured` origin is a user declaration, not authenticated lab evidence. The
numeric rows and raw-file hash are retained; this bridge does not attach the
original raw file bytes or prove their authenticity.

The parent reservation checks its declared work cap and records its recomputed
estimated work. Existing TSE failed-readout accounting can report more work than
a reservation; if the observed estimate exceeds `max_parent_work`, the bridge
runs no waveform candidate and reports the overrun. This is not preemptive OS
resource enforcement. Waveform voxel steps are accounted separately from parent
lab work units and cannot be added as though they were the same unit.

`POST /research/records` accepts `execution.type=measured_waveform_image` with
`parent_record_sha256`, optional embedded parent, and the typed study. The child
retains its parent, fitted bindings, per-case preflight, complete nested search
results, selection and source/runtime hashes. Integrity validation rechecks
parent/bindings, all scenario input and target consistency, pair origins,
refinement metrics, work and selection without claiming a new simulation;
computational replay actually reruns the parent and complete derived search.
The labelled T2 intervals are local linearized covariance intervals under the
authored independent Gaussian-noise model. Their rectangular corners and the
finite B0/B1 scenarios are stress tests, not a joint clinical confidence region.

## Reproducible synthetic case

`parent_plan()` and `derived_plan()` in
`tests/experiment/test_measured_waveform_image.py` use the explicitly synthetic
analytic CPMG example and the 2×2 synthetic waveform-image fixture. The parent
fit yields approximately **40 ms** and **120 ms**, with conditional standard
uncertainties **0.1316 ms** and **0.6620 ms**. Nominal plus four T2 corners,
combined with nominal and +20 Hz/0.8 B1 cases, consume **624,600 waveform voxel
steps** for RF scales `[0.1, 0.5, 1.0]`. The minimum eligible scale is **0.5**
for the authored 0.01 a.u. reconstructed contrast threshold. T1 and proton
density remain the waveform plan's authored values.

A separate fixed-threshold case uses **0.01866 a.u.**: the nominal T2/B0/B1
grid passes at scale 0.5 but a T2 corner fails, so no candidate is selected.
This threshold tests the gate; it is not a clinical criterion. Other tests cover
failed holdout, insufficient aggregate work, wrong tissue IDs, no-fallback target
failure, an invalid RF point, and rehashed forged per-pair origin. A synthetic
fixture temporarily declares `measured` only inside a provenance-propagation
test; it is not evidence of an actual measurement.

On the source-bound worktree the full Python suite passed **1200 tests**, with
one existing Starlette/httpx deprecation warning. The measured bridge,
waveform-image search and Cartesian focused set passed **19 tests**. A fresh
CLI process recomputed the embedded lab parent and all five T2 cases and
returned an identical child record. Frontend files were unchanged and frontend
tests were not rerun in this round.

Remaining work includes real independently sourced lab/phantom data, raw-file
attachment and authentication, calibrated contrast-agent relaxivity/exchange,
dynamic biology, measured B0/B1, more general pulse/trajectory optimization,
finite ADC aperture, multi-coil/3D/flow/diffusion, physician/agent-facing UI and
external validation. This is teaching/research software and is neither scanner
validation nor clinical quality certification.

## Records workbench and local HTTP verification

The records workbench can load a synthetic waveform template for a saved T2
parent, edit its JSON, state the research question and target rationale, and
save the derived study against that parent's hash. The endpoint
`GET /research/records/{sha256}/waveform-example` only constructs the template;
it does not simulate or assert that the parent's calibration passed. The child
run and replay revalidate the parent. Template geometry, RF, T1, proton density
and thresholds are authored synthetic examples even when the parent origin is
user-declared measured data.

The child record presents parent provenance and revalidation, fitted T2 and
uncertainties, actual T2 corner values, all RF candidates and their T2/B0/B1
outcomes, and separate parent-work and voxel-step budgets. A preview is shown
only for a selected candidate when the view agrees with the record's validation;
malformed or inconsistent evidence is withheld. Records remain historical until
computational replay succeeds. The fixed small Cartesian example is a research
entry point, not a clinical protocol or an unconstrained pulse optimizer.

An isolated local API/database run verified parent creation, template retrieval,
child creation, retrieval and full replay over HTTP, including the frontend
origin's CORS header. The frontend route returned HTTP 200 and a production
build completed; browser-window inspection could not be performed because the
computer-use browser host was unavailable. Component tests cover the UI and its
failure states but do not replace a visual or interactive browser assessment.
Frontend validation for this workbench change: **209 tests passed**, TypeScript
checking passed, and the Next.js production build passed in a temporary copy so
that generated output in the worktree was not overwritten.
The full Python regression after adding the template endpoint passed **1200
tests**, with one existing Starlette/httpx deprecation warning.
