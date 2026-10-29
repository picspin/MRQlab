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
| Clinical question → pulse/design → physical simulation | Eight backend chains carry explicit research questions, design/timing parameters, physical provenance and scientific boundaries | Implemented for these declared teaching chains; universal experiment schema and calibrated clinical priors remain incomplete |
| Lab experiment → clinical target | Measured-input TSE pilot includes raw CSV/units, calibration, independent holdout and conditional uncertainty; other chains expose authored controls | Cross-modality measured calibration and robust clinical target translation remain incomplete |
| Parameter optimization | Each chain executes an explicit candidate grid and preserves every point; API search distinguishes execution feasibility from target pass | Measured TSE has bounded uncertainty-corner target checks; general constrained/multi-objective and cross-modality optimization remain incomplete |
| High-precision non-Cartesian inverse | Unscaled complex 2D/3D recovery, independent adjoint/acquisition checks, budget and data residual diagnostics | FINUFFT matrix-free plans now available; radial conditioning, noise/coil/trajectory calibration and non-Cartesian echo-weighted TSE remain incomplete |
| Real flow / slice / gating | Pressure-driven Womersley shear/backflow, volume-weighted moving spins, finite RF/Gz and causal interruption with independent fluid/Bloch references | Straight rigid pipe and fixed radius only; measured calibration, general 3D/compliant flow and motion-encoded images remain incomplete |
| CEST MT/NOE | Effective-pool baseline plus distance/tau-derived signed Solomon pair→bridge→water relay, conditional controls and independent population/ODE checks | Full molecular multi-spin/Redfield relaxation, near-resonance generalized semisolid model and spatial joint imaging remain incomplete |
| More complete MRS | 1–3 spin density matrices, finite RF/isotropic J, coherence-selected 3D PRESS volume fitting with separate RF/grid/FOV checks, center/J mismatch failures | Validated molecular library, full quantum relaxation, realistic field maps, measured spectra and clinical concentration calibration remain incomplete |
| Frontend entry | `/research`, bounded `/research/run` and `/research/search`, actual backend plots/tables, failure states, strict input and source checks | Eight research entries include actual causal scheduling/completion table; native JSON download/re-import remains open, with verified CLI local delivery |
| All verifiable and replayable | Source/result/search hashes, full run and candidate inputs, Python/NumPy versions, exact backend replay tests, source-change rejection | Portable measured-TSE stage records and locked-environment CLI evidence exist; universal multi-study persistence and cross-platform replay remain incomplete |
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

1. Finish native export/import browser verification or provide a verified
   local-file delivery path supported by the in-app browser.
2. Unify the research experiment/measurement/result conventions into a scientific
   record that can ingest lab measurements with units, uncertainty and provenance;
   persist and replay the design→optimization→validation stages.
3. Continue fidelity work in the original priority order. Report model validity,
   conditioning, independent references and failed targets without gain fitting,
   hidden calibration or a claim of clinical/scanner certification.

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
