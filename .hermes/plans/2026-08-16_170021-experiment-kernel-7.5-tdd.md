# Task 7.5 Implementation Plan

> **For implementer:** Strict TDD. No production code without a failing test first. Lock: `.hermes/plans/2026-08-16_170021-experiment-kernel-7.5-lock.md`

**Goal:** Make execution use the capability-selected engine, stop mutating request graphs, and emit only requested `ReadoutSpec` products — before Wave F.

**Architecture:** Add `plan_experiment() -> ExecutionPlan`. `validate_experiment` / `run_experiment` consume the plan. HTTP resolves a deep copy. `build_result_graph` filters on `readout.products`.

**Tech Stack:** Python 3.11+ / Pydantic v2 / FastAPI / pytest. Repo venv: `/opt/data/workspace/MRQlab/.venv`

**Cwd:** `/opt/data/workspace/MRQlab`  
**Branch:** `feature/experiment-kernel-7.5` (already created from `origin/main` @ `1ee5218`)  
**Author:** Xiaolei `<zxl1412@gmail.com>`  
**Do not pop** the Wave F stash.

---

### Task 1: ExecutionPlan + plan_experiment selects the engine that run_experiment uses

**Objective:** TSE without `EngineRef.preferred` executes EPG because the plan used `preferred_engine` metadata + `select_representation`, not a second `or metadata` path.

**Files:**
- Test: `tests/experiment/test_execution_plan.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/kernel.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/__init__.py`

**Step 1: Write failing tests**

```python
# tests/experiment/test_execution_plan.py
from mrqlab_experiment import build_preset, plan_experiment, run_experiment, validate_experiment


def test_tse_plan_selects_epg_from_template_metadata_not_preferred_field():
    graph = build_preset("dark-blood-tse", {"te": 0.02, "tr": 0.1, "echoes": 2})
    assert graph.engine.preferred is None
    plan = plan_experiment(graph)
    assert plan.engine == "epg"
    assert plan.representation == "epg"
    assert plan.preferred == "epg"
    run = run_experiment(graph)
    assert run.plan.engine == "epg"
    assert run.sim_result.meta["engine"] == "epg"


def test_explicit_preferred_override_still_wins_when_capabilities_allow():
    graph = build_preset("dark-blood-tse", {"te": 0.02, "tr": 0.1, "echoes": 2})
    graph.engine.preferred = "bloch"
    plan = plan_experiment(graph)
    assert plan.engine == "bloch"
    assert run_experiment(graph).sim_result.meta["engine"] == "bloch"


def test_capability_mismatch_fails_closed_before_simulate():
    graph = build_preset("dark-blood-tse")
    graph.engine.required_capabilities = frozenset({"shaped_rf", "configuration_states"})
    report = validate_experiment(graph)
    assert report.valid is False
    assert report.errors[0].code in {"capability_mismatch", "unavailable_representation"}
```

**Step 2:** `.venv/bin/python -m pytest tests/experiment/test_execution_plan.py -v`  
Expected: FAIL import — `plan_experiment` not exported.

**Step 3: Minimal implementation**

- `ExecutionPlan` pydantic model (fields per lock).
- `plan_experiment(graph)`:
  - compile sequence
  - `required = graph.engine.required_capabilities | disturbance extra`
  - `preferred = graph.engine.preferred or sequence.metadata.get("preferred_engine")`
  - `selected = select_representation(required, preferred)`
  - `options = replace(EngineOptions(**graph.engine.options), max_work=min(..., graph.constraints.max_work))`
  - return plan; do not mutate `graph`
- `validate_experiment` uses `plan_experiment` (catch `CapabilityMismatch` / compile errors as today).
- `KernelRun` gains `plan: ExecutionPlan`.
- `run_experiment` uses `plan.engine` with `get_engine(plan.engine).simulate(...)`.
- Export `ExecutionPlan`, `plan_experiment`.

**Step 4:** same pytest → PASS. Then `tests/experiment/test_kernel.py tests/experiment/test_disturbances.py tests/experiment/test_capabilities.py` still PASS.

**Step 5:** commit `feat(experiment): execute capability-selected engine via ExecutionPlan`

---

### Task 2: API / kernel do not mutate the caller's graph

**Objective:** `/experiments/run` and `/simulate` resolve on a copy.

**Files:**
- Test: `tests/test_api.py`
- Modify: `services/api/mrqlab_api/main.py`

**Step 1: Write failing tests**

```python
def test_experiments_run_does_not_mutate_caller_graph():
    from mrqlab_experiment import build_preset
    from mrqlab_api.main import experiments_run

    graph = build_preset("spin-echo", {"te": 0.02, "tr": 0.1})
    original_max = graph.constraints.max_work
    original_options = dict(graph.engine.options)
    result = experiments_run(graph)
    assert result.schema_version == "1.0"
    assert graph.constraints.max_work == original_max
    assert graph.engine.options == original_options


def test_simulate_adapter_builds_a_new_graph_without_mutating_preset_factory():
    from mrqlab_experiment import build_preset
    from mrqlab_api.main import SimulateRequest, _graph_from_simulate

    before = build_preset("spin-echo")
    request = SimulateRequest(template={"template": "SE", "params": {"te": 0.02, "tr": 0.1}}, engine="bloch")
    built = _graph_from_simulate(request)
    after = build_preset("spin-echo")
    assert built.engine.preferred == "bloch"
    assert after.engine.preferred == before.engine.preferred
    assert after.sequence == before.sequence
```

**Step 2:** pytest those two → FAIL (in-place assignment).

**Step 3:** `resolved = graph.model_copy(deep=True)` in `experiments_run`. `_graph_from_simulate` uses `model_copy(update=...)` / constructor, never `graph.sequence =`.

**Step 4:** those tests + full `tests/test_api.py` PASS.

**Step 5:** commit `fix(api): resolve experiment graphs on copies`

---

### Task 3: ResultGraph emits only requested readout products

**Objective:** `ReadoutSpec.products` is the observation contract.

**Files:**
- Test: `tests/experiment/test_readout_spec.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/observations.py`
- Modify: `tests/experiment/test_observations.py` (keep default-products test)

**Step 1: Write failing tests**

```python
# tests/experiment/test_readout_spec.py
import pytest
from mrqlab_experiment import build_preset, run_experiment
from mrqlab_experiment.models import ReadoutSpec
from mrqlab_experiment.observations import build_result_graph


def test_result_graph_emits_only_requested_products_in_order():
    graph = build_preset("gradient-echo", {"te": 0.02, "tr": 0.1})
    graph.readout = ReadoutSpec(products=("image", "signal"))
    result = build_result_graph(run_experiment(graph))
    assert [item.id for item in result.observations] == ["image", "signal"]
    assert [item.kind for item in result.observations] == ["image", "signal"]
    image = result.observations[0]
    assert image.derived_from == ()


def test_unknown_readout_product_fails_closed():
    graph = build_preset("spin-echo", {"te": 0.02, "tr": 0.1})
    graph.readout = ReadoutSpec(products=("not_a_product",))
    with pytest.raises(ValueError, match="unknown"):
        build_result_graph(run_experiment(graph))


def test_empty_products_emit_no_observations():
    graph = build_preset("spin-echo", {"te": 0.02, "tr": 0.1})
    graph.readout = ReadoutSpec(products=())
    result = build_result_graph(run_experiment(graph))
    assert result.observations == ()
    assert result.edges == ()
```

**Step 2:** pytest → FAIL (always emits three).

**Step 3:** Filter generators by `products`. Compute signal internally for image if needed. `objective_score` only if requested and objective present. Provenance.representation from `run.plan.representation` if present, else `meta["engine"]`.

**Step 4:** `test_readout_spec.py` + `test_observations.py` + `tests/test_api.py` PASS.

**Step 5:** commit `feat(experiment): honor ReadoutSpec.products in ResultGraph`

---

### Task 4: Full suite + docs pointer

**Step 1:** `.venv/bin/python -m pytest tests/ -q` → all PASS.

**Step 2:** Add a short "Task 7.5" pointer in `docs/superpowers/plans/2026-08-15-experiment-kernel.md` immediately before `### Task 8 (PR F)` — one subsection, do not rewrite Waves A–E.

**Step 3:** commit `docs(experiment): insert Task 7.5 before Wave F`

Do **not** push unless asked. Do **not** open a PR. Do **not** touch `packages/physics/**` numerics or `apps/web/**`.
