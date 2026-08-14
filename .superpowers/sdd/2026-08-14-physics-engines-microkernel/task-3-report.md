# Task 3 Report: Shared Operator Contracts and Golden Math

## RED evidence

No earlier import-missing RED evidence was present in the available artifacts or history.
The observed continuation RED was:

```text
python3.11 -m pytest tests/physics/test_ops_golden.py -q
...F                                                                     [100%]
FAILED tests/physics/test_ops_golden.py::test_relaxation_half_life_and_nco_demodulation
assert 0.6065306597126334 == 0.7071067811865476 +/- 7.1e-07
1 failed, 3 passed in 0.13s
```

The fixture used inconsistent arguments for the required exponential relation.
Per the binding ruling it was changed only to
`relaxation_factors(np.log(2), 2.0, 1.0)`, retaining the expected values.

## GREEN verification

```text
python3.11 -m pytest tests/physics/test_ops_golden.py tests/physics/test_models_caps.py -q
........                                                                 [100%]
8 passed in 0.10s
```

## Files changed

- `packages/physics/mrqlab_physics/ops/types.py`
- `packages/physics/mrqlab_physics/ops/rf.py`
- `packages/physics/mrqlab_physics/ops/relax.py`
- `packages/physics/mrqlab_physics/ops/sample.py`
- `packages/physics/mrqlab_physics/ops/__init__.py`
- `tests/physics/test_ops_golden.py`
- `.superpowers/sdd/2026-08-14-physics-engines-microkernel/task-3-report.md`

## Self-review

- Confirmed all five immutable, slotted contracts and the `Operator` union match the stable contract.
- Confirmed the EPG RF matrix, Cartesian Rodrigues rotation convention, relaxation validation/exponentials, and NCO demodulation match the task brief.
- Scoped staging and commit to Task 3 files and this report; unrelated `.hermes/` and `docs/research/` work is excluded.
- `git diff --check` is run as final commit verification.

## Concerns

None. Terminal startup prints a benign `TERM=su` fallback notice before pytest output; tests still exit successfully.
