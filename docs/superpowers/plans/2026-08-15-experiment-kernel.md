# Experiment Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elevate MRQLab’s existing physics microkernel into an experiment-centered product that compiles intent through three IR layers, produces typed observations, supports forward objectives and disturbance-driven capability selection, and proves the SE/GRE/TSE teaching loops.

**Architecture:** Add `packages/mrqlab_experiment` as an incremental façade around the existing `sequence-ir`, physics scheduler/engines, recon, and FastAPI process. The façade owns the five stable contracts and compilation/result lifecycle; numerical physics stays in the current microkernel. The Next.js application becomes a workspace shell whose clinical Explore, Editor lenses, and TSE Signal Lab share one experiment state.

**Tech Stack:** Python >=3.11, Pydantic >=2, NumPy >=1.26, FastAPI >=0.110, pytest >=8; Next.js 14.2.5, React 18.3.1, TypeScript >=5.5, Vitest, jsdom, Testing Library. One Python process plus one Next.js application; no new required network or GPU runtime.

**Spec:** `docs/superpowers/specs/2026-08-15-experiment-kernel.md`

## Global Constraints

- The stable contracts are named exactly `ExperimentGraph`, `PhysicsOperator`, `StateRepresentation`, `ObjectiveFunction`, and `Observation`.
- The compilation boundary is exactly `Experiment IR → Sequence Compiler → Sequence IR → Physics Compiler → Physics IR → StateRepresentation + Operators → Observation`.
- `SequenceIR` remains the scanner-level source of truth and keeps its eight channels.
- Preserve `SimulationEngine.simulate(SequenceIR, Phantom, ScannerModel, EngineOptions) -> SimResult`; wrap it instead of rewriting physics.
- EPG, EPG-X, and ssEPG are forward models. Optimization is a separate plugin port consuming `ObjectiveFunction`; v0 implements no optimizer algorithm.
- Keep representation separate from operator and use a capability matrix, never a `BaseSimulator` inheritance tree.
- ssEPG is a separate compiler/representation path. PDG bridges phase pathways and spatial image formation. Floquet is only a future `PeriodicSequenceAccelerator`/`SteadyStateSolver`; density matrix + Liouville–von Neumann remains the future MRS base.
- Keep `POST /simulate` compatible and add `POST /experiments/validate` and `POST /experiments/run` as canonical endpoints.
- Begin in `packages/mrqlab_experiment`; document `core/` as the target rename and make no big-bang moves.
- Deploy as one Python process plus Next.js. Do not introduce microservices, queues, GPU workers, or mandatory online services.
- v0.1 proves SE, GRE, and TSE only. Do not implement Floquet, CEST, MRS, DCE, ssEPG, EPG-X exchange, or built-in PDG physics.
- Dashboard Explore is clinical-first. Editor uses Linked Lens and shared cursors named `cursorTime`, `selectedEvent`, `selectedState`, `selectedVoxel`, and `selectedEcho`.
- Reality Slider is only UX sugar over a typed `DisturbanceStack`; unsupported disturbances fail closed and may explain engine reselection.
- AI Lab is last and this plan publishes tool schemas only; the simulator core remains offline-capable.
- Every task starts with a failing test, implements the smallest passing behavior, runs focused and regression tests, and creates one reviewable commit.

---

## File and Module Map

| Path | Action | Single responsibility |
|---|---|---|
| `packages/mrqlab_experiment/mrqlab_experiment/models.py` | Create | `ExperimentGraph` and experiment-level value objects. |
| `packages/mrqlab_experiment/mrqlab_experiment/presets.py` | Create | Clinical/teaching presets that build graphs. |
| `packages/mrqlab_experiment/mrqlab_experiment/compiler.py` | Create | Experiment IR → existing `SequenceIR`. |
| `packages/mrqlab_experiment/mrqlab_experiment/kernel.py` | Create | Validate/run lifecycle and compatibility wrapping. |
| `packages/mrqlab_experiment/mrqlab_experiment/capabilities.py` | Create | `StateRepresentation` descriptors and set-based negotiation. |
| `packages/mrqlab_experiment/mrqlab_experiment/physics_ir.py` | Create | `PhysicsOperator`, `PhysicsIR`, and compiler-span vocabulary. |
| `packages/mrqlab_experiment/mrqlab_experiment/observations.py` | Create | `Observation`, `ResultGraph`, serialization, and provenance. |
| `packages/mrqlab_experiment/mrqlab_experiment/objectives.py` | Create | `ObjectiveFunction` v0 scalar evaluation. |
| `packages/mrqlab_experiment/mrqlab_experiment/disturbances.py` | Create | `DisturbanceStack`, slider mapping, and capability effects. |
| `packages/mrqlab_experiment/mrqlab_experiment/__init__.py` | Create | Stable public exports only. |
| `packages/physics/mrqlab_physics/base.py` | Modify | Attach representation/capability metadata to existing plugins. |
| `packages/physics/mrqlab_physics/engines/*.py` | Modify | Declare built-in capabilities; no numerical rewrite. |
| `packages/physics/mrqlab_physics/registry.py` | Modify | Expose capability descriptors. |
| `services/api/mrqlab_api/main.py` | Modify | Canonical experiment endpoints and `/simulate` adapter. |
| `pyproject.toml` | Modify | Discover `mrqlab_experiment*`. |
| `tests/experiment/` | Create | Contract, compiler, capability, result, objective, disturbance, and thesis tests. |
| `tests/test_api.py` | Modify | Canonical/compatibility endpoint gates. |
| `apps/web/lib/experiment.ts` | Create | Shared experiment/result/cursor TypeScript types. |
| `apps/web/lib/api.ts` | Create | Typed calls to presets and experiment endpoints. |
| `apps/web/components/workspace/WorkspaceProvider.tsx` | Create | Shared experiment state, cursors, undo/redo, and persistence. |
| `apps/web/components/workspace/WorkspaceShell.tsx` | Create | Workspace navigation and layout. |
| `apps/web/components/editor/LinkedLens.tsx` | Create | SYSTEM/PHYSICS/STATE/OBSERVATION linked views. |
| `apps/web/components/signal-lab/TseSignalLab.tsx` | Create | Refocusing-FA teaching chain. |
| `apps/web/app/page.tsx` | Replace | Clinical-first Explore/Build/Resume dashboard. |
| `apps/web/app/editor/page.tsx` | Create | Editor workspace route. |
| `apps/web/app/signal-lab/page.tsx` | Create | Signal Lab route. |
| `apps/web/app/style.css` | Modify | Instrumental skeuomorphism and ratio tokens. |
| `apps/web/tests/` | Create | Vitest component/state tests. |
| `docs/agent-tools/experiment-tools.schema.json` | Create | Agent tool schemas over `ExperimentGraph`; no runtime agent. |
| `docs/ARCHITECTURE.md` | Modify | Experiment center, three IRs, modular monolith, and migration. |
| `docs/PHYSICS.md` | Modify | Representation/operator split and capability matrix. |
| `docs/ROADMAP.md` | Modify | A–H waves and explicit MVP hold line. |
| `README.md` | Modify | Pointers to spec, ADRs, and canonical API. |

## Stable Interfaces Used Across Tasks

```python
# packages/mrqlab_experiment/mrqlab_experiment/models.py
class ExperimentGraph(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    id: str
    name: str
    intent: Literal["teaching", "clinical_contrast", "physics", "custom"]
    nodes: tuple[ExperimentNode, ...]
    edges: tuple[ExperimentEdge, ...]
    sequence: SequenceIR | TemplateRef
    sample: SampleSpec = SampleSpec()
    scanner: ScannerSpec = ScannerSpec()
    engine: EngineRef = EngineRef()
    objective: ObjectiveFunction | None = None
    readout: ReadoutSpec = ReadoutSpec()
    constraints: ConstraintSet = ConstraintSet()
    disturbances: DisturbanceStack = DisturbanceStack()
    provenance: ProvenanceHints = ProvenanceHints()
```

```python
# packages/mrqlab_experiment/mrqlab_experiment/physics_ir.py
class PhysicsOperator(Protocol):
    t: float
    def apply(self, state: Any, event: Any, context: Any) -> Any: ...

class PhysicsIR(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    representation: str
    operators: tuple[PhysicsOperatorRecord, ...]
    compiler_spans: tuple[CompilerSpan, ...]
```

```python
# packages/mrqlab_experiment/mrqlab_experiment/observations.py
class Observation(BaseModel):
    id: str
    kind: ObservationKind
    schema_version: Literal["1.0"] = "1.0"
    data: Any
    axes: dict[str, list[float]] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    derived_from: tuple[str, ...] = ()
    provenance: ObservationProvenance

class ResultGraph(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    experiment_id: str
    observations: tuple[Observation, ...]
    edges: tuple[ResultEdge, ...]
```

The names and fields above are immutable across the A–H waves. Tasks add behavior around them, not alternate spellings.

## PR Wave Map

| Wave | Tasks | Review gate |
|---|---|---|
| Plan | This document, locked spec, ADR-0001…0005 | Documentation only |
| A | Tasks 1–2 | Graph compiles and both canonical/compat APIs run existing physics |
| B | Tasks 3–4 | Capabilities and Physics IR wrap the scheduler without numerical drift |
| C | Task 5 | Versioned ResultGraph and provenance replace ad-hoc response assembly |
| D | Task 6 | Objective v0 produces forward scores only |
| E | Task 7 | Disturbance stack validates and explains representation changes |
| 7.5 | Task 7.5 | ExecutionPlan drives engine selection, request graphs stay unmodified, and ResultGraph honors requested products |
| F | Tasks 8–9 | Clinical Explore and Editor Linked Lens share workspace state |
| G | Task 10 | TSE refocusing FA drives state → echo → k-space → contrast → SAR |
| H | Task 11 | JSON schemas only for tools over `ExperimentGraph` |
| Acceptance | Task 12 | Docs and full regression gate |

### Task 1 (PR A): Add ExperimentGraph, Presets, and the Sequence Compiler

**Files:**
- Create: `packages/mrqlab_experiment/mrqlab_experiment/models.py`
- Create: `packages/mrqlab_experiment/mrqlab_experiment/presets.py`
- Create: `packages/mrqlab_experiment/mrqlab_experiment/compiler.py`
- Create: `packages/mrqlab_experiment/mrqlab_experiment/__init__.py`
- Modify: `pyproject.toml`
- Test: `tests/experiment/test_graph_compiler.py`

**Interfaces:**
- Consumes: `mrqlab_sequence.SequenceIR`, `TemplateRequest`, and `build_sequence`.
- Produces: `ExperimentGraph`, `build_preset(name) -> ExperimentGraph`, and `compile_sequence(graph) -> SequenceIR`.

- [ ] **Step 1: Write the failing graph/compiler test**

```python
# tests/experiment/test_graph_compiler.py
import pytest
from mrqlab_experiment import ExperimentGraph, build_preset, compile_sequence
from mrqlab_experiment.models import ExperimentNode

def test_tse_preset_is_an_experiment_graph_above_sequence_ir():
    graph = build_preset("dark-blood-tse", {"te": 0.02, "tr": 0.1, "echoes": 2})
    assert isinstance(graph, ExperimentGraph)
    assert graph.intent == "clinical_contrast"
    assert [node.kind for node in graph.nodes] == ["RF", "LOOP", "READOUT"]
    sequence = compile_sequence(graph)
    assert sequence.metadata["preferred_engine"] == "epg"
    assert sequence.metadata["experiment_id"] == graph.id

def test_reserved_experiment_node_cannot_execute_in_v0():
    graph = build_preset("spin-echo")
    graph.nodes += (ExperimentNode(id="inject", kind="INJECTION", label="Injection"),)
    with pytest.raises(ValueError, match="reserved node kind INJECTION is not executable in schema 1.0"):
        compile_sequence(graph)
```

- [ ] **Step 2: Run the test and verify the package is missing**

Run: `python3.11 -m pytest tests/experiment/test_graph_compiler.py -q`

Expected: FAIL during import because `mrqlab_experiment` does not exist.

- [ ] **Step 3: Add complete v0 graph models**

```python
# packages/mrqlab_experiment/mrqlab_experiment/models.py
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator
from mrqlab_sequence import SequenceIR

ActiveNodeKind = Literal["RF", "GRADIENT", "DELAY", "ADC", "READOUT", "LOOP"]
ReservedNodeKind = Literal["PREPARATION", "EXCHANGE", "FLOW", "DIFFUSION", "INJECTION"]
NodeKind = ActiveNodeKind | ReservedNodeKind
EdgeKind = Literal["TEMPORAL", "DEPENDENCY", "STATE_TRANSITION"]

class ExperimentNode(BaseModel):
    id: str
    kind: NodeKind
    label: str
    parameters: dict[str, Any] = Field(default_factory=dict)

class ExperimentEdge(BaseModel):
    source: str
    target: str
    kind: EdgeKind = "TEMPORAL"

class TemplateRef(BaseModel):
    template: Literal["SE", "GRE", "TSE"]
    params: dict[str, float | int] = Field(default_factory=dict)

class SampleSpec(BaseModel):
    t1: float = Field(default=1.0, gt=0)
    t2: float = Field(default=0.1, gt=0)
    proton_density: float = Field(default=1.0, ge=0)
    off_resonance_hz: float = 0.0

class ScannerSpec(BaseModel):
    b0_t: float = Field(default=1.5, gt=0)
    gradient_scale: float = Field(default=1.0, ge=0)

class EngineRef(BaseModel):
    preferred: str | None = None
    required_capabilities: frozenset[str] = frozenset()
    options: dict[str, Any] = Field(default_factory=dict)

class ObjectiveFunction(BaseModel):
    kind: Literal["null", "contrast_target"] = "null"
    terms: tuple[dict[str, Any], ...] = ()
    constraints: tuple[dict[str, Any], ...] = ()

class DisturbanceStack(BaseModel):
    items: tuple[dict[str, Any], ...] = ()

class ReadoutSpec(BaseModel):
    products: tuple[str, ...] = ("signal", "k_trajectory", "image")

class ConstraintSet(BaseModel):
    max_work: int = Field(default=2_000_000, ge=1)
    matrix: int = Field(default=32, ge=1)

class ProvenanceHints(BaseModel):
    seed: int = 0
    tags: tuple[str, ...] = ()

class ExperimentGraph(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    id: str
    name: str
    intent: Literal["teaching", "clinical_contrast", "physics", "custom"]
    nodes: tuple[ExperimentNode, ...]
    edges: tuple[ExperimentEdge, ...]
    sequence: SequenceIR | TemplateRef
    sample: SampleSpec = SampleSpec()
    scanner: ScannerSpec = ScannerSpec()
    engine: EngineRef = EngineRef()
    objective: ObjectiveFunction | None = None
    readout: ReadoutSpec = ReadoutSpec()
    constraints: ConstraintSet = ConstraintSet()
    disturbances: DisturbanceStack = DisturbanceStack()
    provenance: ProvenanceHints = ProvenanceHints()

    @model_validator(mode="after")
    def edges_reference_nodes(self):
        ids = {node.id for node in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("experiment node ids must be unique")
        if any(edge.source not in ids or edge.target not in ids for edge in self.edges):
            raise ValueError("experiment edges must reference existing nodes")
        return self
```

- [ ] **Step 4: Add complete presets and compiler**

```python
# packages/mrqlab_experiment/mrqlab_experiment/presets.py
from .models import ExperimentEdge, ExperimentGraph, ExperimentNode, TemplateRef

_PRESETS = {
    "spin-echo": ("SE", "Spin Echo", "teaching", ("RF", "RF", "READOUT")),
    "gradient-echo": ("GRE", "Gradient Echo", "teaching", ("RF", "GRADIENT", "READOUT")),
    "dark-blood-tse": ("TSE", "Dark Blood TSE", "clinical_contrast", ("RF", "LOOP", "READOUT")),
}

def build_preset(name: str, params: dict[str, float | int] | None = None) -> ExperimentGraph:
    try:
        template, title, intent, kinds = _PRESETS[name]
    except KeyError:
        raise ValueError(f"unknown experiment preset {name!r}") from None
    nodes = tuple(
        ExperimentNode(id=f"n{index}", kind=kind, label=f"{kind} {index}")
        for index, kind in enumerate(kinds)
    )
    edges = tuple(
        ExperimentEdge(source=nodes[index].id, target=nodes[index + 1].id)
        for index in range(len(nodes) - 1)
    )
    return ExperimentGraph(
        id=f"preset:{name}", name=title, intent=intent, nodes=nodes, edges=edges,
        sequence=TemplateRef(template=template, params=params or {}),
    )
```

```python
# packages/mrqlab_experiment/mrqlab_experiment/compiler.py
from mrqlab_sequence import SequenceIR, build_sequence
from .models import ExperimentGraph, TemplateRef

RESERVED = {"PREPARATION", "EXCHANGE", "FLOW", "DIFFUSION", "INJECTION"}

def compile_sequence(graph: ExperimentGraph) -> SequenceIR:
    for node in graph.nodes:
        if node.kind in RESERVED:
            raise ValueError(
                f"reserved node kind {node.kind} is not executable in schema {graph.schema_version}"
            )
    sequence = (
        graph.sequence.model_copy(deep=True)
        if isinstance(graph.sequence, SequenceIR)
        else build_sequence(graph.sequence.template, graph.sequence.params)
    )
    sequence.metadata = {**sequence.metadata, "experiment_id": graph.id}
    return sequence
```

```python
# packages/mrqlab_experiment/mrqlab_experiment/__init__.py
from .compiler import compile_sequence
from .models import ExperimentGraph
from .presets import build_preset

__all__ = ["ExperimentGraph", "build_preset", "compile_sequence"]
```

Add `"packages/mrqlab_experiment"` to `where` and `"mrqlab_experiment*"` to `include` under `[tool.setuptools.packages.find]` in `pyproject.toml`.

- [ ] **Step 5: Run focused and sequence regressions**

Run: `python3.11 -m pytest tests/experiment/test_graph_compiler.py tests/physics/test_template_metadata.py -q`

Expected: PASS; SE/GRE/TSE continue to compile through the existing template implementation.

- [ ] **Step 6: Commit PR A graph/compiler slice**

```bash
git add pyproject.toml packages/mrqlab_experiment tests/experiment/test_graph_compiler.py
git commit -m "feat(experiment): add graph and sequence compiler"
```

### Task 2 (PR A): Add Experiment Lifecycle and Canonical API Wrappers

**Files:**
- Create: `packages/mrqlab_experiment/mrqlab_experiment/kernel.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/__init__.py`
- Modify: `services/api/mrqlab_api/main.py`
- Create: `tests/experiment/test_kernel.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `compile_sequence`, existing `get_engine`, `Phantom`, `ScannerModel`, `EngineOptions`, and `SimResult`.
- Produces: `validate_experiment(graph) -> ValidationReport`, `run_experiment(graph) -> KernelRun`, `/presets`, `/experiments/validate`, and `/experiments/run`.

- [ ] **Step 1: Write failing lifecycle and compatibility tests**

```python
# tests/experiment/test_kernel.py
from mrqlab_experiment import build_preset, run_experiment, validate_experiment

def test_kernel_runs_existing_bloch_path_without_reimplementing_physics():
    graph = build_preset("spin-echo", {"te": 0.02, "tr": 0.1})
    report = validate_experiment(graph)
    run = run_experiment(graph)
    assert report.valid is True
    assert run.sequence.metadata["experiment_id"] == graph.id
    assert run.sim_result.meta["engine"] == "bloch"
    assert run.sim_result.signal.size > 0
```

Append to `tests/test_api.py`:

```python
def test_experiment_run_is_canonical_and_simulate_remains_compatible():
    graph = client.get("/presets").json()["presets"][0]["experiment"]
    canonical = client.post("/experiments/run", json=graph)
    compat = client.post("/simulate", json={"template": {"template": "SE"}})
    assert canonical.status_code == 200
    assert compat.status_code == 200
    assert canonical.json()["meta"]["engine"] == compat.json()["meta"]["engine"] == "bloch"

def test_experiment_validate_rejects_reserved_nodes():
    graph = client.get("/presets").json()["presets"][0]["experiment"]
    graph["nodes"].append({"id": "future", "kind": "INJECTION", "label": "Injection"})
    response = client.post("/experiments/validate", json=graph)
    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["errors"][0]["code"] == "unsupported_node"
```

- [ ] **Step 2: Run the tests and verify lifecycle/API symbols are absent**

Run: `python3.11 -m pytest tests/experiment/test_kernel.py tests/test_api.py -q`

Expected: FAIL because the kernel functions and experiment routes do not exist.

- [ ] **Step 3: Implement the lifecycle façade**

```python
# packages/mrqlab_experiment/mrqlab_experiment/kernel.py
from dataclasses import dataclass, replace
from pydantic import BaseModel
from mrqlab_physics import EngineOptions, Phantom, ScannerModel, SimResult, get_engine
from mrqlab_sequence import SequenceIR
from .compiler import compile_sequence
from .models import ExperimentGraph

class ValidationIssue(BaseModel):
    code: str
    message: str

class ValidationReport(BaseModel):
    valid: bool
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()

@dataclass(slots=True)
class KernelRun:
    experiment: ExperimentGraph
    sequence: SequenceIR
    sim_result: SimResult

def validate_experiment(graph: ExperimentGraph) -> ValidationReport:
    try:
        compile_sequence(graph)
    except ValueError as exc:
        code = "unsupported_node" if "reserved node kind" in str(exc) else "invalid_graph"
        return ValidationReport(valid=False, errors=(ValidationIssue(code=code, message=str(exc)),))
    return ValidationReport(valid=True)

def run_experiment(graph: ExperimentGraph) -> KernelRun:
    report = validate_experiment(graph)
    if not report.valid:
        raise ValueError(report.errors[0].message)
    sequence = compile_sequence(graph)
    requested = EngineOptions(**graph.engine.options)
    options = replace(requested, max_work=min(requested.max_work, graph.constraints.max_work))
    engine_name = graph.engine.preferred or str(sequence.metadata.get("preferred_engine", "bloch"))
    result = get_engine(engine_name).simulate(
        sequence,
        Phantom(**graph.sample.model_dump()),
        ScannerModel(**graph.scanner.model_dump()),
        options,
    )
    return KernelRun(graph, sequence, result)
```

Export `KernelRun`, `ValidationReport`, `run_experiment`, and `validate_experiment` from `mrqlab_experiment.__init__`.

- [ ] **Step 4: Add exact API adapter helpers and routes**

```python
# services/api/mrqlab_api/main.py additions
from mrqlab_experiment import (
    ExperimentGraph, build_preset, run_experiment, validate_experiment,
)

def _legacy_response(result, matrix: int) -> dict[str, Any]:
    recon = fft_reconstruct(result.signal) if result.signal.size else np.array([])
    return {
        "signal": [{"real": float(value.real), "imag": float(value.imag)} for value in result.signal],
        "k_trajectory": result.k_trajectory.tolist(),
        "reconstruction_magnitude": np.abs(recon).tolist(),
        "meta": result.meta,
        "timing": result.timing,
    }

@app.get("/presets")
def presets():
    names = ("spin-echo", "gradient-echo", "dark-blood-tse")
    return {"presets": [{"name": name, "experiment": build_preset(name).model_dump(mode="json")} for name in names]}

@app.post("/experiments/validate")
def experiments_validate(graph: ExperimentGraph):
    return validate_experiment(graph)

@app.post("/experiments/run")
def experiments_run(graph: ExperimentGraph):
    if graph.constraints.matrix > MAX_MATRIX:
        raise HTTPException(422, f"matrix exceeds SIM_MAX_MATRIX ({MAX_MATRIX})")
    graph.constraints.max_work = min(graph.constraints.max_work, MAX_WORK)
    try:
        return _legacy_response(run_experiment(graph).sim_result, graph.constraints.matrix)
    except (ValueError, TypeError, NotImplementedError) as exc:
        raise HTTPException(422, str(exc)) from exc
```

Replace the body of `/simulate` after its matrix check with an adapter that builds a graph and calls the canonical lifecycle:

```python
    sequence = request.sequence or build_sequence(request.template.template, request.template.params)
    graph = build_preset(
        {"SE": "spin-echo", "GRE": "gradient-echo", "TSE": "dark-blood-tse"}.get(
            str(sequence.metadata.get("template", "SE")), "spin-echo"
        )
    )
    graph.sequence = sequence
    graph.engine.preferred = request.engine
    graph.engine.options = request.options
    graph.sample = graph.sample.model_validate(request.phantom or {})
    graph.scanner = graph.scanner.model_validate(request.scanner or {})
    graph.constraints.matrix = request.matrix
    graph.constraints.max_work = MAX_WORK
    try:
        return _legacy_response(run_experiment(graph).sim_result, request.matrix)
    except (ValueError, TypeError, NotImplementedError) as exc:
        raise HTTPException(422, str(exc)) from exc
```

- [ ] **Step 5: Run lifecycle, API, and physics regressions**

Run: `python3.11 -m pytest tests/experiment/test_kernel.py tests/test_api.py tests/physics/test_bloch_engine.py tests/physics/test_epg_engine.py -q`

Expected: PASS; `/simulate` still returns its existing keys and both APIs execute the same `run_experiment` path.

- [ ] **Step 6: Commit PR A lifecycle/API slice**

```bash
git add packages/mrqlab_experiment services/api/mrqlab_api/main.py tests/experiment/test_kernel.py tests/test_api.py
git commit -m "feat(api): add canonical experiment lifecycle"
```

### Task 3 (PR B): Declare StateRepresentation Capabilities and Negotiate Engines

**Files:**
- Create: `packages/mrqlab_experiment/mrqlab_experiment/capabilities.py`
- Modify: `packages/physics/mrqlab_physics/base.py`
- Modify: `packages/physics/mrqlab_physics/engines/bloch_engine.py`
- Modify: `packages/physics/mrqlab_physics/engines/epg_engine.py`
- Modify: `packages/physics/mrqlab_physics/engines/spectral_engine.py`
- Modify: `packages/physics/mrqlab_physics/registry.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/kernel.py`
- Test: `tests/experiment/test_capabilities.py`

**Interfaces:**
- Consumes: Existing `EnginePlugin` descriptors and graph `required_capabilities`.
- Produces: `StateRepresentation`, `CapabilityMismatch`, `select_representation`, and `/engines` descriptors with `representation` and `supports`.

- [ ] **Step 1: Write the failing capability-matrix tests**

```python
# tests/experiment/test_capabilities.py
import pytest
from mrqlab_experiment import build_preset, validate_experiment
from mrqlab_experiment.capabilities import CapabilityMismatch, select_representation

def test_capability_selection_is_set_inclusion_not_inheritance():
    selected = select_representation(frozenset({"configuration_states", "hard_rf"}), "epg")
    assert selected.name == "epg"
    assert selected.supports >= {"configuration_states", "hard_rf"}

def test_missing_shaped_rf_fails_closed_with_ssepg_explanation():
    graph = build_preset("dark-blood-tse")
    graph.engine.required_capabilities = frozenset({"configuration_states", "shaped_rf"})
    report = validate_experiment(graph)
    assert report.valid is False
    assert report.errors[0].code == "capability_mismatch"
    assert "ssEPG" in report.errors[0].message

def test_no_base_simulator_skill_tree_exists():
    with pytest.raises(CapabilityMismatch):
        select_representation(frozenset({"exchange"}), "epg")
```

- [ ] **Step 2: Run the test and verify capability symbols are missing**

Run: `python3.11 -m pytest tests/experiment/test_capabilities.py -q`

Expected: FAIL during import because `capabilities.py` does not exist.

- [ ] **Step 3: Implement the complete capability matrix**

```python
# packages/mrqlab_experiment/mrqlab_experiment/capabilities.py
from dataclasses import dataclass

Capability = str

@dataclass(frozen=True, slots=True)
class StateRepresentation:
    name: str
    supports: frozenset[Capability]
    available: bool
    explanation: str

class CapabilityMismatch(ValueError):
    pass

REPRESENTATIONS = {
    "bloch": StateRepresentation(
        "bloch", frozenset({"hard_rf", "off_resonance", "spatial_encoding", "magnetization_states"}),
        True, "Cartesian magnetization for spatial and off-resonance evolution",
    ),
    "epg": StateRepresentation(
        "epg", frozenset({"hard_rf", "configuration_states", "steady_state"}),
        True, "Classic single-pool configuration states for echo trains",
    ),
    "spectral": StateRepresentation(
        "spectral", frozenset({"hard_rf", "off_resonance", "multi_pool", "magnetization_states"}),
        True, "Independent chemical-shift pools without exchange",
    ),
    "ssepg": StateRepresentation(
        "ssepg", frozenset({"hard_rf", "shaped_rf", "configuration_states", "spatial_encoding"}),
        False, "ssEPG is a dedicated future compiler path for slice-selective RF",
    ),
    "pdg": StateRepresentation(
        "pdg", frozenset({"hard_rf", "configuration_states", "spatial_encoding", "off_resonance"}),
        False, "PDG is an optional provider seam bridging pathways and image formation",
    ),
    "epg-x": StateRepresentation(
        "epg-x", frozenset({"hard_rf", "configuration_states", "exchange", "multi_pool"}),
        False, "EPG-X combines EPG state with exchange operators",
    ),
}

def select_representation(required: frozenset[str], preferred: str | None) -> StateRepresentation:
    candidates = [REPRESENTATIONS[preferred]] if preferred in REPRESENTATIONS else list(REPRESENTATIONS.values())
    matches = [item for item in candidates if item.available and required <= item.supports]
    if matches:
        return matches[0]
    future = [item for item in REPRESENTATIONS.values() if required <= item.supports]
    hint = future[0].explanation if future else f"no representation declares {sorted(required)}"
    raise CapabilityMismatch(f"required capabilities {sorted(required)} are unavailable: {hint}")
```

- [ ] **Step 4: Attach exact metadata to EnginePlugin and registry output**

Add these fields to `EnginePlugin` in `packages/physics/mrqlab_physics/base.py`:

```python
    representation: str = "bloch"
    supports: frozenset[str] = frozenset()
```

Add strict validation:

```python
        if not isinstance(self.representation, str) or not self.representation:
            raise ValueError("engine plugin representation must be a non-empty string")
        if not isinstance(self.supports, frozenset) or any(not isinstance(x, str) for x in self.supports):
            raise TypeError("engine plugin supports must be a frozenset of strings")
```

Set the built-in engine descriptors to the exact capability sets from `REPRESENTATIONS`, then add these keys to each registry descriptor:

```python
"representation": engine.plugin.representation,
"supports": sorted(engine.plugin.supports),
```

At the end of `validate_experiment`, before returning valid, add:

```python
    try:
        select_representation(graph.engine.required_capabilities, graph.engine.preferred)
    except CapabilityMismatch as exc:
        return ValidationReport(
            valid=False,
            errors=(ValidationIssue(code="capability_mismatch", message=str(exc)),),
        )
```

- [ ] **Step 5: Run capability, registry, and API tests**

Run: `python3.11 -m pytest tests/experiment/test_capabilities.py tests/physics/test_registry_plugins.py tests/test_api.py -q`

Expected: PASS; built-ins declare capabilities and unavailable representations fail closed.

- [ ] **Step 6: Commit PR B capability slice**

```bash
git add packages/mrqlab_experiment packages/physics/mrqlab_physics tests/experiment/test_capabilities.py
git commit -m "feat(physics): declare representation capabilities"
```

### Task 4 (PR B): Formalize PhysicsOperator Records and Physics IR Compiler Spans

**Files:**
- Create: `packages/mrqlab_experiment/mrqlab_experiment/physics_ir.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/kernel.py`
- Test: `tests/experiment/test_physics_ir.py`

**Interfaces:**
- Consumes: Existing `preflight_schedule`, `schedule`, and `RfOp | Relax | Shift | GradInterval | AdcSample`.
- Produces: `PhysicsOperator`, `PhysicsOperatorRecord`, `CompilerSpan`, `PhysicsIR`, and `compile_physics_ir`.

- [ ] **Step 1: Write the failing Physics IR test**

```python
# tests/experiment/test_physics_ir.py
from mrqlab_experiment import build_preset, compile_sequence
from mrqlab_experiment.physics_ir import compile_physics_ir
from mrqlab_physics import EngineOptions

def test_existing_scheduler_compiles_to_versioned_physics_ir():
    graph = build_preset("dark-blood-tse", {"te": 0.02, "tr": 0.1, "echoes": 2})
    ir = compile_physics_ir(compile_sequence(graph), "epg", EngineOptions(epg_kmax=8))
    assert ir.schema_version == "1.0"
    assert ir.representation == "epg"
    assert {op.kind for op in ir.operators} >= {"RF_ROTATION", "FREE_EVOLUTION", "EPG_SHIFT", "READOUT"}
    assert ir.compiler_spans == ({"kind": "EPG", "start": 0, "stop": len(ir.operators)},)

def test_ssepg_is_a_distinct_span_name_not_epg_flag():
    assert "ssEPG" in {"Bloch", "EPG", "PDG", "ssEPG"}
```

- [ ] **Step 2: Run the test and verify the Physics IR module is absent**

Run: `python3.11 -m pytest tests/experiment/test_physics_ir.py -q`

Expected: FAIL during import because `physics_ir.py` does not exist.

- [ ] **Step 3: Implement the complete typed compiler adapter**

```python
# packages/mrqlab_experiment/mrqlab_experiment/physics_ir.py
from typing import Any, Literal, Protocol
from pydantic import BaseModel
from mrqlab_physics import EngineOptions
from mrqlab_physics.kernel.scheduler import preflight_schedule, schedule
from mrqlab_physics.ops.types import AdcSample, GradInterval, Relax, RfOp, Shift
from mrqlab_sequence import SequenceIR

class PhysicsOperator(Protocol):
    t: float
    def apply(self, state: Any, event: Any, context: Any) -> Any: ...

OperatorKind = Literal["RF_ROTATION", "FREE_EVOLUTION", "EPG_SHIFT", "GRADIENT", "READOUT"]
SpanKind = Literal["Bloch", "EPG", "PDG", "ssEPG"]

class PhysicsOperatorRecord(BaseModel):
    kind: OperatorKind
    t: float
    parameters: dict[str, Any]

class CompilerSpan(BaseModel):
    kind: SpanKind
    start: int
    stop: int

class PhysicsIR(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    representation: str
    operators: tuple[PhysicsOperatorRecord, ...]
    compiler_spans: tuple[CompilerSpan, ...]

def _record(op) -> PhysicsOperatorRecord:
    if isinstance(op, RfOp):
        return PhysicsOperatorRecord(kind="RF_ROTATION", t=op.t, parameters={"alpha_rad": op.alpha_rad, "phase_rad": op.phase_rad})
    if isinstance(op, Relax):
        return PhysicsOperatorRecord(kind="FREE_EVOLUTION", t=op.t, parameters={"dt": op.dt})
    if isinstance(op, Shift):
        return PhysicsOperatorRecord(kind="EPG_SHIFT", t=op.t, parameters={"dk": op.dk, "source": op.source})
    if isinstance(op, GradInterval):
        return PhysicsOperatorRecord(kind="GRADIENT", t=op.t, parameters={"dt": op.dt, "gradient": op.gradient})
    if isinstance(op, AdcSample):
        return PhysicsOperatorRecord(kind="READOUT", t=op.t, parameters={"nco_frequency_hz": op.nco_frequency_hz, "nco_phase_rad": op.nco_phase_rad})
    raise TypeError(f"unknown scheduled operator {type(op).__name__}")

def compile_physics_ir(sequence: SequenceIR, representation: str, options: EngineOptions) -> PhysicsIR:
    plan = preflight_schedule(sequence, options, max_operators=options.max_work)
    records = tuple(_record(op) for op in schedule(sequence, options, plan))
    span_name = {"bloch": "Bloch", "epg": "EPG", "pdg": "PDG", "ssepg": "ssEPG"}.get(representation)
    if span_name is None:
        raise ValueError(f"no compiler span for representation {representation!r}")
    return PhysicsIR(
        representation=representation,
        operators=records,
        compiler_spans=(CompilerSpan(kind=span_name, start=0, stop=len(records)),),
    )
```

- [ ] **Step 4: Run Physics IR and scheduler regression tests**

Run: `python3.11 -m pytest tests/experiment/test_physics_ir.py tests/physics/test_scheduler_runner.py tests/physics/test_ops_golden.py -q`

Expected: PASS; operator ordering and values remain owned by the existing scheduler.

- [ ] **Step 5: Commit PR B Physics IR slice**

```bash
git add packages/mrqlab_experiment/mrqlab_experiment/physics_ir.py tests/experiment/test_physics_ir.py
git commit -m "feat(experiment): expose typed physics IR"
```

### Task 5 (PR C): Wrap SimResult in Observation and ResultGraph

**Files:**
- Create: `packages/mrqlab_experiment/mrqlab_experiment/observations.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/kernel.py`
- Modify: `services/api/mrqlab_api/main.py`
- Create: `tests/experiment/test_observations.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `KernelRun`, `SimResult`, `fft_reconstruct`, experiment/readout metadata.
- Produces: `Observation`, `ResultGraph`, `build_result_graph`, and canonical JSON from `/experiments/run`; `/simulate` retains legacy JSON.

- [ ] **Step 1: Write the failing result/provenance tests**

```python
# tests/experiment/test_observations.py
from mrqlab_experiment import build_preset, run_experiment
from mrqlab_experiment.observations import build_result_graph

def test_result_graph_wraps_signal_kspace_image_and_provenance():
    graph = build_preset("gradient-echo", {"te": 0.02, "tr": 0.1})
    result = build_result_graph(run_experiment(graph))
    assert [item.kind for item in result.observations] == ["signal", "k_trajectory", "image"]
    image = result.observations[-1]
    assert image.derived_from == (result.observations[0].id,)
    assert image.provenance.engine == "bloch"
    assert image.provenance.experiment_hash
```

Append to `tests/test_api.py`:

```python
def test_canonical_run_returns_result_graph_while_simulate_keeps_legacy_shape():
    graph = client.get("/presets").json()["presets"][1]["experiment"]
    canonical = client.post("/experiments/run", json=graph).json()
    compat = client.post("/simulate", json={"template": {"template": "GRE"}}).json()
    assert canonical["schema_version"] == "1.0"
    assert {item["kind"] for item in canonical["observations"]} >= {"signal", "k_trajectory", "image"}
    assert "reconstruction_magnitude" in compat
```

- [ ] **Step 2: Run tests and verify observation symbols are missing**

Run: `python3.11 -m pytest tests/experiment/test_observations.py tests/test_api.py -q`

Expected: FAIL during import because `observations.py` does not exist.

- [ ] **Step 3: Implement versioned observations and deterministic provenance**

```python
# packages/mrqlab_experiment/mrqlab_experiment/observations.py
import hashlib, json
from typing import Any, Literal
import numpy as np
from pydantic import BaseModel, Field
from mrqlab_recon import fft_reconstruct

ObservationKind = Literal["signal", "k_trajectory", "image", "magnetization", "configurations", "echo_train", "sar", "objective_score"]

class ObservationProvenance(BaseModel):
    experiment_hash: str
    engine: str
    representation: str
    assumptions: tuple[str, ...]
    seed: int
    n_ops: int
    estimated_work: int

class Observation(BaseModel):
    id: str
    kind: ObservationKind
    schema_version: Literal["1.0"] = "1.0"
    data: Any
    axes: dict[str, list[float]] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    derived_from: tuple[str, ...] = ()
    provenance: ObservationProvenance

class ResultEdge(BaseModel):
    source: str
    target: str
    kind: Literal["derived_from", "engine", "recon"]

class ResultGraph(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    experiment_id: str
    observations: tuple[Observation, ...]
    edges: tuple[ResultEdge, ...]

def _complex(values: np.ndarray) -> list[dict[str, float]]:
    return [{"real": float(v.real), "imag": float(v.imag)} for v in values]

def build_result_graph(run) -> ResultGraph:
    raw = run.experiment.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    meta = run.sim_result.meta
    provenance = ObservationProvenance(
        experiment_hash=digest, engine=str(meta["engine"]), representation=str(meta["engine"]),
        assumptions=tuple(meta.get("assumptions", ())), seed=run.experiment.provenance.seed,
        n_ops=int(meta.get("n_ops", 0)), estimated_work=int(meta.get("estimated_work", 0)),
    )
    signal = Observation(id="signal", kind="signal", data=_complex(run.sim_result.signal), units={"value": "a.u."}, provenance=provenance)
    trajectory = Observation(id="k_trajectory", kind="k_trajectory", data=run.sim_result.k_trajectory.tolist(), units={"k": "teaching-gradient·s"}, provenance=provenance)
    image_data = np.abs(fft_reconstruct(run.sim_result.signal)).tolist() if run.sim_result.signal.size else []
    image = Observation(id="image", kind="image", data=image_data, units={"value": "a.u."}, derived_from=(signal.id,), provenance=provenance)
    return ResultGraph(
        experiment_id=run.experiment.id, observations=(signal, trajectory, image),
        edges=(ResultEdge(source=signal.id, target=image.id, kind="recon"),),
    )
```

- [ ] **Step 4: Return ResultGraph only from the canonical route**

Replace the success return in `experiments_run` with:

```python
        return build_result_graph(run_experiment(graph))
```

Keep `_legacy_response` exclusively in `/simulate`. Export `Observation` and `ResultGraph` from `mrqlab_experiment.__init__`.

- [ ] **Step 5: Run result, API, recon, and engine regressions**

Run: `python3.11 -m pytest tests/experiment/test_observations.py tests/test_api.py tests/physics/test_cross_engine.py -q`

Expected: PASS; canonical runs are versioned while `/simulate` remains backward compatible.

- [ ] **Step 6: Commit PR C ResultGraph slice**

```bash
git add packages/mrqlab_experiment services/api/mrqlab_api/main.py tests/experiment/test_observations.py tests/test_api.py
git commit -m "feat(experiment): add observation result graph"
```

### Task 6 (PR D): Evaluate ObjectiveFunction v0 Without an Optimizer

**Files:**
- Create: `packages/mrqlab_experiment/mrqlab_experiment/objectives.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/models.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/observations.py`
- Test: `tests/experiment/test_objectives.py`

**Interfaces:**
- Consumes: Signal observations and typed objective terms.
- Produces: `ObjectiveFunction`, `ObjectiveTerm`, `ObjectiveConstraint`, and `evaluate_objective` returning an `objective_score` observation.

- [ ] **Step 1: Write the failing forward-score test**

```python
# tests/experiment/test_objectives.py
import pytest
from mrqlab_experiment.objectives import ObjectiveFunction, ObjectiveTerm, evaluate_objective

def test_contrast_target_scores_forward_observations_only():
    objective = ObjectiveFunction(kind="contrast_target", terms=(
        ObjectiveTerm(observation="signal", metric="peak_magnitude", target=0.8, weight=2.0),
    ))
    score = evaluate_objective(objective, {"signal": [0.5 + 0j, 0.9 + 0j]})
    assert score == pytest.approx(0.02)
    assert not hasattr(objective, "optimize")

def test_null_objective_scores_zero():
    assert evaluate_objective(ObjectiveFunction(), {"signal": []}) == 0.0
```

- [ ] **Step 2: Run the test and verify the objective module is absent**

Run: `python3.11 -m pytest tests/experiment/test_objectives.py -q`

Expected: FAIL during import because `objectives.py` does not exist.

- [ ] **Step 3: Implement complete typed objective data and evaluator**

```python
# packages/mrqlab_experiment/mrqlab_experiment/objectives.py
from typing import Literal
import numpy as np
from pydantic import BaseModel, Field

class ObjectiveTerm(BaseModel):
    observation: Literal["signal", "echo_train"]
    metric: Literal["peak_magnitude", "mean_magnitude"]
    target: float
    weight: float = Field(default=1.0, gt=0)

class ObjectiveConstraint(BaseModel):
    metric: Literal["scan_time_s", "sar_relative"]
    upper_bound: float = Field(gt=0)
    penalty: float = Field(default=1.0, gt=0)

class ObjectiveFunction(BaseModel):
    kind: Literal["null", "contrast_target"] = "null"
    terms: tuple[ObjectiveTerm, ...] = ()
    constraints: tuple[ObjectiveConstraint, ...] = ()

def evaluate_objective(objective: ObjectiveFunction, products: dict[str, object]) -> float:
    if objective.kind == "null":
        return 0.0
    total = 0.0
    for term in objective.terms:
        values = np.asarray(products[term.observation], dtype=np.complex128)
        measured = float(np.max(np.abs(values))) if term.metric == "peak_magnitude" else float(np.mean(np.abs(values)))
        total += term.weight * (measured - term.target) ** 2
    return total
```

Import this `ObjectiveFunction` into `models.py` and delete the temporary class there. When `graph.objective` is non-null, append an `Observation(kind="objective_score", data=evaluate_objective(...), derived_from=("signal",))` in `build_result_graph`.

- [ ] **Step 4: Run objective and ResultGraph tests**

Run: `python3.11 -m pytest tests/experiment/test_objectives.py tests/experiment/test_observations.py -q`

Expected: PASS; there is no grid, Bayesian, CMA-ES, gradient, or AI search loop in runtime code.

- [ ] **Step 5: Commit PR D objective slice**

```bash
git add packages/mrqlab_experiment tests/experiment/test_objectives.py tests/experiment/test_observations.py
git commit -m "feat(experiment): add forward objective scores"
```

### Task 7 (PR E): Add DisturbanceStack Schema and Representation Reselection Explanations

**Files:**
- Create: `packages/mrqlab_experiment/mrqlab_experiment/disturbances.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/models.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/kernel.py`
- Test: `tests/experiment/test_disturbances.py`

**Interfaces:**
- Consumes: `StateRepresentation` capability vocabulary.
- Produces: typed `Disturbance`, `DisturbanceStack`, `stack_from_reality`, and `disturbance_requirements`.

- [ ] **Step 1: Write failing schema, slider, and reselection tests**

```python
# tests/experiment/test_disturbances.py
from mrqlab_experiment import build_preset, validate_experiment
from mrqlab_experiment.disturbances import Disturbance, DisturbanceStack, stack_from_reality

def test_reality_slider_maps_to_reproducible_stack():
    assert stack_from_reality(0).items == ()
    assert [item.kind for item in stack_from_reality(50).items] == ["thermal_noise", "b0_map"]

def test_slice_profile_teaches_ssepg_reselection_and_fails_closed():
    graph = build_preset("dark-blood-tse")
    graph.disturbances = DisturbanceStack(items=(
        Disturbance(id="slice", kind="slice_profile", domain="sequence", parameters={"samples": 32}),
    ))
    report = validate_experiment(graph)
    assert report.valid is False
    assert report.errors[0].code == "unavailable_representation"
    assert "EPG → ssEPG" in report.errors[0].message
```

- [ ] **Step 2: Run the test and verify typed disturbances are absent**

Run: `python3.11 -m pytest tests/experiment/test_disturbances.py -q`

Expected: FAIL during import because `disturbances.py` does not exist.

- [ ] **Step 3: Implement the complete v0 disturbance schema and mapping**

```python
# packages/mrqlab_experiment/mrqlab_experiment/disturbances.py
from typing import Any, Literal
from pydantic import BaseModel, Field

DisturbanceKind = Literal[
    "thermal_noise", "b0_map", "b1_map", "gradient_delay", "eddy_current",
    "gradient_nonlinearity", "motion", "flow", "diffusion", "exchange",
    "susceptibility", "coil_sensitivity", "adc_imperfection", "slice_profile",
]

class Disturbance(BaseModel):
    id: str
    kind: DisturbanceKind
    domain: Literal["signal", "field", "scanner", "motion", "tissue", "sequence"]
    enabled: bool = True
    parameters: dict[str, Any] = Field(default_factory=dict)

class DisturbanceStack(BaseModel):
    items: tuple[Disturbance, ...] = ()

_REQUIREMENTS = {
    "slice_profile": (frozenset({"shaped_rf", "configuration_states"}), "EPG → ssEPG"),
    "exchange": (frozenset({"exchange", "multi_pool"}), "EPG → EPG-X / hybrid"),
    "b0_map": (frozenset({"spatial_encoding", "off_resonance"}), "EPG → PDG for spatial B0"),
}

def disturbance_requirements(stack: DisturbanceStack) -> tuple[frozenset[str], tuple[str, ...]]:
    required: set[str] = set()
    explanations: list[str] = []
    for item in stack.items:
        if item.enabled and item.kind in _REQUIREMENTS:
            capabilities, explanation = _REQUIREMENTS[item.kind]
            required.update(capabilities)
            explanations.append(explanation)
    return frozenset(required), tuple(explanations)

def stack_from_reality(value: int) -> DisturbanceStack:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        raise ValueError("reality must be an integer from 0 to 100")
    items = []
    if value >= 25:
        items.append(Disturbance(id="noise", kind="thermal_noise", domain="signal", parameters={"snr_db": 40.0}))
    if value >= 50:
        items.append(Disturbance(id="b0", kind="b0_map", domain="field", parameters={"peak_hz": 20.0}))
    if value >= 75:
        items.append(Disturbance(id="motion", kind="motion", domain="motion", parameters={"translation_mm": 1.0}))
    return DisturbanceStack(items=tuple(items))
```

Import `DisturbanceStack` into `models.py` and remove its temporary class. In `validate_experiment`, combine disturbance requirements with `graph.engine.required_capabilities`; when explanations target an unavailable future representation, return `ValidationIssue(code="unavailable_representation", message="; ".join(explanations))`.

- [ ] **Step 4: Run disturbance, capability, and lifecycle tests**

Run: `python3.11 -m pytest tests/experiment/test_disturbances.py tests/experiment/test_capabilities.py tests/experiment/test_kernel.py -q`

Expected: PASS; no disturbance numerical operator is added to the physics backends.

- [ ] **Step 5: Commit PR E disturbance slice**

```bash
git add packages/mrqlab_experiment tests/experiment/test_disturbances.py
git commit -m "feat(experiment): add disturbance stack schema"
```

### Task 7.5: Harden the workbench physics backend (before Wave F)

Backend-only insert after Task 7 / PR E. `plan_experiment()` returns an `ExecutionPlan`; `validate_experiment` and `run_experiment` consume it so TSE without `EngineRef.preferred` executes EPG via capability selection. HTTP `/experiments/run` and `/simulate` resolve on a deep copy and never mutate the caller graph. `build_result_graph` emits exactly `ReadoutSpec.products`. Does not implement Wave F, snapshot collection, or a frozen-Pydantic sweep. Lock: `.hermes/plans/2026-08-16_170021-experiment-kernel-7.5-lock.md`.

### Task 8 (PR F): Establish the Workspace Shell, Shared Experiment State, and Cursors

**Files:**
- Modify: `apps/web/package.json`
- Create: `apps/web/vitest.config.ts`
- Create: `apps/web/tests/setup.ts`
- Create: `apps/web/lib/experiment.ts`
- Create: `apps/web/components/workspace/WorkspaceProvider.tsx`
- Create: `apps/web/components/workspace/WorkspaceShell.tsx`
- Modify: `apps/web/app/layout.tsx`
- Create: `apps/web/tests/workspace-provider.test.tsx`

**Interfaces:**
- Consumes: JSON-ready `ExperimentGraph` and `ResultGraph` contracts.
- Produces: one provider for workspace, experiment, result, undo/redo, persistence, and the five shared cursors.

- [ ] **Step 1: Add the failing workspace-state test**

```tsx
// apps/web/tests/workspace-provider.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WorkspaceProvider, useWorkspace } from "../components/workspace/WorkspaceProvider";

function Probe() {
  const state = useWorkspace();
  return <>
    <output>{state.workspace}:{state.cursors.selectedEcho ?? "none"}</output>
    <button onClick={() => state.openWorkspace("signal-lab")}>open</button>
    <button onClick={() => state.setCursors({ selectedEcho: 3 })}>echo</button>
  </>;
}

describe("WorkspaceProvider", () => {
  it("shares workspace and linked-lens cursors", () => {
    render(<WorkspaceProvider><Probe /></WorkspaceProvider>);
    fireEvent.click(screen.getByText("open"));
    fireEvent.click(screen.getByText("echo"));
    expect(screen.getByRole("status")).toHaveTextContent("signal-lab:3");
  });
});
```

- [ ] **Step 2: Configure Vitest and verify the provider is missing**

Add scripts and development dependencies to `apps/web/package.json`:

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "lint": "next lint",
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.8",
    "@testing-library/react": "^16.0.1",
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "jsdom": "^24.1.1",
    "typescript": "^5.5",
    "vitest": "^2.0.5"
  }
}
```

```ts
// apps/web/vitest.config.ts
import { defineConfig } from "vitest/config";
export default defineConfig({ test: { environment: "jsdom", setupFiles: ["./tests/setup.ts"] } });
```

```ts
// apps/web/tests/setup.ts
import "@testing-library/jest-dom/vitest";
```

Run: `cd apps/web && npm install && npm test -- workspace-provider.test.tsx`

Expected: FAIL because `WorkspaceProvider` does not exist.

- [ ] **Step 3: Add complete shared TypeScript contracts**

```ts
// apps/web/lib/experiment.ts
export type WorkspaceId = "dashboard" | "editor" | "signal-lab" | "contrast-lab" | "optimization-lab" | "ai-lab";
export type LensCursors = {
  cursorTime: number | null;
  selectedEvent: string | null;
  selectedState: string | null;
  selectedVoxel: [number, number, number] | null;
  selectedEcho: number | null;
};
export type ExperimentGraph = {
  schema_version: "1.0"; id: string; name: string;
  intent: "teaching" | "clinical_contrast" | "physics" | "custom";
  nodes: Array<{ id: string; kind: string; label: string; parameters: Record<string, unknown> }>;
  edges: Array<{ source: string; target: string; kind: string }>;
  sequence: Record<string, unknown>; sample: Record<string, unknown>;
  scanner: Record<string, unknown>; engine: Record<string, unknown>;
  objective: Record<string, unknown> | null; readout: { products: string[] };
  constraints: { max_work: number; matrix: number };
  disturbances: { items: Array<Record<string, unknown>> };
  provenance: { seed: number; tags: string[] };
};
export type Observation = { id: string; kind: string; data: unknown; derived_from: string[] };
export type ResultGraph = { schema_version: "1.0"; experiment_id: string; observations: Observation[] };
export const EMPTY_CURSORS: LensCursors = {
  cursorTime: null, selectedEvent: null, selectedState: null,
  selectedVoxel: null, selectedEcho: null,
};
```

- [ ] **Step 4: Implement the complete provider and shell**

```tsx
// apps/web/components/workspace/WorkspaceProvider.tsx
"use client";
import { createContext, useContext, useMemo, useState } from "react";
import { EMPTY_CURSORS, ExperimentGraph, LensCursors, ResultGraph, WorkspaceId } from "../../lib/experiment";

type ContextValue = {
  workspace: WorkspaceId; experiment: ExperimentGraph | null; result: ResultGraph | null;
  cursors: LensCursors; openWorkspace(id: WorkspaceId): void;
  setExperiment(value: ExperimentGraph | null): void; setResult(value: ResultGraph | null): void;
  setCursors(value: Partial<LensCursors>): void;
};
const Context = createContext<ContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [workspace, openWorkspace] = useState<WorkspaceId>("dashboard");
  const [experiment, setExperiment] = useState<ExperimentGraph | null>(null);
  const [result, setResult] = useState<ResultGraph | null>(null);
  const [cursors, replaceCursors] = useState(EMPTY_CURSORS);
  const value = useMemo(() => ({
    workspace, experiment, result, cursors, openWorkspace, setExperiment, setResult,
    setCursors: (next: Partial<LensCursors>) => replaceCursors(current => ({ ...current, ...next })),
  }), [workspace, experiment, result, cursors]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useWorkspace() {
  const value = useContext(Context);
  if (!value) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return value;
}
```

```tsx
// apps/web/components/workspace/WorkspaceShell.tsx
"use client";
import Link from "next/link";
import { useWorkspace } from "./WorkspaceProvider";

export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const { workspace } = useWorkspace();
  return <main className="workspace-shell">
    <nav aria-label="Workspaces">
      <Link href="/">MRQLAB</Link><span>{workspace.toUpperCase()}</span>
      <Link href="/">Explore</Link><Link href="/editor">Editor</Link><Link href="/signal-lab">Signal Lab</Link>
    </nav>
    {children}
    <p className="disclaimer">EDUCATIONAL SIMULATOR · NOT FOR CLINICAL USE · NO SCANNER HARDWARE CONNECTED</p>
  </main>;
}
```

Wrap the existing layout body with `<WorkspaceProvider><WorkspaceShell>{children}</WorkspaceShell></WorkspaceProvider>` and keep importing `./style.css`.

- [ ] **Step 5: Run workspace tests and typecheck**

Run: `cd apps/web && npm test -- workspace-provider.test.tsx && npm run typecheck`

Expected: PASS; all five cursor field names typecheck exactly.

- [ ] **Step 6: Commit PR F shell/state slice**

```bash
git add apps/web/package.json apps/web/package-lock.json apps/web/vitest.config.ts apps/web/tests apps/web/lib apps/web/components/workspace apps/web/app/layout.tsx
git commit -m "feat(web): add experiment workspace shell"
```

### Task 9 (PR F): Build Clinical Explore and the Editor Linked Lens

**Files:**
- Create: `apps/web/lib/api.ts`
- Replace: `apps/web/app/page.tsx`
- Create: `apps/web/app/editor/page.tsx`
- Create: `apps/web/components/editor/LinkedLens.tsx`
- Modify: `apps/web/app/style.css`
- Create: `apps/web/tests/explore-editor.test.tsx`

**Interfaces:**
- Consumes: `/presets`, `/experiments/run`, shared experiment/result state and cursors.
- Produces: clinical-first Explore cards, Editor cockpit, SYSTEM/PHYSICS/STATE/OBSERVATION lenses, and instrumental ratio tokens.

- [ ] **Step 1: Write failing UI contract tests**

```tsx
// apps/web/tests/explore-editor.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Home from "../app/page";
import { LinkedLens } from "../components/editor/LinkedLens";
import { WorkspaceProvider } from "../components/workspace/WorkspaceProvider";

describe("clinical Explore and Linked Lens", () => {
  it("leads with clinical questions and keeps sequence names secondary", () => {
    render(<WorkspaceProvider><Home /></WorkspaceProvider>);
    expect(screen.getByText("Dark Blood")).toBeVisible();
    expect(screen.getByText(/Uses: TSE/)).toBeVisible();
  });
  it("names all conceptual layers and exposes linked cursor controls", () => {
    render(<WorkspaceProvider><LinkedLens /></WorkspaceProvider>);
    for (const label of ["SYSTEM", "PHYSICS", "STATE", "OBSERVATION"]) expect(screen.getByText(label)).toBeVisible();
    expect(screen.getByRole("slider", { name: "Experiment time" })).toBeVisible();
  });
});
```

- [ ] **Step 2: Run tests and verify the new dashboard/editor components are absent**

Run: `cd apps/web && npm test -- explore-editor.test.tsx`

Expected: FAIL because `LinkedLens` and clinical Explore do not exist.

- [ ] **Step 3: Add typed API calls**

```ts
// apps/web/lib/api.ts
import { ExperimentGraph, ResultGraph } from "./experiment";
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export async function listPresets(): Promise<Array<{ name: string; experiment: ExperimentGraph }>> {
  const response = await fetch(`${BASE}/presets`);
  if (!response.ok) throw new Error(`presets failed: ${response.status}`);
  return (await response.json()).presets;
}
export async function runExperiment(graph: ExperimentGraph): Promise<ResultGraph> {
  const response = await fetch(`${BASE}/experiments/run`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(graph),
  });
  if (!response.ok) throw new Error(`experiment run failed: ${await response.text()}`);
  return response.json();
}
```

- [ ] **Step 4: Implement clinical Explore and Linked Lens**

```tsx
// apps/web/app/page.tsx
"use client";
import Link from "next/link";
const cards = [
  ["T1 Contrast", "Why does white matter become bright?", "Uses: IR / GRE"],
  ["Dark Blood", "Suppress flowing blood while preserving vessel wall", "Uses: TSE"],
  ["Dixon", "Separate water and fat", "Uses: multi-echo GRE · seam only"],
  ["T2 Mapping", "Estimate transverse relaxation", "Uses: multi-echo SE"],
];
export default function Home() {
  return <section className="dashboard"><header><h1>Explore · Build · Resume</h1><p>Start with a clinical or physical question.</p></header>
    <div className="explore-grid">{cards.map(([title, question, uses]) =>
      <article key={title}><h2>{title}</h2><p>{question}</p><small>{uses}</small><Link href="/editor">Explore</Link></article>
    )}</div>
  </section>;
}
```

```tsx
// apps/web/components/editor/LinkedLens.tsx
"use client";
import { useWorkspace } from "../workspace/WorkspaceProvider";
export function LinkedLens() {
  const { cursors, setCursors } = useWorkspace();
  return <section className="linked-lens">
    <header><label>Experiment time <input aria-label="Experiment time" type="range" min="0" max="100" value={cursors.cursorTime ?? 0} onChange={e => setCursors({ cursorTime: Number(e.target.value) })}/></label></header>
    <article className="system"><b>SYSTEM</b><h2>Sequence timeline</h2></article>
    <article className="physics"><b>PHYSICS</b><h2>Spin / rotating frame</h2></article>
    <article className="state"><b>STATE</b><h2>EPG pathway graph</h2></article>
    <article className="observation"><b>OBSERVATION</b><h2>Signal · k-space · image</h2></article>
  </section>;
}
```

```tsx
// apps/web/app/editor/page.tsx
"use client";
import { useEffect } from "react";
import { LinkedLens } from "../../components/editor/LinkedLens";
import { useWorkspace } from "../../components/workspace/WorkspaceProvider";
export default function EditorPage() {
  const { openWorkspace } = useWorkspace();
  useEffect(() => openWorkspace("editor"), [openWorkspace]);
  return <section className="editor-cockpit"><aside>Experiment navigator</aside><LinkedLens/><aside>SAR · duty · assumptions</aside></section>;
}
```

Add these exact tokens and layout rules to `style.css`:

```css
:root{--rail:19%;--canvas:62%;--timeline:38%;--visualization:62%;--amber:#ffc45b;--cyan:#59e0e6}
.editor-cockpit{display:grid;grid-template-columns:var(--rail) var(--canvas) var(--rail);gap:14px}
.linked-lens{display:grid;grid-template-columns:var(--timeline) var(--visualization);grid-template-areas:"header header" "system system" "physics observation" "state observation";gap:12px}
.linked-lens>article{border:1px solid #697276;background:linear-gradient(145deg,#3d4448,#181c1e);padding:16px;min-height:150px}
.linked-lens b{color:var(--amber);font:11px monospace;letter-spacing:2px}
.system{grid-area:system}.physics{grid-area:physics}.state{grid-area:state}.observation{grid-area:observation}
.explore-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}.explore-grid article{border:1px solid #697276;padding:20px;background:#202628}.explore-grid small{display:block;color:var(--cyan);margin:16px 0}
```

- [ ] **Step 5: Run UI tests, typecheck, and production build**

Run: `cd apps/web && npm test -- explore-editor.test.tsx && npm run typecheck && npm run build`

Expected: PASS; the ratios appear as tokens and no component mechanically computes `1.618`.

- [ ] **Step 6: Commit PR F Explore/Editor slice**

```bash
git add apps/web
git commit -m "feat(web): add clinical explore and linked lenses"
```

### Task 10 (PR G): Prove the Progressive TSE Refocusing-angle Teaching Chain

**Files:**
- Modify: `packages/sequence-ir/mrqlab_sequence/templates.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/observations.py`
- Create: `tests/experiment/test_tse_thesis.py`
- Create: `apps/web/components/signal-lab/TseSignalLab.tsx`
- Create: `apps/web/app/signal-lab/page.tsx`
- Create: `apps/web/tests/tse-signal-lab.test.tsx`

**Interfaces:**
- Consumes: TSE template, EPG configurations, signal, k-trajectory, shared cursors, and canonical run API.
- Produces: `refocusing_flip_angle` template parameter plus `configurations`, `echo_train`, `sar`, and image observations displayed as one causal chain.

- [ ] **Step 1: Write failing backend thesis test**

```python
# tests/experiment/test_tse_thesis.py
from mrqlab_experiment import build_preset, run_experiment
from mrqlab_experiment.observations import build_result_graph

def _run(angle):
    graph = build_preset("dark-blood-tse", {
        "te": 0.02, "tr": 0.12, "echoes": 4, "refocusing_flip_angle": angle,
    })
    graph.engine.options = {"epg_kmax": 8, "return_configurations": True}
    graph.readout.products = ("signal", "k_trajectory", "image", "configurations", "echo_train", "sar")
    return build_result_graph(run_experiment(graph))

def test_refocusing_angle_changes_every_tse_thesis_product():
    high, low = _run(180), _run(120)
    by_kind = lambda result: {item.kind: item.data for item in result.observations}
    a, b = by_kind(high), by_kind(low)
    for kind in ("configurations", "echo_train", "image", "sar"):
        assert a[kind] != b[kind]
    assert a["sar"] > b["sar"]
```

- [ ] **Step 2: Run the backend test and verify the parameter/products fail**

Run: `python3.11 -m pytest tests/experiment/test_tse_thesis.py -q`

Expected: FAIL because the template hard-codes 180° and ResultGraph does not materialize TSE teaching products.

- [ ] **Step 3: Parameterize TSE refocusing RF and materialize requested products**

In `build_sequence`, validate and use:

```python
    refocusing_flip = _finite_parameter(p, "refocusing_flip_angle", 180.0)
    if not 0 < refocusing_flip <= 180:
        raise ValueError("refocusing_flip_angle must satisfy 0 < angle <= 180")
```

Replace each appended SE/TSE refocusing value `180` with `refocusing_flip`, and add `"refocusing_flip_angle": refocusing_flip` to template metadata.

In `build_result_graph`, after the base three observations, add requested products with these exact formulas:

```python
    requested = set(run.experiment.readout.products)
    extras = []
    if "configurations" in requested and run.sim_result.configurations is not None:
        extras.append(Observation(id="configurations", kind="configurations", data=np.abs(run.sim_result.configurations).tolist(), derived_from=(signal.id,), provenance=provenance))
    if "echo_train" in requested:
        envelope = np.abs(run.sim_result.signal).tolist()
        extras.append(Observation(id="echo_train", kind="echo_train", data=envelope, axes={"echo": list(range(1, len(envelope) + 1))}, derived_from=(signal.id,), provenance=provenance))
    if "sar" in requested:
        angle = float(run.sequence.metadata.get("refocusing_flip_angle", 180.0))
        echoes = int(run.sequence.metadata.get("echoes", 1))
        sar = echoes * (angle / 180.0) ** 2
        extras.append(Observation(id="sar", kind="sar", data=sar, units={"value": "relative"}, provenance=provenance))
```

Return `observations=(signal, trajectory, image, *extras)`. This SAR value is explicitly a teaching-relative meter, not a scanner safety calculation.

- [ ] **Step 4: Add the failing Signal Lab interaction test**

```tsx
// apps/web/tests/tse-signal-lab.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TseSignalLab } from "../components/signal-lab/TseSignalLab";
import { WorkspaceProvider } from "../components/workspace/WorkspaceProvider";

describe("TSE Signal Lab", () => {
  it("shows the complete parameter-to-contrast chain", async () => {
    const run = vi.fn().mockResolvedValue({
      schema_version: "1.0", experiment_id: "tse",
      observations: [
        { id: "configurations", kind: "configurations", data: [[1]], derived_from: ["signal"] },
        { id: "echo_train", kind: "echo_train", data: [1, .8], derived_from: ["signal"] },
        { id: "image", kind: "image", data: [1, .8], derived_from: ["signal"] },
        { id: "sar", kind: "sar", data: 1.2, derived_from: [] },
      ],
    });
    render(<WorkspaceProvider><TseSignalLab run={run}/></WorkspaceProvider>);
    fireEvent.change(screen.getByRole("slider", { name: "Refocusing flip angle" }), { target: { value: "120" } });
    fireEvent.click(screen.getByText("Run teaching chain"));
    for (const label of ["EPG states", "Echo train", "k-space weighting", "Tissue contrast", "SAR 1.20"])
      expect(await screen.findByText(label)).toBeVisible();
  });
});
```

- [ ] **Step 5: Implement the Signal Lab component and route**

```tsx
// apps/web/components/signal-lab/TseSignalLab.tsx
"use client";
import { useState } from "react";
import { ResultGraph } from "../../lib/experiment";

export function TseSignalLab({ run }: { run(graph: Record<string, unknown>): Promise<ResultGraph> }) {
  const [angle, setAngle] = useState(180); const [result, setResult] = useState<ResultGraph | null>(null);
  const get = (kind: string) => result?.observations.find(item => item.kind === kind)?.data;
  async function execute() {
    setResult(await run({ preset: "dark-blood-tse", params: { refocusing_flip_angle: angle } }));
  }
  return <section className="signal-lab"><label>Refocusing flip angle
    <input aria-label="Refocusing flip angle" type="range" min="90" max="180" value={angle} onChange={event => setAngle(Number(event.target.value))}/>
    <output>{angle}°</output></label><button onClick={execute}>Run teaching chain</button>
    {result && <div className="causal-chain"><article>EPG states<pre>{JSON.stringify(get("configurations"))}</pre></article>
      <article>Echo train<pre>{JSON.stringify(get("echo_train"))}</pre></article><article>k-space weighting</article>
      <article>Tissue contrast<pre>{JSON.stringify(get("image"))}</pre></article>
      <article>SAR {Number(get("sar")).toFixed(2)}</article></div>}
  </section>;
}
```

```tsx
// apps/web/app/signal-lab/page.tsx
"use client";
import { TseSignalLab } from "../../components/signal-lab/TseSignalLab";
import { runExperiment } from "../../lib/api";
export default function SignalLabPage() {
  return <TseSignalLab run={async input => {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}/presets`);
    const presets = (await response.json()).presets;
    const graph = presets.find((item: { name: string }) => item.name === "dark-blood-tse").experiment;
    graph.sequence.params = (input as { params: Record<string, number> }).params;
    graph.engine.options = { epg_kmax: 8, return_configurations: true };
    graph.readout.products = ["signal", "k_trajectory", "image", "configurations", "echo_train", "sar"];
    return runExperiment(graph);
  }}/>;
}
```

- [ ] **Step 6: Run backend/frontend thesis gates**

Run: `python3.11 -m pytest tests/experiment/test_tse_thesis.py tests/physics/test_epg_engine.py -q && cd apps/web && npm test -- tse-signal-lab.test.tsx && npm run typecheck`

Expected: PASS; 180° and 120° produce different EPG, echo, image, and relative-SAR products.

- [ ] **Step 7: Commit PR G thesis slice**

```bash
git add packages/sequence-ir packages/mrqlab_experiment tests/experiment/test_tse_thesis.py apps/web
git commit -m "feat(signal-lab): prove TSE refocusing chain"
```

### Task 11 (PR H): Publish Agent Tool Schemas Only

**Files:**
- Create: `docs/agent-tools/experiment-tools.schema.json`
- Create: `docs/agent-tools/README.md`
- Create: `tests/experiment/test_agent_tool_schemas.py`

**Interfaces:**
- Consumes: ExperimentGraph/ResultGraph JSON schemas and canonical endpoints.
- Produces: offline JSON Schema definitions for eight tools; no agent runtime, credentials, network tools, or autonomous loop.

- [ ] **Step 1: Write the failing schema contract test**

```python
# tests/experiment/test_agent_tool_schemas.py
import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
def test_agent_schema_names_tools_and_graph_contract():
    schema = json.loads((ROOT / "docs/agent-tools/experiment-tools.schema.json").read_text())
    names = {item["allOf"][1]["properties"]["name"]["const"] for item in schema["oneOf"]}
    assert names == {
        "inspect_experiment", "inspect_signal", "compare_tissues", "run_simulation",
        "run_optimization", "explain_epg_pathway", "suggest_parameters", "find_failure_mode",
    }
    assert schema["$defs"]["experimentGraph"]["properties"]["schema_version"]["const"] == "1.0"
```

- [ ] **Step 2: Run the test and verify the schema file is absent**

Run: `python3.11 -m pytest tests/experiment/test_agent_tool_schemas.py -q`

Expected: FAIL with `FileNotFoundError`.

- [ ] **Step 3: Create the complete tool schema document**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://mrqlab.local/schemas/experiment-tools.schema.json",
  "$defs": {
    "experimentGraph": {
      "type": "object",
      "required": ["schema_version", "id", "name", "nodes", "edges", "sequence", "sample", "scanner", "engine", "readout", "constraints", "disturbances", "provenance"],
      "properties": { "schema_version": { "const": "1.0" }, "id": { "type": "string" }, "name": { "type": "string" } },
      "additionalProperties": true
    },
    "tool": {
      "type": "object",
      "required": ["name", "input", "side_effect"],
      "properties": {
        "name": { "type": "string" },
        "input": { "type": "object" },
        "side_effect": { "enum": ["read", "compute"] }
      },
      "additionalProperties": false
    }
  },
  "oneOf": [
    { "allOf": [{ "$ref": "#/$defs/tool" }, { "properties": { "name": { "const": "inspect_experiment" }, "side_effect": { "const": "read" } } }] },
    { "allOf": [{ "$ref": "#/$defs/tool" }, { "properties": { "name": { "const": "inspect_signal" }, "side_effect": { "const": "read" } } }] },
    { "allOf": [{ "$ref": "#/$defs/tool" }, { "properties": { "name": { "const": "compare_tissues" }, "side_effect": { "const": "compute" } } }] },
    { "allOf": [{ "$ref": "#/$defs/tool" }, { "properties": { "name": { "const": "run_simulation" }, "side_effect": { "const": "compute" } } }] },
    { "allOf": [{ "$ref": "#/$defs/tool" }, { "properties": { "name": { "const": "run_optimization" }, "side_effect": { "const": "compute" } } }] },
    { "allOf": [{ "$ref": "#/$defs/tool" }, { "properties": { "name": { "const": "explain_epg_pathway" }, "side_effect": { "const": "read" } } }] },
    { "allOf": [{ "$ref": "#/$defs/tool" }, { "properties": { "name": { "const": "suggest_parameters" }, "side_effect": { "const": "read" } } }] },
    { "allOf": [{ "$ref": "#/$defs/tool" }, { "properties": { "name": { "const": "find_failure_mode" }, "side_effect": { "const": "read" } } }] }
  ]
}
```

`docs/agent-tools/README.md` must state: schemas describe tools over `ExperimentGraph`; `run_optimization` is reserved until an optimizer plugin exists; no runtime agent ships; every compute tool calls canonical experiment services; and the simulator remains offline-capable.

- [ ] **Step 4: Run schema and offline-boundary tests**

Run: `python3.11 -m pytest tests/experiment/test_agent_tool_schemas.py -q && rg -n "openai|anthropic|langchain|httpx" packages/mrqlab_experiment`

Expected: schema test PASS; the search returns no agent SDK or network-runtime imports.

- [ ] **Step 5: Commit PR H schemas-only slice**

```bash
git add docs/agent-tools tests/experiment/test_agent_tool_schemas.py
git commit -m "docs(agent): publish experiment tool schemas"
```

### Task 12 (Acceptance): Update Architecture Docs and Run the Full Gate

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/PHYSICS.md`
- Modify: `docs/ROADMAP.md`
- Modify: `README.md`
- Create: `tests/experiment/test_experiment_docs.py`

**Interfaces:**
- Consumes: all A–H contracts and ADRs.
- Produces: public architecture/physics/roadmap narrative and a final regression record.

- [ ] **Step 1: Write the failing documentation contract test**

```python
# tests/experiment/test_experiment_docs.py
from pathlib import Path
ROOT = Path(__file__).parents[2]

def test_architecture_names_locked_contracts_and_boundaries():
    text = (ROOT / "docs/ARCHITECTURE.md").read_text()
    for required in (
        "ExperimentGraph", "PhysicsOperator", "StateRepresentation", "ObjectiveFunction", "Observation",
        "Experiment IR", "Sequence Compiler", "Sequence IR", "Physics Compiler", "Physics IR",
        "ONE Python process", "packages/mrqlab_experiment", "/experiments/run", "/simulate",
    ):
        assert required in text

def test_roadmap_holds_mvp_scope():
    text = (ROOT / "docs/ROADMAP.md").read_text()
    assert "SE" in text and "GRE" in text and "TSE" in text
    assert "Do not implement Floquet/CEST/MRS/DCE in v0.1" in text
```

- [ ] **Step 2: Run the docs test and verify the old narrative fails**

Run: `python3.11 -m pytest tests/experiment/test_experiment_docs.py -q`

Expected: FAIL because the existing docs still center `SequenceIR` and `SimulationEngine`.

- [ ] **Step 3: Apply the exact documentation content map**

```markdown
# docs/ARCHITECTURE.md required section order
1. Product thesis and Experiment equation
2. Five stable contracts
3. Three-layer IR diagram
4. Kernel responsibilities and exclusions
5. Capability matrix; representation versus operator
6. Observation/ResultGraph and provenance
7. Disturbance Stack and reselection
8. Workspace shell, Linked Lens, and shared cursors
9. Modular monolith and incremental packages/mrqlab_experiment → core target
10. Compatibility API and offline agent-tool boundary
```

```markdown
# docs/PHYSICS.md required additions
- EPG/EPG-X/ssEPG are forward models; optimizer plugins own inverse search.
- Bloch/EPG/PDG/density matrix are representations; RF/Relax/Shift/Exchange/etc. are operators.
- ssEPG uses dedicated compiler spans; PDG bridges pathways and spatial image formation.
- MRS base is density matrix + Liouville–von Neumann; Floquet is an accelerator/steady-state solver.
- Capability table for Bloch, EPG, Spectral, future ssEPG, EPG-X, PDG, and density matrix.
```

```markdown
# docs/ROADMAP.md required release statements
- v0.1: SE timeline ↔ Bloch ↔ signal ↔ image.
- v0.1: GRE gradient ↔ k-space ↔ contrast.
- v0.1 thesis: TSE refocusing FA ↔ EPG ↔ echo train ↔ k-space weighting ↔ contrast + relative SAR.
- Do not implement Floquet/CEST/MRS/DCE in v0.1.
- Waves A–H follow the plan; AI Lab runtime is last.
```

Add README links to the locked spec, implementation plan, ADR directory, canonical `/experiments/*` API, and `/simulate` compatibility note.

- [ ] **Step 4: Run the full Python acceptance suite**

Run:

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/python -m pytest -q
```

Expected: all existing physics/API tests and all new experiment tests pass; SE/GRE/TSE numerical paths remain green.

- [ ] **Step 5: Run the full web acceptance suite**

Run: `cd apps/web && npm ci && npm test && npm run typecheck && npm run build`

Expected: PASS; Dashboard, Editor, and Signal Lab compile as one Next.js application.

- [ ] **Step 6: Run static architecture and anti-scope checks**

Run:

```bash
rg -n "class (SpinEcho|TurboSpinEcho|CEST|ASL).*Sequence|class AdvancedSimulator" packages services
rg -n "Floquet|CEST|MRS|DCE" packages/mrqlab_experiment apps/web services/api
rg -n "FastAPI\(" services apps packages
git status --short
```

Expected: first search has no matches; second search contains only explicit unavailable/seam copy and no implementation modules; exactly one FastAPI application exists; status contains only files from the current implementation task.

- [ ] **Step 7: Commit documentation and acceptance gates**

```bash
git add README.md docs/ARCHITECTURE.md docs/PHYSICS.md docs/ROADMAP.md tests/experiment/test_experiment_docs.py
git commit -m "docs: publish experiment kernel architecture"
```

## Self-Review Against the Locked Spec

### 1. Spec coverage

| Locked requirement | Implemented by |
|---|---|
| Five exact contracts | Stable interfaces; Tasks 1, 3, 5, 6; Task 12 docs gate |
| Three-layer IR | Tasks 1 and 4; ADR-0002 |
| EPG is forward; optimizer + Objective own inverse | Task 6; ADR-0003; no search runtime |
| Representation ≠ operator | Tasks 3–4; docs gate |
| Capability matrix, no inheritance tree | Task 3 |
| ssEPG own compiler spans | Task 4 vocabulary and unavailable capability path |
| Floquet accelerator; density-matrix MRS base | Spec/ADR/docs seam only |
| PDG bridge | Capability explanation and docs seam only |
| Disturbance Stack and engine reselection | Task 7 |
| Workspace shell + clinical Explore | Tasks 8–9 |
| Editor Linked Lens + shared cursors | Tasks 8–9 |
| Instrumental skeuomorphism and ratio tokens | Task 9 |
| AI Lab last; tools over ExperimentGraph; offline core | Task 11 |
| Modular monolith and incremental migration | Tasks 1–2 and 12; ADR-0005 |
| `/simulate` compatibility and canonical experiment API | Tasks 2 and 5 |
| SE/GRE/TSE MVP hold line | Tasks 1–5 preserve SE/GRE; Task 10 proves TSE |
| PR Plan → A–H split | PR Wave Map and Tasks 1–11 |

Coverage result: every locked requirement maps to a task or to an explicit seam-only ADR. Floquet, CEST, MRS, and DCE have no MVP implementation task.

### 2. Placeholder scan

Every implementation step includes concrete signatures, field names, assertions, commands, expected results, and commit scope. Deferred physics appears only as explicit unavailable capability records and documentation seams; there are no unfinished implementation markers or instructions to infer missing behavior.

### 3. Type consistency

- `ExperimentGraph` remains schema `1.0` and is the request type for both canonical endpoints.
- `compile_sequence` always returns the existing `SequenceIR`.
- `compile_physics_ir` consumes that `SequenceIR` plus `EngineOptions` and returns `PhysicsIR` schema `1.0`.
- `StateRepresentation.supports` and `EngineRef.required_capabilities` are both `frozenset[str]`.
- `run_experiment` always returns `KernelRun`; only `build_result_graph` converts it to `ResultGraph`.
- `Observation.derived_from`, `ResultEdge`, and observation ids use the same string identifiers.
- Objective evaluation consumes signal/echo products and returns only a scalar score; it exposes no optimizer method.
- `DisturbanceStack` is typed once in `disturbances.py` and imported by `models.py`.
- TypeScript uses the exact five cursor names and consumes the same `1.0` wire versions.
- `/simulate` uses `_legacy_response`; `/experiments/run` returns `ResultGraph`.

## Execution Handoff — Stop and Wait for the User

Plan implementation must not begin from the planning branch. After this docs-only plan is reviewed, wait for the user to choose one option:

1. **Open plan PR** — create a documentation-only pull request for the plan, locked spec, and ADRs.
2. **开工: litellm subagents** — use fresh litellm subagents task-by-task with review gates; Codex retains global plan and final review.
3. **Codex executing-plans** — use the required `superpowers:executing-plans` skill and execute in batches with checkpoints.

No origin push or product-code implementation is authorized by this plan.
