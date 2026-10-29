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
| Clinical question → pulse/design → physical simulation | Five backend chains carry explicit research questions, design/timing parameters, physical provenance and scientific boundaries | Implemented for these declared teaching chains; universal experiment schema and calibrated clinical priors remain incomplete |
| Lab experiment → clinical target | Editable two-class phantoms, tissues, spin/pool controls and explicit synthetic/control objectives | Measured lab data ingestion, calibration, uncertainty and robust clinical target translation remain incomplete |
| Parameter optimization | Each chain executes an explicit candidate grid and preserves every point; API search distinguishes execution feasibility from target pass | No general constrained/multi-objective solver or uncertainty-aware optimization over lab data |
| High-precision non-Cartesian inverse | Unscaled complex 2D/3D recovery, independent adjoint/acquisition checks, budget and data residual diagnostics | FINUFFT matrix-free plans now available; radial conditioning, noise/coil/trajectory calibration and non-Cartesian echo-weighted TSE remain incomplete |
| Real flow / slice / gating | Actual positions move through finite RF/Gz; independent constant-velocity phase and ODE convergence; state persists between cycles | Prescribed 1D constant velocity, not pulsatile/3D hemodynamics or prospective gating; full motion-encoded images remain incomplete |
| CEST MT/NOE | Concurrent liquid/semisolid generator, conditional exchange-off controls, CW/pulsed tests, named effective rNOE approximation | Microscopic NOE cross relaxation, near-resonance generalized semisolid model and spatial joint imaging remain incomplete |
| More complete MRS | 1–3 spin density matrices, finite RF/isotropic J, analytic doublet check, full complex basis fitting, J-mismatch failure | Validated molecular library, full quantum relaxation, spatially converged PRESS localization and clinical concentration calibration remain incomplete |
| Frontend entry | `/research`, bounded `/research/run` and `/research/search`, actual backend plots/tables, failure states, strict input and source checks | Native export/download/file-picker roundtrip remains unverified; Blob content/import and API replay have automated coverage |
| All verifiable and replayable | Source/result/search hashes, full run and candidate inputs, Python/NumPy versions, exact backend replay tests, source-change rejection | Durable multi-stage project model and comprehensive environment lock/replay tooling remain incomplete |
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
