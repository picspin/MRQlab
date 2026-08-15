# Physics Engines Microkernel — Final Consolidated Fix Report

Date: 2026-08-14

Branch: `feature/physics-microkernel`

Starting revision: `c7cd93e4b63a8a6e7e3cbbc2466bc2cbcf45ba60`

Commit subject: `fix(physics): harden microkernel boundaries`

## Scope and ruling

This is the single consolidated fix wave for all four Important and both Minor findings in `final-review-report.md`.

The binding ruling from the locked product spec was applied: the microkernel, not an entry-point implementation, owns scheduling, arithmetic work preflight/caps, ADC/NCO sampling, k-trajectory tracking, and common `SimResult` assembly. The Task 9 intermediate full-`SimulationEngine` entry-point seam was intentionally replaced before release. Entry points now publish `EnginePlugin` backend descriptors, and `get_engine(...)` still returns an object with the public four-argument `simulate(sequence, phantom, scanner, options) -> SimResult` call.

Legacy full-engine entry points fail with a migration-specific error instead of being trusted silently. `PDGAdapter` remains the separately instantiated optional provider seam and is not accepted as a registry plugin or added as a fourth built-in.

The library-level `EngineOptions.return_magnetization=True` default was preserved because direct library results explicitly expose magnetization. The HTTP boundary forces both snapshot options off because the current response omits magnetization and configurations.

## Design

### Arithmetic scheduler preflight and bounded materialization

- Added `SchedulePlan` and `preflight_schedule`.
- ADC gates are reduced to arithmetic windows and sample counts without expanding dwell samples.
- A lower-bound operator calculation rejects obviously excessive ADC requests before iterating sample times.
- An exact operator count is then computed with a streaming merge of bounded base-event times and ADC sample times; the engine enforces `operator_count × descriptor state_width` before calling `schedule` or the backend factory.
- Added explicit limits of 100,000 channel events and 250,000 ADC samples.
- Schedule materialization checks that its final operator count agrees with the arithmetic plan.
- Replaced `_value_at`'s repeated event-time list construction with cached immutable time/value tuples and bisection. No per-lookup list rebuilding remains.
- Gradient-area fallback now rejects non-finite intermediate area rather than leaking an arithmetic exception.

### Strict public numeric boundaries

- All public physics dataclass numeric inputs now reject non-real, boolean-as-number, NaN, and infinity values as appropriate.
- `epg_kmax` and `max_work` require strict integral, non-boolean values.
- Snapshot flags require strict booleans.
- `Event.time`, `Event.value`, and `SequenceIR.duration` use finite Pydantic floats and reject booleans.
- API dictionaries preserve raw values until the physics dataclasses validate them, so a raw JSON `NaN` cannot be normalized around the server cap.
- The API matrix field is a strict integer.

### Kernel-controlled plugins and result assembly

- Added the public frozen `EnginePlugin` descriptor with a state-width function, backend factory, optional metadata factory, snapshot target, description, and availability.
- Made `SimulationEngine` the kernel-owned façade used by built-ins and entry-point descriptors.
- Converted Bloch, EPG, and spectral engines into thin descriptor-backed façade subclasses.
- Added a non-allocating spectral state-width validator so the cap precedes expanded pool/spin state allocation.
- Moved NCO demodulation from built-in backends to `run_backend`; state backends expose raw transverse signal through `observe()` and never receive `AdcSample` through `apply`.
- Centralized signal, scaled k-trajectory, snapshot field, common metadata, convention metadata, work metadata, and timing assembly.
- Registry loading accepts `EnginePlugin` instances or no-argument descriptor subclasses, preserves case-insensitive lookup and built-in shadow protection, and rejects old full-engine instances/subclasses clearly.

### Sequence and HTTP validation

- `SequenceIR` rejects every channel event after its declared duration.
- Template echo counts are strict positive, non-boolean integers.
- The final ADC gate/echo train must fit inside TR for GRE, SE, and TSE.
- The TR-fit check compares before multiplication, so astronomically large integers produce a 422 instead of `OverflowError`/500.
- `epg_dk_events` must be a list/tuple of mappings with finite in-range time and three finite integral, non-boolean `dk` components; every malformed shape raises `ValueError` and therefore HTTP 422.
- API snapshot flags are forced false until those arrays are part of the response contract.

### Independent numerical gates and status documentation

- Added a three-engine analytic complex golden using nonzero RF phase, off-resonance, NCO frequency, and NCO phase, plus the locked convention string as a literal.
- Added a three-echo CPMG/EPG T2-envelope golden.
- Added a fat/water quarter-beat complex-phase golden.
- Added a nonzero-position gradient golden that independently locks spatial phase, scanner gradient scaling, and k-trajectory.
- Removed the unused `gradient_hz_per_m` helper; the behavior is locked at the real backend boundary instead.
- Updated README, ROADMAP, PHYSICS, and ARCHITECTURE to state that Physics v1 is delivered and to document the descriptor seam and safety behavior.

## Files changed

Production and public API:

- `packages/physics/mrqlab_physics/base.py`
- `packages/physics/mrqlab_physics/registry.py`
- `packages/physics/mrqlab_physics/__init__.py`
- `packages/physics/mrqlab_physics/models.py`
- `packages/physics/mrqlab_physics/kernel/scheduler.py`
- `packages/physics/mrqlab_physics/kernel/caps.py`
- `packages/physics/mrqlab_physics/kernel/runner.py`
- `packages/physics/mrqlab_physics/kernel/units.py`
- `packages/physics/mrqlab_physics/backends/protocol.py`
- `packages/physics/mrqlab_physics/backends/bloch.py`
- `packages/physics/mrqlab_physics/backends/epg.py`
- `packages/physics/mrqlab_physics/backends/spectral.py`
- `packages/physics/mrqlab_physics/engines/bloch_engine.py`
- `packages/physics/mrqlab_physics/engines/epg_engine.py`
- `packages/physics/mrqlab_physics/engines/spectral_engine.py`
- `packages/sequence-ir/mrqlab_sequence/models.py`
- `packages/sequence-ir/mrqlab_sequence/templates.py`
- `services/api/mrqlab_api/main.py`

Tests:

- `tests/physics/test_models_caps.py`
- `tests/physics/test_scheduler_runner.py`
- `tests/physics/test_registry_plugins.py`
- `tests/physics/test_template_metadata.py`
- `tests/physics/test_cross_engine.py`
- `tests/physics/test_bloch_engine.py`
- `tests/physics/test_epg_engine.py`
- `tests/physics/test_spectral_engine.py`
- `tests/test_api.py`

Documentation:

- `README.md`
- `docs/ROADMAP.md`
- `docs/PHYSICS.md`
- `docs/ARCHITECTURE.md`
- this report

Unrelated user-owned `.hermes/`, `.venv-task7/`, and `docs/research/` were not modified or staged.

## TDD evidence — RED

### 1. Scheduler materialization and explicit limits

Command:

```bash
.venv/bin/python -m pytest -q tests/physics/test_scheduler_runner.py::test_arithmetic_preflight_rejects_work_before_scheduler_materialization tests/physics/test_scheduler_runner.py::test_scheduler_enforces_explicit_event_limit tests/physics/test_scheduler_runner.py::test_scheduler_enforces_explicit_adc_sample_limit
```

Output: `3 failed in 0.20s` (exit 1).

Reasons:

- the engine called `schedule` before its cap and hit the test sentinel;
- no event-limit check existed;
- no ADC-sample-limit check existed.

### 2. Finite and strict physics/API inputs

Command:

```bash
.venv/bin/python -m pytest -q tests/physics/test_models_caps.py::test_public_physics_models_reject_non_finite_numbers tests/physics/test_models_caps.py::test_engine_options_reject_non_strict_integer_and_boolean_fields tests/test_api.py::test_raw_json_nan_cannot_bypass_server_work_cap tests/test_api.py::test_http_options_reject_non_strict_integer_and_boolean_fields
```

Output: `18 failed, 1 warning in 0.28s` (exit 1).

Reasons:

- six non-finite physical model cases constructed successfully;
- fractional/bool integer fields and numeric boolean flags were accepted;
- raw JSON `NaN` with server `MAX_WORK=1` returned HTTP 200;
- several non-strict HTTP option payloads returned 200, and bool `max_work` reached the work comparison rather than strict validation.

### 3. Plugin ownership contract

Command:

```bash
.venv/bin/python -m pytest -q tests/physics/test_registry_plugins.py
```

Output: `4 failed, 1 passed in 0.11s` (exit 1).

Reasons:

- `EnginePlugin` did not exist;
- the registry required a full `SimulationEngine` instead of a descriptor;
- no kernel façade existed for descriptor caps/ADC/result assembly;
- a legacy full-engine entry point was accepted instead of rejected.

### 4. Duration, echo, and malformed shift boundaries

Command:

```bash
.venv/bin/python -m pytest -q tests/physics/test_template_metadata.py::test_sequence_rejects_channel_events_after_declared_duration tests/physics/test_template_metadata.py::test_templates_require_strict_positive_integer_echo_count tests/physics/test_template_metadata.py::test_template_echo_train_must_fit_within_tr tests/physics/test_scheduler_runner.py::test_scheduler_rejects_malformed_metadata_shifts_as_validation_errors tests/test_api.py::test_http_rejects_post_duration_sequence_events tests/test_api.py::test_http_template_endpoints_reject_invalid_echo_counts tests/test_api.py::test_http_template_endpoints_reject_echo_tr_overflow tests/test_api.py::test_http_malformed_epg_shift_metadata_is_a_validation_error
```

Output: `19 failed, 2 passed, 1 warning in 0.45s` (exit 1).

Reasons:

- post-duration channel events returned HTTP 200;
- zero, negative, fractional, and boolean echo counts were accepted/truncated;
- echo trains extending beyond TR returned HTTP 200 on affected paths;
- missing metadata keys leaked `KeyError`/`TypeError`, and malformed HTTP metadata raised a server exception rather than returning 422.

### 5. API snapshot suppression

Command:

```bash
.venv/bin/python -m pytest -q tests/test_api.py::test_api_does_not_collect_snapshots_that_it_does_not_return
```

Output: `1 failed, 1 warning in 0.39s` (exit 1).

Reason: the API honored `return_magnetization=True` even though it omitted the array, and the backend snapshot sentinel was called.

### 6. Kernel-owned ADC/NCO sampling

Command:

```bash
.venv/bin/python -m pytest -q tests/physics/test_scheduler_runner.py::test_runner_samples_after_prior_intervals_and_tracks_k tests/physics/test_scheduler_runner.py::test_scheduler_converts_rf_and_nco_phases_and_samples_before_new_interval
```

Output: `2 failed in 0.10s` (exit 1).

Reason: `run_backend` passed `AdcSample` into the backend and called `observe(op)`; the new raw-signal backend contract correctly failed with `TypeError` before implementation.

### 7. Extremely large integral echo count found during self-review

Command:

```bash
.venv/bin/python -m pytest -q tests/physics/test_template_metadata.py::test_template_echo_train_must_fit_within_tr tests/test_api.py::test_http_template_endpoints_reject_echo_tr_overflow
```

Output: `3 failed, 3 passed, 1 warning in 0.67s` (exit 1).

Reason: `te * echoes` raised `OverflowError` for `10**400`, leaking a 500 from both template HTTP paths. The fix compares the integer echo count with the available-TR ratio before multiplication.

### Numerical coverage characterization

The four requested numerical gates target formulas that the final review had already found correct, so correct tests were expected to pass before production edits. The first run exposed an incorrect test fixture string (a shortened convention phrase), not a product defect: numerical arrays passed but the literal assertion failed. The fixture was corrected to the locked convention without changing production. The valid baseline command then produced `4 passed in 0.09s`. This is recorded as characterization evidence rather than misrepresented as RED.

## Verification evidence — GREEN

### Focused groups

- Scheduler/preflight command above: `3 passed in 0.14s`.
- Finite/strict validation command above: `18 passed, 1 external warning in 0.29s`.
- Plugin file: `5 passed in 0.14s`.
- Final duration/echo/metadata command above (including huge integral counts): `24 passed, 1 external warning in 0.30s`.
- Snapshot plus runner/ADC command: `3 passed, 1 external warning in 0.29s`.
- Four independent numerical goldens: `4 passed in 0.14s`.
- Dedicated huge-echo rerun: `6 passed, 1 external warning in 0.20s`.

The warning in every API-containing run is the pre-existing external `StarletteDeprecationWarning` from FastAPI's `TestClient` import.

### Full suite

Command:

```bash
.venv/bin/python -m pytest -q
```

Output:

```text
........................................................................ [ 72%]
...........................                                              [100%]
99 passed, 1 warning in 0.38s
```

Exit: 0. The sole warning is the external Starlette/httpx compatibility deprecation described above.

### `/engines` smoke

Command:

```bash
.venv/bin/python -c 'from fastapi.testclient import TestClient; from mrqlab_api.main import app; response=TestClient(app).get("/engines"); payload=response.json(); assert response.status_code == 200; assert {item["name"] for item in payload["engines"]} == {"bloch", "epg", "spectral"}; assert all(item["available"] for item in payload["engines"]); print(payload)'
```

Exit: 0. Output listed `bloch`, `epg`, and `spectral`, all available and sourced as built-ins, with default `bloch`.

### Compilation and static checks

```bash
.venv/bin/python -m compileall -q packages/sequence-ir packages/physics packages/recon services/api
```

Exit: 0, no output.

```bash
rg -n "BlochEngine|EPGEngine|SpectralEngine" packages/recon apps/web
```

Exit: 1, expected no matches. Recon/web have no concrete-engine coupling.

```bash
rg -n "torch|MRzero|pulseq_zero|pypulseq|sigpy|scipy" packages/physics pyproject.toml
```

Exit: 1, expected no matches. NumPy remains the only numerical default and no heavy optional import/probe was added.

```bash
rg -n "\[event\.time for event in events\]|times = \[event\.time" packages/physics/mrqlab_physics
```

Exit: 1, expected no matches. The quadratic `_value_at` list-rebuild pattern is absent.

```bash
git diff --check
```

Exit: 0, no output.

## Self-review

### Locked-spec ownership

- All three built-ins now traverse one common façade path: state width → arithmetic preflight/cap → schedule → backend run/core ADC demodulation → common `SimResult`.
- Entry-point code cannot replace `simulate`; it supplies only descriptor callbacks and state behavior.
- The backend factory is never called before the exact work cap.
- Core metadata wins over plugin metadata for reserved fields because common keys are applied after descriptor metadata.
- The four-argument public call and built-in classes remain available.

### Safety and validation

- Arithmetic lower-bound rejection occurs before ADC sample enumeration or schedule materialization.
- Accepted enumeration is bounded by both the hard sample limit and the request work limit.
- Event lookup caches channel arrays once per preflight rather than allocating a time list in every scheduler loop.
- Sequence channel times, template echoes/TR, raw metadata, and all physics input numbers now fail as controlled validation errors.
- API snapshot suppression is enforced even if a request asks for a snapshot the response does not expose.

### Numerical independence

- Expected RF/NCO phase is derived analytically in the test rather than with production helpers.
- The convention string is duplicated as a locked literal.
- The multi-echo expected envelope is `exp(-TE_n/T2)` over three distinct echoes.
- The quarter-beat spectral expected value is the literal `-0.5 - 0.5j`.
- The gradient expected phase and `[1.5, 0, 0]` trajectory are hand-derived from position, teaching gradient, duration, and scanner scale.

### Mutation check

- Moving the cap after `schedule` trips the materialization sentinel.
- Removing either hard schedule limit trips its focused test.
- Allowing NaN/bool/fractional public values trips model and HTTP tests.
- Restoring full-engine plugins, backend-owned ADC/NCO, or per-engine result assembly trips registry/kernel tests.
- Removing duration/echo/metadata validation trips direct and HTTP tests, including the 500 regressions.
- Restoring API snapshot collection trips the backend snapshot sentinel.
- RF/NCO sign, later-echo decay, spectral phase, spatial gradient scaling, or k-trajectory drift trips an independent numerical golden.

### Dependency and worktree hygiene

- Physics still depends inward on sequence IR; API consumes registry/models; recon and web do not import concrete backends.
- No torch, MRzero, pulseq-zero, PyPulseq, SigPy, or SciPy default dependency/import was introduced.
- User-owned `.hermes/`, `.venv-task7/`, and `docs/research/` remain untouched and unstaged.

## Residual concerns

- FastAPI's current TestClient emits one external Starlette/httpx deprecation warning; it is unchanged and does not affect behavior.
- The scheduler event cap runs after the HTTP framework has parsed the JSON body. It prevents scheduler amplification, but deployment ingress should still impose a request-body size limit for transport-level protection.
- An entry-point descriptor's `state_width` callback is contractually required to remain allocation-free. Core can guarantee that the backend factory is delayed until after the cap, but it cannot prevent malicious work inside the estimator callback itself.
- The descriptor seam intentionally breaks compatibility with the unreleased Task 9 full-engine entry-point shape; the registry error and updated documentation provide the migration path.
