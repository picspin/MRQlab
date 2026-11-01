# Platform goal: verified anchors and remaining requirements

This is the current project-facing status of the MRI pulse design/optimization
platform. It records evidence, rather than redefining the goal around implemented
models. The broader lab-to-clinical teaching/research platform goal remains active.
No scanner validation, clinical quality certification or patient recommendation
claim is made. Milestones B (Executable Sequence) and C (Licensed Local Compute)
remain parked; the existing Milestone A protocol catalog still has two entries.

## Local anchors, in requested order

| Anchor | Scope | Full verification at that anchor |
|---|---|---|
| `dac373b` | Exactly the requested TSE report, implementation and tests | Python 542; frontend 82; TS/diff pass |
| `9664125` | Exact-DFT CGLS radial/stack-of-stars reference inverse | Python 564; frontend 82; TS/diff pass |
| `60fb11b` | Persistent moving spins, finite slice RF/Gz, retrospective trigger acceptance | Python 583; frontend 82; TS/diff pass |
| `5b660ab` | Concurrent CEST/semisolid MT/effective rNOE and controls | Python 603; frontend 82; TS/diff pass |
| `d292956` | Coupled-spin finite-RF MRS basis and full complex readout fit | Python 619; frontend 82; TS/diff pass |
| `cf1973e` | Browser design, simulation, finite search, explicit targets and pinned replay | Python 641; frontend 90; TS/diff/build pass |

All commits are local. No push, PR or merge was performed. This branch contains
the preceding anchors in sequence; the worktrees remain independently inspectable.
The original TSE worktree's unrelated `.DS_Store` was excluded from its commit.

## Requirement audit

| Requirement | Current evidence | Status / missing evidence |
|---|---|---|
| RF/gradient orchestration matched to standard sequence schemes | SequenceIR, family templates/composition/lowering and finite research timelines exist; ideal TSE RF/timing/ky controls now share a bounded human/agent edit contract | General operation-level RF/physical-gradient control across paired imaging runners, uniform constraints and cross-engine equivalence remain incomplete; B/C stay parked |
| Tissue biophysics under intrinsic/extrinsic influence | Explicit static per-tissue concentration/relaxivity now reaches common Bloch/EPG, scoring and TSE; PGSE diffusion and liquid-water CEST parameter-binding checks pass | Legacy unitless `PhysiologyModel.contrast_agent_concentration` is rejected rather than ignored. Dynamic kinetics, agent-induced diffusion/exchange, spatial joint state, measured relaxivity/uncertainty and biological validation remain incomplete |
| Doctor MR Image / Agent Signal Vector bidirectional reading and control | A complete complex TSE pair has units/axes/tissue bindings and an inverse-transform check; both use the same source-pinned parent-preserving semantic edits with actual browser/CLI replay | This is one declared ideal TSE adapter, not a universal cross-modality contract, real-anatomy validation or proven physician/LLM usability. General waveform control and multimodal state/optimization remain incomplete |
| Clinical question → pulse/design → physical simulation | Twelve backend chains carry explicit research questions, design/timing parameters, physical provenance and scientific boundaries | Implemented for declared teaching chains with common question/context and execution-record stages; general clinical target translation, measurement bindings and calibrated priors remain incomplete |
| Lab experiment → clinical target | Measured-input TSE and a velocity-CSV → conditional pressure → finite-RF DIR study include units, calibration, independent holdout and uncertainty; flow retains exact raw CSV bytes | Flow example is synthetic and its design targets fail; measured CEST/MRS calibration, authenticated lab evidence and robust clinical target translation remain incomplete |
| Parameter optimization | Each chain executes an explicit candidate grid and preserves every point; API search distinguishes execution feasibility from target pass | Measured TSE has bounded uncertainty-corner target checks; general constrained/multi-objective and cross-modality optimization remain incomplete |
| High-precision non-Cartesian inverse | Unscaled complex 2D/3D recovery, paired direct/FINUFFT operators, measured-prior/navigated radial TSE and an exact finite-ADC hard-180° reference with T2/B0 and known receive maps | Finite-ADC default budget fails; an explicit larger-budget stricter-residual reference passes unchanged image/component targets. Variable-flip/finite-RF echo-window coherence, measured field/coil/trajectory calibration, noisy uncertainty and general voxel T2 inference remain incomplete |
| Real flow / slice / gating | Pressure-driven Womersley shear/backflow, finite RF/Gz, causal interruption, bipolar/EPI point-ADC images and conditional velocity-derived pressure with independent holdout/covariance/corner refinement | Default DIR targets fail. Measured-flow study produces DIR signals, not joint MR-image pressure inference. Straight rigid pipe/fixed transverse centers only; measured-image phase/velocity calibration, general 3D/compliant flow and realistic hardware/readout remain incomplete |
| CEST MT/NOE | Effective-pool baseline, signed Solomon relay and finite-history generalized Bloch semisolid RF including zero offset, independent augmented Bloch references and full-trace convergence gates | Default relay target fails; contrast-passing high-power point fails refinement, so no design is selected. Measured molecular calibration, full multi-spin/Redfield relaxation and spatial joint imaging remain incomplete |
| More complete MRS | 1–3 spin density helpers, finite RF/isotropic J, 3D PRESS quadrature and a separate local-Lindblad/full-TR quantum chain with independent Bloch/Kraus/ODE references and T1/saturation failures | Quantum relaxation/TR is not yet coupled to 3D PRESS. Validated molecular/Redfield library, realistic maps/noise, measured spectra and clinical concentration calibration remain incomplete |
| Frontend entry | `/research`, bounded `/research/run` and `/research/search`, actual backend plots/tables, failure states, strict input and source checks | Twelve entries include finite-ADC radial mode, causal decisions, ADC completeness, image/velocity validity and failed-only searches. CEST, quantum-MRS, finite-ADC radial and shared-record native JSON browser replay pass; other modality/CSV coverage remains open |
| All verifiable and replayable | Source/result/search hashes, full run and candidate inputs, Python/NumPy versions, exact backend replay tests, source-change rejection | All twelve chains and measured TSE share immutable local multi-study SQLite records, complete source/runtime-pinned CLI/API replay and lossless portable snapshots; cross-platform replay, raw attachments and general derived multimodal workflows remain incomplete |
| Submission content excluded | Inherited `docs/ismrm` matches 33 original manuscript-worktree files before project removal; original worktree and Git history retained; ignore rule prevents accidental untracked re-entry | Enforced in the current project snapshot; historical anchors intentionally remain immutable |
| No push/PR/merge, B/C parked | Local commit chain, unchanged roadmap/locked catalog; API regression retains two A protocols | Preserved |

## Submission/project separation

The parent history had inherited a manuscript directory from earlier work. It
was not new content authored in this iteration, but keeping it in the current
project would violate the user's explicit separation requirement. Its original
files remain in `/Users/hilbert/work/MRQlab-worktrees/ismrm-fix/docs/ismrm`, and
in Git history at `4342840`. The current project snapshot removes that directory
and ignores its path. Generic protocol/physics execution regression tests were
retained under `tests/experiment/test_protocol_execution_regressions.py`.
Other worktrees, including manuscript worktrees and MRQlab-pr53, were not modified.
Optional relocation of related workspace folders has not been performed: it must
not silently copy manuscript content into the project or disturb live worktrees.

## Next evidence to obtain

1. Extend the verified CEST/quantum-MRS/finite-ADC/shared-record native JSON flow to the
   remaining modality-specific and CSV paths; retain verified CLI local delivery.
2. Extend the shared scientific records and the measured-TSE → radial derivation
   with raw-data archives, general unit/uncertainty conventions and measured
   bindings for CEST/NOE and MRS. The conditional velocity-to-flow binding now
   retains raw bytes and independent holdout; actual measured-image calibration
   and general flow inference remain open. Preserve failed target outcomes.
3. Continue fidelity work in the original priority order. Report model validity,
   conditioning, independent references and failed targets without gain fitting,
   hidden calibration or a claim of clinical/scanner certification.
4. Verify the expanded platform contract: operation-level RF/gradient control,
   explicit intrinsic/extrinsic tissue state (including concentration/relaxivity),
   and a common linked MR Image / Signal Vector representation with typed edits,
   complete recomputation and observable target evidence. Existing fields and
   separate model outputs do not establish this bidirectional requirement.

The preceding partial implementations are progress toward the full objective;
they are not evidence that every platform requirement has been achieved.

After manuscript separation and test relocation, full validation still reports
Python **641 passed** and frontend **90 passed** (13 files); TypeScript passes.
The original manuscript worktree remains at `4342840` with only its pre-existing
untracked `.DS_Store`. The current project has no tracked submission directory.


## Measured-input TSE stage (2026-10-29)

The current `lab/measurement-study` worktree extends `94f67b5` with a measured-input
TSE pilot around existing ExperimentGraphs, independent holdout/calibration gates,
T2-uncertainty scenario checks, reconstructed ROI contrast targets, six-stage
provenance and portable source/runtime-pinned records. A real CLI CSV import,
atomic save and complete computational replay are verified. The production
browser also completed the full JSON-based study and replay. Native CSV file
selection/import was observed; native JSON download/re-import remains open.

The new [coverage report](lab-measurement-study-coverage.md) and self-contained
[example record](examples/tse-lab-study-record.json) preserve assumptions, failed
cases and exact inputs. The Python↔JavaScript number-serialization boundary was
found in browser testing and fixed with explicit numeric canonicalization and a
lossless request snapshot; real Node roundtrip replay is a regression test.

This advances measured data ingestion, conditional uncertainty and local staged
persistence for TSE. It does not complete measured-data calibration for flow,
CEST or MRS, a universal scientific study schema, multi-study project persistence,
or the remaining physics-fidelity requirements. The full platform goal remains
active; B/C stay parked, submission content remains excluded, and no push/PR/merge
was performed.

Measured-input stage full verification: Python **667 passed**, frontend **95
passed** (14 files), TypeScript and production build passed. The final example
CSV byte hash and complete computational replay were checked after source freeze.


## Fast non-Cartesian stage (2026-10-29)

From `3b518f5`, optional pinned FINUFFT plans now connect fast acquisition,
paired adjoint, actual CGLS inverse, image validation, source/result replay and
an explicit frontend method selector. Exact DFT remains the independent small-
grid reference. The [coverage report](fast-noncartesian-coverage.md) and
[reproducible evidence](examples/fast-noncartesian-evidence.json) retain both the
128 radial 300-iteration failure and the later passing longer solve. Large
image recovery is explicitly closed-model with independent exact subset checks.
The large radial solve exceeds API budgets; resource limits are planning proxies.

Locked-environment validation: Python **688 passed**, frontend **96 passed**,
TypeScript and production build pass. The real browser/API FINUFFT simulation
and exact result-hash replay passed. The full goal remains active: noise/coil/
trajectory and radial-conditioning work, physical flow/gating, microscopic NOE,
real MRS basis and cross-modality measured-study closure remain unfinished.
B/C stay parked; no submission content, push, PR or merge was introduced.


## Pulsatile-flow and causal-gating stage (2026-10-29)

From `3acac6a`, the [new coverage report](pulsatile-causal-dir-coverage.md) records
pressure-driven Womersley flow, exact accelerating-trajectory gradient integrals,
finite slice RF, volume-weighted ring reservoirs, causal trigger decisions and
physically propagated partial RF interruptions. Independent fluid finite-volume
and Bloch RK4 checks supplement replay. Both default regular/irregular designs
fail their declared targets and remain recorded as failed. No-readout cases
produce no blood/wall measurement values.

The sixth research entry executes the real model and distinguishes scheduled
preparations from eventual completed readouts. Source/result hash replay and
full numerical evidence rerun passed. Python **719 passed**, frontend **97
passed**, TypeScript and production build pass. The straight rigid pipe and
authored pressure waveform do not complete general or measured hemodynamics.
The full objective remains active; CEST microscopic NOE and fuller MRS fidelity,
cross-modality measured closure and remaining reconstruction/image gaps continue.
B/C remain parked, with no push, PR, merge or submission content.


## Solomon relay CEST/MT stage (2026-10-29)

From `75dcbaa`, the [new coverage report](solomon-relay-cest-coverage.md) records
signed isotropic dipolar rates from distance and correlation time, a non-exchanging
donor coupled to a labile bridge, and concurrent water CEST/semisolid MT. A
four-state population transition network and full independent Cartesian ODE
validate the minimal pair model. Fast-motion negative contrast and failed power
candidates remain visible; the bridge-disconnected water effect vanishes.

The seventh research entry supports real simulation, pulse-power search and
source/result/candidate hash replay. Molecular priors are fixed during design
search and varied only through separate sensitivity runs. Portable-JSON CLI
verification now handles tuple-based pool arrays, with actual roundtrip and
spectrum-tampering regressions. Independent evidence recomputation matched.
Python **746 passed**, frontend **98 passed**, TypeScript and production build
pass. Full multi-spin/Redfield coherence, near-resonance generalized MT, measured
priors and spatial CEST/NOE remain open. The complete platform goal stays active;
no push, PR, merge, B/C unlock or submission content was introduced.


## Handoff continuation and PRESS localization (2026-10-30)

`e1574a8` is a verification-only Claude handoff on `9664125`, not a solver
change or NUFFT implementation. Independent historical revalidation passed
**568 Python / 82 frontend**. Four tests were carried forward as `34e871e`
with strict original image targets, and the missing 3D 32×32 gridding NRMSE
**0.5425621821984188** was reproduced in both historical and current checkouts.
The handoff's 16×16 3D stop typo is explicitly resolved as `data_residual`,
`converged=true`. Both `.pi/` and `HANDOFF-TO-CODEX.md` remain untracked and intact.
[Integration evidence](handoff-noncartesian-integration.md) separates that exact-DFT
reference from the later FINUFFT feature. Original TSE/non-Cartesian worktrees
still point to `dac373b`/`9664125`; no worktree merge or cleanup was performed.

Read-only reinspection on 2026-10-31 finds the handoff checkout at `2d1cfb0`,
a documentation-only child of `e1574a8` filling that same 3D gridding value.
Its untracked `.pi/` and handoff file are preserved; this later observation does
not change the solver anchor or the integration evidence above.

The eighth research entry now covers finite-RF PRESS [-1,+1,-1] coherence
selection, complex 3D volume quadrature, explicit excitation rephasing and
full-complex basis fitting. Separate spatial/RF/FOV targets and center-point /
J-mismatch failures are preserved. Default maximum amount error is 7.85237e-5;
center-basis mismatch error is 0.662351. The [coverage report](press-volume-coverage.md)
and [replayable evidence](examples/press-volume-evidence.json) record physical
assumptions, source/runtime manifests, complex-volume hashes and remaining gaps.

Python **770 passed**, frontend **99 passed**, TypeScript/production build and
independent CLI/real HTTP replay pass. Browser clicking/visual inspection of the
new entry remains unverified because browser access was unavailable and native
Safari control timed out. A separate UI “another app” symptom was traced to the
Codex managed app-server's active thread writer, not to a Claude worktree lock;
no service or lock was altered. Validated molecular libraries, full relaxation,
measured multimodal closure, persistent universal scientific records and earlier
physics gaps still prevent completion of the overall goal. B/C remain parked;
submission content is excluded; no push, PR or merge was performed.


## Echo-resolved radial TSE stage (2026-10-30)

From `92be1d2`, the [new coverage report](echo-radial-tse-coverage.md) and
[recomputed evidence](examples/echo-radial-tse-evidence.json) connect periodic EPG
echo curves to timed radial spokes / Cartesian kz, paired temporal-basis
forward/adjoint operators, actual unregularized inverse and declared-echo images.
Two unknown complex component maps use known EPG temporal priors; labels only
generate/evaluate the sample. Lossless two-mode temporal SVD is explicit, without
image gain fitting or a spatial reference inside the inverse. Exact DFT and
FINUFFT remain distinct backends with independent voxel-sum checks. The shared
EPG helper preserves Cartesian TSE behavior; original worktree anchors stay intact.

The ninth research entry searches pulse/echo schedules and minimizes RF proxy
only among candidates passing every image/component/residual/contrast/RF target.
The 140°→110° candidate passes and reduces the RF proxy from 102 to 52.6667; the
100°→80° candidate has an image error below 1e-6 but **fails** the separate
component target, so is not selected. Model-mismatch/work-stop and 3D RF-limit
failures remain available. No passing candidate means no best design, while
complete failed-only search records can still be exported/replayed.

Python **805 passed**, frontend **101 passed**, TypeScript/production build,
independent all-case CLI recomputation and real HTTP run/search replay passed.
An intentionally changed evidence hash was rejected. Browser clicking/visual
inspection remains unverified: a fresh inventory still reports unavailable
browser access. The full objective remains active; measured multimodal scientific
records, calibrated priors/uncertainty and the remaining physical/browser gaps
are not replaced by this closed-model evidence. B/C stay parked; no submission
material, push, PR, merge or production-router change was introduced.


## Shared scientific-record stage (2026-10-30)

From `2d6e8fa`, [common local scientific records](scientific-records-coverage.md)
now persist all nine research runners/searches plus the measured TSE workflow.
Study context, target rationale, lossless request/result snapshots, full complex
results, every candidate, sources/runtime and five dependency-hashed stages form
one immutable record. Background references cannot silently claim calibration.
The original measured TSE calibration/holdout/uncertainty stages remain intact.

The new `/research/records` library groups distinct physics under a study ID,
exports/imports portable records, and separates historical target reports, content
integrity and actual current-environment computational replay. Research and lab
study screens can recompute, compare the expected execution hash and save.
SQLite transaction/idempotence/concurrency/corruption checks and real CLI
process tests supplement every-model replay and actual Node numeric roundtrip.
The default local database lives in the project `.mrqlab/` directory and is
ignored by Git; it is not an in-memory service or a cloud deployment.

Python **828 passed**, frontend **108 passed**, TS and production build passed.
Real HTTP/CORS saved three records under one study; after an actual API restart,
a new process recovered and fully recomputed all three exactly, retaining the
TSE target failure and MRS invalid candidate. An independently replayed complete
example is committed with its plan. API lazy app export preserves compatibility
and removes CLI double-import warnings. No existing scientific fixture was
regenerated to falsely relabel its original source anchor.

The browser host remains unavailable, so rendered browser/file-flow verification
is still missing. Universal raw/measurement/uncertainty bindings, calibrated
clinical translation, cross-record derived workflows and earlier physics gaps
remain unfinished; common records do not claim those capabilities. The full goal
remains active, B/C stay parked, and no push/PR/merge, submission import or
production-router change occurs.


## Measurement-derived radial design stage (2026-10-30)

From `3fdf6fc`, a saved measured-TSE parent now supplies actual calibrated T2
bindings to a new radial pulse-design study, after its original numerical study
and independent holdout are revalidated. The original historical parent and its
source/runtime are retained unchanged. This is numerical parent revalidation,
not a claim to replay its older source/runtime envelope under new code.
The portable child embeds the complete parent; importing it into an empty store
retains both records and requires no external parent database for child replay.

The [coverage report](calibrated-radial-coverage.md) and
[recomputed evidence](examples/calibrated-radial-evidence.json) preserve all ten
executed scenarios. Both 180-degree and 140-to-110-degree candidates pass nominal
image/component targets, but each fails all four inherited T2 interval corners
with the nominal inverse basis held fixed. Worst component NRMSE is 0.04375074
and 0.02171317 respectively. No candidate is selected; relative RF reductions
do not override failed targets. The derived total RF proxy includes periodic
preparation, separate from the standalone acquisition-only field. T1/PD remain
authored, and the supplied parent data are synthetic. Rectangular local stress
samples are not clinical or continuous worst-case bounds.

Python **842 passed**, frontend **111 passed**, TS and production build passed.
Actual HTTP save/full replay, independent evidence recomputation, and a new CLI
process replay in an isolated store match the entire child record. The measured
parent pane exposes derivation and the child distinguishes nominal preview from
the failed uncertainty study. Browser access remains unavailable, so clicking,
visual and native file-flow checks remain open. Cross-modality calibration,
uncertainty-aware inversion, earlier physical-fidelity and persistence gaps still
prevent completion of the full goal. B/C remain parked; no submission import,
push, PR, merge, router change or project-folder relocation occurred.


## Exact-center T2 navigator stage (2026-10-30)

From `5432087`, an explicit six-echo / 144-spoke / 33-point acquisition supplies
exact k=0 data for a bounded two-global-T2 EPG fit inside the measured intervals.
The first four echoes fit the curves; last-two echoes and alternating repeats
validate them. The estimator and spatial CGLS receive no labels/reference/sample
T2. Complex DC mixture coefficients are navigation nuisance parameters and never
rescale images. The unchanged historical measured parent is numerically
revalidated; authored T1/PD and synthetic input origin remain explicit.

The [coverage report](navigator-radial-coverage.md) and
[independently checkable evidence](examples/navigator-radial-evidence.json) preserve
all ten runs, same-data fixed-prior controls, work/memory allowances, independent
complex Prony references for ideal 180-degree echoes and withheld-model failures.
The 140-to-110-degree candidate passes all five local stress cases; the 180-degree
corner-2 stops at residual 1.14990e-10 and fails the unchanged 1e-10 data target,
despite image/component errors below 1e-6. Its failure is retained. Selection is
conditional on this finite noiseless two-class grid and changed acquisition,
not a continuous robust or clinical optimum. Full-grid work is 483,664,688,904
under an explicit reserved 501-billion / capped 600-billion planning allowance.

Python **856 passed**, frontend **113 passed**, TS and production build passed.
Independent complete evidence/CLI replay is byte-identical; isolated import
retains the parent and child, and actual HTTP save/read/full replay matches both
record and payload identities while retaining the failed 180-degree candidate.
The parent-pane preset visibly loads new echoes, center sampling and budgets;
the child labels data-estimated curves and withheld validation separately.
Browser/native-file verification remains unavailable. Noise-aware uncertainty
propagation, broader tissue distributions/voxel mapping, full readout physics,
measured flow/CEST/MRS closure and the earlier platform gaps remain unfinished.
The overall goal stays active; B/C remain parked, with no submission import,
push, PR, merge, production-router change or folder relocation.


## Causal motion-encoded EPI stage (2026-10-30)

From `71f2f4d`, the tenth research entry couples the pressure-driven axial flow
and persistent finite-RF ensemble to actual bipolar velocity encoding, gradient-
integrated EPI sampling and unscaled complex image reconstruction. Cell/slab
intersection geometry determines receive weights without fitted normalization.
Trigger interruptions retain executed state, gradient-command prefixes and raw
ADC values; incomplete grids do not generate images, and a single image does not
generate a flow measurement. Opposite encodings retain their separate cardiac
times, gradient-moment reference, instantaneous reference and measured validity.

The [coverage report](flow-epi-coverage.md) and
[recomputed evidence](examples/flow-epi-evidence.json) preserve the default DIR
velocity RMSE **0.04820858 m/s**, complex frozen-image NRMSE **0.202502** and
failed suppression/retention targets. A steady no-DIR phase-encoding control has
velocity RMSE **0.00024026 m/s** but still fails the combined DIR/image targets.
The finite search retains two executable failures and one gradient-infeasible
point; **no design is selected**. A 0.917-second interruption keeps 30/256 raw
samples with no fabricated image/velocity. All 256 independent complex ADC
references match within 2.59184e-14; RF/axial/ramp refinement preserves the target
failure. The finest offline refinement explicitly exceeds the unchanged API
work cap, with its larger budget recorded.

Final validation after the receive-volume correction: Python **881 passed**,
frontend **114 passed**, TS and production build passed. Independent full
evidence/new-process CLI and actual HTTP create/read/import/export/full replay
match the complete scientific search and retain every failed/infeasible point.
The browser host remains unavailable, so rendered/visual/native-file checks
remain open. This is authored rigid-pipe point-ADC imaging, not measured or
general clinical flow: transverse transport, realistic gradient switching,
coils/noise/field maps, phase calibration, clinical transfer and prior CEST/MRS
and platform gaps remain unfinished. The overall goal remains active; B/C stay
parked, submission materials stay excluded, and no push, PR, merge, router change
or workspace relocation occurred.

## Finite-memory semisolid CEST / MT stage (2026-10-30)

From `de9cdb3`, the eleventh research entry integrates a time-domain generalized
Bloch Green function with complex shaped RF, all pulse/gap history, liquid
exchange and the existing signed Solomon relay. Zero offset is regular in this
different physical model; the canonical singular absorption-rate model still
rejects its zero-offset case. No frequency clamp, Gaussian substitution, signal
gain, sign clipping or inter-pulse reset was added. Common semisolid Z and the
short-coherence exchange guard remain explicit limitations.

The [coverage report](cest-memory-coverage.md) and
[independently recomputed evidence](examples/cest-memory-evidence.json) retain
all seven offsets and all five controls at 3,840/7,680 intervals, full-grid
water/bound convergence checks, maximum-error witnesses and whole-history hashes.
Default full-trace difference **0.0001184018** passes the **0.0002** gate, but
relay contrast **0.0025574892** fails **0.005**. At 2 µT both contrasts pass while
full-trace difference **0.0003887770** fails; the malformed gap is infeasible.
No candidate is selected. Signed negative controls and independent 19-state
Bloch/hard-pulse/long-lag references are preserved. The larger explicit work
allowance and unchanged physical targets are documented rather than hidden.

Full regression is **903 Python / 115 frontend**, with TS and production build
passing. Independent full evidence, a new generic CLI process and actual HTTP
create/read/full replay match the complete scientific search. Actual in-app
browser access recovered: the default run, result replay, native download and
file-chooser reimport pass, as do recompute/save, record-link navigation, complete
record native export/import and full computation replay. The screen distinguishes
integrity PASS, historical physical targets FAIL and current replay PASS.
Two browser-discovered record-status inconsistencies were fixed and verified.
Historical reports of browser unavailability describe their own earlier anchors;
they no longer describe this checked JSON path. Other modality/CSV browser tests,
measured molecular binding, full relaxation/spatial physics and earlier platform
gaps remain open. The full goal stays active; B/C stay parked. No submission
import, push, PR, merge, router change or workspace relocation occurred.

## Quantum-relaxed MRS / full TR stage (2026-10-31)

From `7fef144`, the twelfth research entry evolves complete small-spin densities
under finite RF, chemical shift/J and independent local Lindblad baths, through
every ADC dwell and the physical post-readout recovery. The full composed TR
channel supplies a trace-constrained periodic state, with explicit finite-dummy
alternatives, condition/residual and all-node physical-state checks. No scalar
envelope, equilibrium reset, gain calibration, eigenvalue clipping or hidden
timing overlap is used. The ideal independent-spin dephaser is explicitly distinct
from a spatial crusher. The existing 3D PRESS chain is not silently upgraded.

The [coverage report](quantum-mrs-coverage.md) and
[independently recomputed evidence](examples/quantum-mrs-evidence.json) preserve
separate 32→64 basis and 64→128 sample RF comparisons, full FID/basis/state/cycle
identities, independent analytic Bloch, Kraus, Choi and coupled density-ODE tests.
Default amount error **0.0000929760** passes, while fully recovered and wrong-T1
bases fail at **0.6050918985** and **0.7851670354**. The latter has residual
**0.0040118410**, illustrating why a good fit alone does not prove quantification.
The .18-s TR retains only **.1239166322** of its fully recovered signal and fails
the unchanged .2 target. The finite grid selects .30 s at **.2117922124**; .10 s
is infeasible because complete ADC ends at .1585 s. This is not a clinical optimum.

Regression is **930 Python / 116 frontend**, with TS/build passing. Independent
full evidence, a new generic CLI process and actual HTTP save/read/full replay
match the complete scientific search. Actual browser testing covers default run,
equilibrium mismatch, all search failures, a 7.26-MB native download/file-chooser
reimport and exact candidate/selection replay. Browser scientific-record save,
native export/import and complete recomputation also match; console errors are
absent. The quantum chain still needs 3D PRESS/crusher coupling, molecular and
measured calibration, realistic field/noise models and uncertainty; earlier
platform gaps remain open. The full goal stays active, B/C stay parked, and no
submission import, push, PR, merge, router change or folder relocation occurred.

## Finite-ADC radial / B0 / receive-map stage (2026-10-31)

From `998b612`, the existing radial TSE entry gains explicit finite point-ADC
T2 decay and spatial B0 phase, individual complex receive channels and balanced
ideal prephaser/readout/rewinder moments. This exact dense DFT reference requires
hard 180-degree CPMG; unsupported variable flips, FINUFFT selection and timing
overlaps fail explicitly. Authored field/receive maps are retained with units and
hashes, without coil/RSS normalization or calibration. The two unrestricted
complex component maps use a complete temporal SVD, no image support or gain fit.

The [coverage report](finite-adc-radial-coverage.md) and
[independently recomputed evidence](examples/finite-adc-radial-evidence.json)
compare all raw samples against separate hard-RF rotations, physical gradient
integration, T1/T2/B0 evolution and coil sums: default/complex-phase 2D cases each
have 6,144 values, maximum absolute error about **1.19e-12**; a 3D case matches
all 512 values. Complete forward/adjoint, odd/even kz and independent dense-LS
tests cover arbitrary complex maps without spatial truth in the solver.

The default 20-billion budget fails at image error **.0018707920**, component
error **.0183800985**, residual **6.50136e-8**, with a visible work stop. Raising
only the budget to 50 billion reaches residual **9.96574e-11** yet component
error **1.45323e-6** still fails. A separate **stricter 1e-12** residual target
and explicit larger allowance recover components to **7.64134e-9**, preserving
the original 1e-6 image/component gates. Default frozen-ADC control error is
**.3847829515**. Wrong-field, complex-phase budget and 3D undersampling failures
remain preserved. No default ADC-duration candidate qualifies for selection.

Regression is **954 Python / 117 frontend**, with TS/build passing. Independent
evidence, a new generic CLI process and actual HTTP create/read/full replay match
the entire failed scientific search. Browser native research download/reimport
and all-candidate replay, scientific save/link/export/import/full replay also
match; the physical target report stays FAIL while integrity/replay pass. This
extends a current research mode, leaving twelve entries and the locked A catalog
unchanged. Variable-flip/finite-RF/window physics, calibrated maps/trajectory,
noise/whitening/uncertainty, scalable field-aware inversion and earlier platform
gaps remain unfinished. The full goal stays active, B/C stay parked; no submission
import, push, PR, merge, router change or folder relocation occurred.

## Velocity-derived pressure and expanded platform audit (2026-11-01)

From `fdbad1c`, the [measured-flow study](measured-flow-coverage.md) retains raw
velocity CSV bytes and source/origin, fits only independent calibration velocity
rows and binds pressure coefficients conditionally on authored geometry/fluid/
frequency/clock. Known-sigma full covariance and acquisition holdout are checked
before nominal/eight-corner finite-RF causal DIR and coarse/fine observables.
An independent finite-volume momentum solve gives second-order pressure recovery.
The default synthetic input passes calibration and every numerical gate, while
both physical suppression/retention candidates fail and selection remains null.
Holdout, identifiability, budget and underresolved cases preserve their failures.

The new `/research/flow-study` route uses the shared scientific-record store.
Actual native CSV download/file-chooser re-import, record save/download/native
re-import and two full computational replays pass. CLI and independent-process
evidence are exact. Regression is **977 Python / 124 frontend**, TS/build pass.
This is a DIR signal workflow, not measured MR-image pressure reconstruction.
No clinical/scanner certification, push/PR/merge or B/C change occurred.

The expanded user objective additionally requires operation-level RF/gradient
orchestration, tissue relaxation/diffusion/exchange under intrinsic and external
influences (especially contrast agents), and bidirectional doctor-readable MR
Image / agent-readable Signal Vector control. Current sources were inspected:
SequenceIR/family lowering, reconstructed images and complete complex signals
exist, and diffusion/exchange are supported only in declared chains. The legacy physiology
concentration field has no verified concentration/relaxivity execution binding;
the common linked image/vector schema and safe typed edits are unfinished.
These are explicit remaining requirements, not inferred completion from the
current separate modules. The full expanded goal remains active.

## Static exposure and paired human/agent TSE control (2026-11-01)

From `d383d52`, the [contrast / image-signal continuation](contrast-image-signal-coverage.md)
adds explicit per-tissue static concentration and supplied relaxivity to common
kernel execution, plan states, observations and scoring. Baseline T1/T2 remain
unchanged; effective rates, units, B0/temperature/medium conditions, validity
range and origin are retained. Unitless legacy physiology concentration,
unsupported/extrapolated exposures, ambiguous measured-T2 baseline and currently
unwired radial/inverse exposure combinations fail explicitly.

The existing TSE runner now returns a complete complex image / acquisition-order
signal pair with spatial indices, normalized coordinates, sample times, tissue
bindings and a checked inverse-DFT link. `/research/contrast-study` uses the same
bounded typed RF/timing/order/concentration edits as an agent. Each child fully
recomputes its source/runtime-pinned parent, retains it immutably and recomputes
both views. Consistently forged parent target reports are caught by actual
computation. Three edit generations bound recursive replay. Physical gradient
waveform edits are deliberately unsupported in this ideal TSE adapter.

Independent CPMG/direct-DFT checks cover five concentrations and 2D/3D complete
complex data. Coupled PGSE diffusion and CEST-water parameter-binding checks also
pass without changing their authored ADC/exchange rates. Actual browser controls,
standalone vector download/verification, full native parent/child export/import,
shared-library replay and a fresh CLI process pass. A Node request reproduces
the exact browser records and the same complete pair as Python. Historical raw
metadata hashes retain their numeric-token distinctions; neither old identities
nor physical data are relabelled. Image target failure is retained.

Regression is **1026 Python / 132 frontend** (18 files), TS/build pass. This is
progress on explicit extrinsic state and bidirectional reading/control for one
declared adapter. Dynamic biology, measured relaxivity/uncertainty, general
operation-level RF/gradient orchestration, broader modality adapters and actual
physician/LLM usability remain incomplete. The expanded platform goal stays
active. No manuscript import, push/PR/merge, B/C promotion or router change occurred.
