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
