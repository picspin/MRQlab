# Experiment Kernel Locked Specification

**Status:** Locked for implementation
**Date:** 2026-08-15
**Scope:** MRQLab v0.1 experiment-kernel elevation
**Supersedes:** A `SimulationEngine`-centered product model. The existing physics microkernel remains the numerical execution substrate.

## Product Thesis

Form a hypothesis → design an MR experiment → understand state evolution → observe consequence → optimize toward a clinical/physical objective.

The product center is an experiment, not a simulator class or sequence class:

```text
Experiment
  = Sequence
  + Spin/Tissue (Sample)
  + Scanner
  + Physics Engine
  + Objective
  + Readout
```

SE, GRE, and TSE remain named presets that build graphs. They do not become parallel domain-model roots.

## Five Stable Kernel Contracts

These exact names are normative:

1. `ExperimentGraph` — the experiment structure above scanner events.
2. `PhysicsOperator` — an action with `apply(state, event, context) -> state` semantics.
3. `StateRepresentation` — the state domain propagated by operators.
4. `ObjectiveFunction` — a forward score and future optimization target with explicit constraints.
5. `Observation` — a typed, versioned product derived from a run.

`SequenceIR` remains necessary and authoritative for scanner-level channels, but is subordinate to `ExperimentGraph`.

## Required Architecture

### Three-layer IR

```text
Experiment IR
    ↓  Sequence Compiler
Sequence IR
    ↓  Physics Compiler
Physics IR
    ↓
StateRepresentation + PhysicsOperator
    ↓
Observation
```

- Experiment IR preserves user and clinical meaning.
- Sequence IR preserves scanner event meaning and the existing eight-channel `SequenceIR` DNA.
- Physics IR is a versioned typed operator stream compiled from scheduled events.
- A compiler may emit representation spans such as `BlochSpan`, `EPGSpan`, and, later, `PDGSpan`; ssEPG must receive its own path rather than an EPG feature flag.

### ExperimentGraph v0

`packages/mrqlab_experiment` is the first implementation location. `core/experiment` is the documented target name after incremental migration; there is no big-bang package move.

The v0 graph contains:

```text
Node kinds: RF | GRADIENT | DELAY | ADC | READOUT | LOOP
Reserved node kinds: PREPARATION | EXCHANGE | FLOW | DIFFUSION | INJECTION
Edge kinds: TEMPORAL | DEPENDENCY | STATE_TRANSITION
```

Only active v0 node kinds may be instantiated. Reserved kinds are present in the schema vocabulary but validation refuses their execution with explicit errors.

Each graph carries a `sequence` source (`SequenceIR` or template reference), a sample, scanner, engine preference, objective, readout selection, constraints, disturbance stack, and provenance hints. SE/GRE/TSE presets compile existing templates into this graph.

### Physics IR v0

Physics IR formalizes the existing scheduler output without changing numerical behavior:

```text
PhysicsIR(schema_version="1.0", representation, operators, compiler_spans)
```

Its operator variants correspond to the existing `RfOp`, `Relax`, `Shift`, `GradInterval`, and `AdcSample`. This wave adds public protocol vocabulary and capability metadata; it does not rewrite operator mathematics.

## Physics Semantics

### Representation is not operator

State representations include Bloch, EPG, PDG, ssEPG, and density matrix. Operators include RF, relaxation, gradient/shift, exchange, diffusion, flow, off-resonance, and chemical shift. No `BaseSimulator → AdvancedSimulator` inheritance tree is allowed.

EPG-X means an EPG state with exchange operators. PDG bridges abstract EPG pathways and spatial Bloch/image formation. ssEPG requires dedicated compiler spans. The future MRS base is density-matrix and Liouville–von Neumann propagation; Floquet is only a future `PeriodicSequenceAccelerator` or `SteadyStateSolver`.

### Capability negotiation

Every representation/engine descriptor exposes a set drawn from this stable vocabulary:

```text
hard_rf | shaped_rf | exchange | diffusion | flow | off_resonance
spatial_encoding | steady_state | differentiable | multi_pool | multi_species
configuration_states | magnetization_states
```

Selection is set inclusion over required capabilities. Missing capabilities fail closed. Engine selection may be explained to the UI, and a disturbance change may recommend or require a different representation.

### EPG is forward

EPG, EPG-X, and ssEPG are forward models. Inverse design is an optimizer plugin evaluating an `ObjectiveFunction` over repeated forward runs:

```text
theta* = argmin_theta ObjectiveFunction(Observation(engine(graph, theta)))
```

Grid, Bayesian, and CMA-ES are planned non-differentiable optimizers. Differentiable EPG and Adam/LBFGS are later work. No optimizer is hidden inside EPG or AI Lab.

## Observation and ResultGraph

`Observation` is a discriminated, JSON-ready record with:

```text
id, kind, schema_version, data, axes, units, derived_from, provenance
```

v0 kinds are `signal`, `k_trajectory`, `image`, `magnetization`, `configurations`, `echo_train`, `sar`, and `objective_score`. `spectrum` is reserved but not implemented in this MVP wave. `ResultGraph` contains observations plus explicit `derived_from`, `engine`, and `recon` edges.

The experiment kernel wraps the existing `SimResult`; it does not alter `SimulationEngine.simulate(SequenceIR, Phantom, ScannerModel, EngineOptions) -> SimResult`. `/simulate` remains a compatibility endpoint and uses the same wrapper as the canonical `/experiments/run` endpoint.

Every run records a stable schema version, experiment hash, selected engine and representation, assumptions, compiler versions, seed, work estimate, and timing.

## ObjectiveFunction v0

An objective is data, not an optimizer:

```text
ObjectiveFunction(
  kind="contrast_target",
  terms=[weighted signal targets],
  constraints=[scan_time and SAR upper bounds],
)
```

v0 evaluates scalar scores from existing observations. It supports `contrast_target` and `null`. It records constraints but provides no search algorithm. Later optimizers consume the same contract and should expose candidates and Pareto trade-offs, not only one answer.

## Disturbance Stack

The Reality Slider becomes optional UX sugar over an ordered `DisturbanceStack`. A disturbance contains `id`, `kind`, `domain`, `enabled`, and typed parameters. v0 implements the schema, validation, deterministic slider mapping, capability requirements, and selection explanation. It does not implement disturbance physics.

The stable kinds are:

```text
thermal_noise | b0_map | b1_map | gradient_delay | eddy_current
gradient_nonlinearity | motion | flow | diffusion | exchange
susceptibility | coil_sensitivity | adc_imperfection | slice_profile
```

Teaching examples are normative:

```text
TSE ideal             → EPG
+ slice_profile       → ssEPG recommendation (unavailable in v0)
+ exchange            → EPG-X/hybrid recommendation (unavailable in v0)
+ spatial b0_map      → PDG recommendation (provider seam only)
```

Unavailable physics must be reported explicitly; the kernel must not silently fall back to a physically incomplete result.

## Backend Deployment and Repository Shape

The deployed v1 shape is a modular monolith:

```text
ONE Python process: experiment kernel + physics engines + recon + optimization ports + FastAPI
ONE Next.js application
```

Microkernel describes in-process code boundaries, not microservices. Job schedulers and GPU workers are considered only when workloads require them.

The five-year target layout is:

```text
core/{experiment,sequence,sample,scanner,operators,objectives,results,provenance}
engines/{bloch,epg,pdg,ssepg,bloch_mcconnell,density_matrix}
accelerators/{floquet,differentiable,gpu}
disturbances/{b0,b1,noise,motion,flow,diffusion,eddy_current}
optimization/{grid,bayesian,evolutionary,gradient}
recon/{fft,nufft,sense}
adapters/{pulseq,ismrmrd,marcos}
plugins/{cases,experiments,tissues}
packages/{schemas,units,protocol}
```

Implementation begins in `packages/mrqlab_experiment`, preserves `packages/sequence-ir`, `packages/physics`, `packages/recon`, and `services/api`, and uses re-exports during any later rename.

## API Contract

- Keep `POST /simulate` compatible indefinitely.
- Keep `POST /sequences/build`, `GET /engines`, and `GET /health`.
- Add canonical `POST /experiments/validate` and `POST /experiments/run`.
- Add `GET /presets` for clinical-first Explore cards.
- `/simulate` creates an implicit null-objective experiment and calls the same application service used by `/experiments/run`.
- Validation errors use stable codes for invalid graph, unsupported node, capability mismatch, unavailable representation, constraint violation, and invalid observation request.

## Frontend Contract

The frontend is a workspace shell with microfrontend-style feature folders sharing one experiment state. The shell owns routing, workspace selection, experiment state, undo/redo, persistence, plugin registration, and the command palette.

Required v0 workspaces are Dashboard Explore, Editor, and Signal Lab. Contrast Lab, Optimization Lab, and AI Lab remain registered future routes only.

- Dashboard Explore is clinical-first: T1 Contrast, Dark Blood, Dixon, and T2 Mapping cards; sequence names are secondary `Uses:` text.
- Editor uses instrumental skeuomorphism: real parameter controls, waveform scope, SAR/duty meters, and state observers. Decorative fake hardware is excluded.
- Golden ratio values are design tokens (`19% | 62% | 19%`, `38% | 62%`), not a universal mechanical ratio.
- Linked Lens defaults to Sequence above Physics and Observation. A focused state lens may expand EPG/PDG state.
- Shared cursors are named exactly `cursorTime`, `selectedEvent`, `selectedState`, `selectedVoxel`, and `selectedEcho`.
- The four conceptual copy labels are SYSTEM, PHYSICS, STATE, and OBSERVATION.

The TSE Signal Lab must demonstrate:

```text
drag refocusing FA
  → EPG states change
  → echo train changes
  → k-space weighting changes
  → tissue contrast changes
  → SAR meter changes
```

## AI Boundary

AI Lab is last. This wave publishes schemas only for tools over `ExperimentGraph`:

```text
inspect_experiment | inspect_signal | compare_tissues | run_simulation
run_optimization | explain_epg_pathway | suggest_parameters | find_failure_mode
```

No runtime agent and no network dependency are introduced. The simulator core remains offline-capable.

## MVP Scope

v0.1 proves only:

- SE: timeline ↔ Bloch ↔ signal ↔ image.
- GRE: gradient ↔ k-space ↔ contrast.
- TSE: refocusing train ↔ EPG states ↔ echo train ↔ k-space weighting ↔ tissue contrast, with a SAR meter.

Floquet, CEST, MRS, and DCE receive vocabulary and ADR seams only. There are no implementation tasks for their physics, UI workflows, or optimizer paths in this plan.

## Delivery Waves

1. Plan: locked spec, implementation plan, and five ADRs.
2. A: `ExperimentGraph`, presets, compiler façade, application service, and canonical APIs.
3. B: `PhysicsOperator`, `StateRepresentation`, capability negotiation, and typed Physics IR.
4. C: `Observation`, `ResultGraph`, serialization, and provenance.
5. D: `ObjectiveFunction` v0 and forward scores.
6. E: `DisturbanceStack` schema, slider mapping, and engine-reselection explanations.
7. F: Workspace shell, clinical Explore, Editor Linked Lens, and shared cursors.
8. G: Progressive TSE refocusing-angle Signal Lab chain and SAR meter.
9. H: Agent tool JSON schemas only.

## Acceptance Criteria

- The five contracts appear with their exact names in schemas, docs, and tests.
- Experiment → Sequence → Physics IR boundaries are explicit and versioned.
- Existing SE/GRE/TSE numerical tests remain green.
- Capability mismatch and reserved graph nodes fail closed.
- `/simulate` and `/experiments/run` share one execution path.
- ResultGraph wraps current `SimResult` and contains typed provenance.
- Objective v0 scores an observation but contains no optimizer loop.
- Disturbance changes can explain a required representation change.
- Dashboard, Editor, and Signal Lab share one typed state and shared cursors.
- The TSE thesis chain is covered by API, state, and UI tests.
- No Floquet/CEST/MRS/DCE implementation, microservice split, runtime agent, or mandatory network service is introduced.

## Non-goals

- Scanner control, MaRCoS/Red Pitaya acquisition, or safety certification.
- Clinical diagnostic claims.
- A sequence-class hierarchy.
- A simulator inheritance hierarchy.
- Full optimizer algorithms or differentiable physics.
- Floquet, CEST, MRS, DCE, ssEPG, EPG-X, or built-in PDG physics in v0.1.
- Microservices, job queues, or GPU workers.

