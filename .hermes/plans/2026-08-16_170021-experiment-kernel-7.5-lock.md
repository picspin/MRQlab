# Task 7.5 Lock — Harden workbench physics backend (before Wave F)

**Status:** Locked for implementation  
**Date:** 2026-08-16  
**Branch:** `feature/experiment-kernel-7.5` from `origin/main` @ `1ee5218`  
**Inserts:** after Task 7 (PR E, merged) and **before** Task 8 / Wave F  
**Source:** `notes/research/mrqlab-physics/2026-08-16-clarification-workbench-hardening.md` §§25–29  
**Does not implement:** Wave F frontend, graph executable-ization, TSE vertical slice UI, hybrid engines, snapshot collection for magnetization/configurations

---

## Product / architecture lock (unchanged)

```text
Experiment = Sequence + Sample + Scanner + Physics Engine + Objective + Readout
```

Five contracts remain: `ExperimentGraph`, `PhysicsOperator`, `StateRepresentation`, `ObjectiveFunction`, `Observation`.

Backend topology stays: `mrqlab_experiment` kernel + physics engine plugins + SequenceIR + recon. **Do not** retopologize packages. Engine plugin still only owns representation/backend; kernel owns execution.

Clarification backend line for this task:

```text
ExecutionPlan → capability-selected engine → requested Observation → immutable ResultGraph
```

Frontend Feature-Sliced + Projection work is **out of 7.5**. 7.5 only makes the backend contract honest so later lenses can consume it.

---

## P0 scope (only these three)

### P0-A — `run_experiment()` must execute the capability-selected engine

**Bug:** `validate_experiment()` calls `select_representation(...)`, but `run_experiment()` still does:

```python
engine_name = graph.engine.preferred or str(sequence.metadata.get("preferred_engine", "bloch"))
get_engine(engine_name).simulate(...)
```

Resolver result never enters execution.

**Lock:**

1. Introduce `plan_experiment(graph) -> ExecutionPlan`.
2. `validate_experiment` and `run_experiment` both go through `plan_experiment`.
3. `run_experiment` calls `get_engine(plan.engine).simulate(...)`.
4. `KernelRun` carries the `ExecutionPlan` so API / future UI can consume it.

`ExecutionPlan` (new, in `kernel.py` or `models.py`):

```python
class ExecutionPlan(BaseModel):
    experiment_id: str
    representation: str          # StateRepresentation.name
    engine: str                  # get_engine() name; v0 == representation for bloch/epg/spectral
    required_capabilities: tuple[str, ...]
    preferred: str | None
    options: dict[str, Any]
    reasons: tuple[str, ...]     # disturbance explanations + "preferred|metadata|capability"
```

**Selection algorithm (do not change resolver semantics):**

```text
sequence = compile_sequence(graph)
required = graph.engine.required_capabilities | disturbance_requirements(...).caps
preferred = graph.engine.preferred or sequence.metadata.get("preferred_engine")
selected = select_representation(required, preferred)
engine = selected.name
```

Passing `preferred=None` into `select_representation` would pick **bloch** first (dict order) and break TSE → EPG. Always feed template `preferred_engine` as preferred when `EngineRef.preferred` is unset.

If preferred is set but cannot satisfy `required`, keep today's fail-closed `CapabilityMismatch` / `unavailable_representation`. Do **not** silently fall over to another available engine.

v0 engine name == representation name (`bloch` / `epg` / `spectral`). No new mapping table.

### P0-B — API / kernel must not mutate the request graph

**Bug:** `/experiments/run` writes `graph.constraints.max_work` and `graph.engine.options`. `/simulate` adapter (`_graph_from_simulate`) mutates preset fields in place.

This poisons A/B compare, undo, provenance, later optimization.

**Lock:**

1. Kernel functions treat `ExperimentGraph` as read-only. No attribute assignment on the input graph.
2. HTTP handlers resolve a **copy**: `graph.model_copy(deep=True)` then write caps/options on the copy only.
3. `_graph_from_simulate` must **build** a new graph (preset + overrides) via constructor / `model_copy(update=...)`, never `graph.sequence = ...`.
4. Work/option caps stay: `max_work = min(requested, MAX_WORK)`; API still forces `return_magnetization=False` and `return_configurations=False` on the **resolved copy**.
5. Do **not** freeze all Pydantic models in this task. Existing tests assign `graph.disturbances` / `graph.engine.required_capabilities`. Immutability here means **resolution/API**, not a repo-wide `frozen=True` sweep.

### P0-C — `build_result_graph` must honor `ReadoutSpec.products`

**Bug:** `ReadoutSpec.products` exists (default `("signal", "k_trajectory", "image")`) but `build_result_graph` always emits those three (+ `objective_score` if an objective is set).

**Lock:**

1. Emit **exactly** the products listed in `run.experiment.readout.products`, in that order.
2. Unknown product name → fail closed (`ValueError` / validate error `unknown_product`). Allowed v0 kinds = `ObservationKind`.
3. Internal precursors may be computed (image still FFTs signal) but **not** added to `ResultGraph.observations` unless requested.
4. `derived_from` only references ids that are actually emitted. If `image` is requested without `signal`, `image.derived_from == ()`.
5. `objective_score` is emitted only when it is in `products` **and** `graph.objective is not None`. If requested without an objective → fail closed.
6. Empty `products=()` → empty observations and edges (explicit, not default).
7. Do **not** turn on magnetization/configuration snapshots in this task. If those kinds are requested while API still strips snapshot flags, fail closed with a clear message rather than returning empty arrays that look successful.

Provenance.representation must be the **selected representation** (`plan.representation`), not blindly `meta["engine"]`. Today both are equal; still wire it from the plan so hybrid later does not lie.

---

## Out of scope (park)

| Item | Why parked |
|------|------------|
| Wave F workspace shell / cursors | Task 8 |
| TSE vertical-slice UI / Feature-Sliced projections | Frontend line |
| Graph executable-ization / pulse inspector | Later |
| Frozen Pydantic on all experiment models | Would rewrite Task 7 tests; not required for immutable *resolution* |
| Snapshot observations (magnetization / configurations) via API | API still forces snapshot flags off |
| New engines (ssEPG, PDG, EPG-X, hybrid) | Seams only, already in capability table |
| Changing `select_representation` fail-closed / no-failover rule | Behavior lock |

---

## Files

**Create**

- `tests/experiment/test_execution_plan.py`
- `tests/experiment/test_readout_spec.py` (or fold into `test_observations.py`)

**Modify**

- `packages/mrqlab_experiment/mrqlab_experiment/kernel.py` — `ExecutionPlan`, `plan_experiment`, `KernelRun.plan`, `run_experiment` uses plan
- `packages/mrqlab_experiment/mrqlab_experiment/observations.py` — filter by `readout.products`; representation from plan
- `packages/mrqlab_experiment/mrqlab_experiment/__init__.py` — export `ExecutionPlan`, `plan_experiment`
- `services/api/mrqlab_api/main.py` — copy-on-resolve; no in-place mutation
- `tests/test_api.py` — immutability + readout + existing compat
- `tests/experiment/test_kernel.py` / `test_observations.py` — plan + default products still pass
- `docs/superpowers/plans/2026-08-15-experiment-kernel.md` — insert Task 7.5 before Task 8 (docs-only, same PR or follow-up commit)

**Do not touch:** `packages/physics/**` numerical backends, Wave F `apps/web/**`, SequenceIR DNA.

---

## TDD acceptance

See sibling plan `.hermes/plans/2026-08-16_170021-experiment-kernel-7.5-tdd.md`.

Must stay green:

```text
.venv/bin/python -m pytest tests/ -q
```

Existing invariants:

- SE/GRE → bloch when no override
- TSE template without `engine` → epg (`preferred_engine` metadata still wins when `EngineRef.preferred` is None)
- Explicit `engine` override still wins if capabilities allow
- `/simulate` legacy JSON shape unchanged
- `/experiments/run` remains ResultGraph
- Disturbance `slice_profile` still fail-closed `unavailable_representation` / `EPG → ssEPG`
- API still rejects snapshot collection (`return_magnetization` forced off)

New invariants:

- `run_experiment(tse).sim_result.meta["engine"] == plan.engine == "epg"` via resolver, not a second code path
- Mutating a graph after `plan_experiment` / `run_experiment` is irrelevant because inputs were not aliased/written
- `ReadoutSpec(products=("signal",))` → observations kinds `["signal"]` only
- HTTP `/experiments/run` does not change fields on a caller-held graph object (unit-test the handler with a live model instance)

---

## Handoff

- Impl branch: `feature/experiment-kernel-7.5`
- Author: Xiaolei `<zxl1412@gmail.com>`
- Push: picspin SSH (`id_ed25519_github` on this gateway is fine if `Hi picspin!`)
- No `gh` on Pi — compare URL after push
- Wave F stash exists on previous branch: `wip wave F RED (park before 7.5)` — do not pop onto 7.5
