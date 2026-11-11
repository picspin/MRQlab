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

This is a conflict check, not complete hardware or waveform validation. In
particular, cross-block gradient boundary transitions and slew, RF power and
SAR, simultaneous RF/gradient physics, scanner-specific export, safety review,
and scanner testing require separate work. `HARDWARE_REVIEW_REQUIRED` is not a
scanner authorization.

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

On the aligned worktree, Python `tests/` passed **1152 tests**, with one
Starlette/httpx deprecation warning. The full run explicitly used
`PYTHONPATH=packages/sequence-ir:packages/physics:packages/recon:packages/mrqlab_experiment:services/api:services/local_agent`
so child CLI processes, as well as pytest itself, load this worktree. Without
that setting, two subprocess tests loaded the shared venv's older editable
checkout and failed record verification; the bound-path rerun passed both and
the full suite. Frontend Vitest passed **202 tests**, TypeScript `--noEmit
--incremental false` passed, and `npm run build` passed. These are local results,
not CI or scanner validation.
