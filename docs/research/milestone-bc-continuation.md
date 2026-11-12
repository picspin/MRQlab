# Milestone B/C continuation

On 2026-11-11 the user authorized work on milestones B and C. This document
records bounded research changes from the code tree of GitHub main `4d24eab`
(`5b8a5c6` has the same tree). Neither milestone is complete, scanner-ready,
clinically validated, nor licensed for deployment by this change.

## Same-channel sequence collisions

`lower_sequence` now rejects overlapping RF, ADC, or same-axis gradient
intervals from separate blocks after start-time raster quantization. Intervals
are half-open; adjacent same-channel events and concurrent different gradient
axes remain allowed. The ADC/RF guard remains independent. Tests cover all
three channel types and a valid parallel/adjacent example.

Gradient waveforms are treated as sample-and-hold, with implicit zero when a
channel has no waveform. Discrete nominal slew is checked between successive
samples, at adjacent block joins, and entering/leaving idle periods. The
previous sample's raster is the interval at an adjacent join; entering a
waveform after a shorter idle gap uses that shorter interval, including the
idle interval from sequence start to an initially delayed waveform. A waveform
that starts at t=0 is compared with a zero sample one waveform raster earlier.
Decimal timing is used to avoid rejecting exactly adjacent intervals due to floating-point sums;
RF/ADC guard boundaries use the same timing convention. Sequence models reject
non-finite timings, offsets, and samples. The declared profile's threshold,
including an exactly equal limit, is tested; an over-limit boundary fails.

These checks do not calculate continuous gradient ramps or physical slew, nor
do they cover RF power and SAR, simultaneous RF/gradient physics,
scanner-specific export, safety review, or scanner testing. In particular,
sample-and-hold transitions are idealized; the finite-difference quantity is a
nominal check and is not proof of actual scanner waveform behavior.
`HARDWARE_REVIEW_REQUIRED` is not a scanner authorization.

## Queued job cancellation

Local CPU and GPU workers atomically claim queued jobs against cancellation.
If cancellation wins, the worker does not run; if the worker wins, the existing
not-preemptible error is returned. A concurrent test checks both valid event
sequences. This does not implement running-job preemption, persistent job
storage, GPU physics, a production license service, or multi-process coordination.

## Existing research evidence carried forward

The original Claude handoff's 32×32 exact-DFT tests and measurements were
adapted to the continuing line and documented in
[handoff integration](handoff-noncartesian-integration.md). The original strict
image target remains in force; CGLS is the exact-DFT reference and the later
FINUFFT path is separate. The 3D agent inference tests also now assert actual
center-plane values, DC amplitudes and decay residual, following `c35da9d`.
These use authored synthetic tissue labels; they do not establish clinical or
physician/LLM usability.

## Verification

At the preceding `bc2ed37` anchor, Python `tests/` passed **1152 tests**, with one
Starlette/httpx deprecation warning. The full run explicitly used
`PYTHONPATH=packages/sequence-ir:packages/physics:packages/recon:packages/mrqlab_experiment:services/api:services/local_agent`
so child CLI processes, as well as pytest itself, load this worktree. Without
that setting, two subprocess tests loaded the shared venv's older editable
checkout and failed record verification; the bound-path rerun passed both and
the full suite. Frontend Vitest passed **202 tests**, TypeScript `--noEmit
--incremental false` passed, and `npm run build` passed. These are local results,
not CI or scanner validation.

After adding gradient boundary checks and finite-value validation, the same
source-bound Python command passed **1162 tests**, with the same warning.
The focused sequence/lowering/export/protocol regression set passed **41 tests**.
No frontend files changed in this continuation; frontend tests and the build
were last run at the preceding anchor rather than repeated for these backend
changes.
