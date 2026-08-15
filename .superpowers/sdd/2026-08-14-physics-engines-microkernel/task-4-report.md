# Task 4 Report: IR Scheduler and Backend-Neutral Runner

## RED evidence

```text
python3.11 -m pytest tests/physics/test_scheduler_runner.py -q
...
E   ModuleNotFoundError: No module named 'mrqlab_physics.kernel.runner'
...
1 error in 0.23s
```

The prescribed test failed during import because the scheduler and runner modules did not yet exist.

## GREEN verification

```text
python3.11 -m pytest tests/physics/test_scheduler_runner.py tests/physics/test_ops_golden.py tests/physics/test_models_caps.py -q
..........                                                               [100%]
10 passed in 0.09s
```

`git diff --check` also completed without output or errors.

## Files changed

- `packages/physics/mrqlab_physics/kernel/scheduler.py`
- `packages/physics/mrqlab_physics/kernel/runner.py`
- `packages/physics/mrqlab_physics/backends/protocol.py`
- `tests/physics/test_scheduler_runner.py`
- `.superpowers/sdd/2026-08-14-physics-engines-microkernel/task-4-report.md`

## Self-review

- Deterministically merges sequence-channel events, ADC dwell samples, and metadata shift times.
- Converts RF and NCO phases from degrees to radians and emits metadata shifts before ADC sampling at a shared timestamp.
- Uses gradient-area shifts only when explicit metadata shifts are absent.
- Applies every operator through the backend-neutral protocol, samples after preceding intervals, and records k-space and optional per-operator snapshots.
- Staging is limited to Task 4 files and this report; unrelated `.hermes/` and `docs/research/` edits are excluded.

## Concerns

None. The terminal prints a benign `TERM=su` fallback notice before pytest output; pytest completed successfully.

## Fix Round 1

### Tests changed

- Added fractional metadata `dk` rejection coverage.
- Added same-timestamp gradient fallback ordering coverage.
- Added RF/NCO degree-to-radian conversion and ADC-before-new-interval coverage with `RecordingBackend`.
- Added metadata-shift precedence over gradient-area fallback coverage.

### RED evidence

```text
python3.11 -m pytest tests/physics/test_scheduler_runner.py -q
..FF                                                                     [100%]
FAILED tests/physics/test_scheduler_runner.py::test_scheduler_rejects_fractional_metadata_shift_components
E       Failed: DID NOT RAISE <class 'ValueError'>
FAILED tests/physics/test_scheduler_runner.py::test_scheduler_places_gradient_fallback_after_rf_at_shared_timestamp
E       AssertionError: ... Shift ... != ... RfOp ...
2 failed, 2 passed in 0.14s
```

### GREEN verification

```text
python3.11 -m pytest tests/physics/test_scheduler_runner.py tests/physics/test_ops_golden.py tests/physics/test_models_caps.py -q
..............                                                           [100%]
14 passed in 0.09s
```

`git diff --check` completed without output or errors.

### Files changed

- `packages/physics/mrqlab_physics/kernel/scheduler.py`
- `tests/physics/test_scheduler_runner.py`
- `.superpowers/sdd/2026-08-14-physics-engines-microkernel/task-4-report.md`

### Self-review

- Metadata `dk` values must be finite, numeric, non-boolean, and mathematically integral before conversion to `int`.
- Gradient-area shifts are computed before emission and inserted at their target knot, maintaining RF → Shift → ADC → interval ordering at every timestamp.
- Explicit metadata shifts continue to suppress all gradient-area fallback shifts.
- ADC samples retain the left-inclusive, right-exclusive gate boundary and execute before the next interval at the shared timestamp.
