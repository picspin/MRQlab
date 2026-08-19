# Wave G Dual-Axis Review

**Verdict: PASS-WITH-NITS**

Reviewed `eac1800...` working tree on `feature/experiment-kernel-g` (Task 10 / PR G).

## Findings

No P0 findings.

### Nit: ResultGraph builders honor requested product order

**Location:** `packages/mrqlab_experiment/mrqlab_experiment/observations.py`

Task 10 snippet appends extras after a fixed base triple. 7.5 already locked “emit exactly `ReadoutSpec.products`, in that order.” This slice adds `configurations` / `echo_train` / `sar` builders into that ordered loop instead of always emitting the base three. Matches the later, stricter contract.

### Nit: `/simulate` still strips snapshots; `/experiments/run` is gated

**Location:** `services/api/mrqlab_api/main.py`

Legacy `/simulate` still forces snapshot flags off (existing API test). Canonical `/experiments/run` now honors `return_configurations` / `return_magnetization` only when the matching product is requested. Teaching chain can collect EPG states without reopening snapshot collection on the compat endpoint.

### Nit: Signal Lab mutates the fetched preset graph locally

**Location:** `apps/web/app/signal-lab/page.tsx`

Matches the plan snippet. Mutation is local JSON, not the kernel request-graph alias bug from 7.5.

## Axis A: Lock / Spec / TDD Fidelity

- `refocusing_flip_angle` is a validated template parameter (`0 < angle <= 180`) and is written into SequenceIR metadata.
- SE/TSE refocusing RF uses that parameter; default remains 180°.
- Requested products `configurations`, `echo_train`, `sar` materialize with the specified teaching formulas.
- `magnetization` / `configurations` still fail closed when the matching snapshot was not collected.
- `echo_train` as an **objective term** remains reserved (Wave G does not implement that scorer).
- Signal Lab shows EPG states → echo train → k-space weighting → tissue contrast → SAR.
- RED observed: thesis failed on reserved/disabled `configurations`; UI failed on missing `TseSignalLab`.

## Axis B: Quality / Regressions

- `test_readout_spec` updated so `echo_train` / `sar` emit, and snapshot fail-closed is data-driven rather than unconditional.
- Physics backends untouched.
- Full gates green.

## Verification

- `.venv/bin/python -m pytest tests/ -q` → 139 passed, 1 warning
- `cd apps/web && npm test` → 4 passed
- `npm run typecheck` → pass
- `npm run build` → pass (`/`, `/editor`, `/signal-lab`)
