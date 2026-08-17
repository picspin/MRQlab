# Architecture

## 1. Product thesis and Experiment equation

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

SE, GRE, and TSE are named presets that build an `ExperimentGraph`. They are not parallel domain-model roots. The existing physics microkernel remains the numerical execution substrate.

## 2. Five stable contracts

These exact names are normative:

1. `ExperimentGraph` — the experiment structure above scanner events.
2. `PhysicsOperator` — an action with `apply(state, event, context) -> state` semantics.
3. `StateRepresentation` — the state domain propagated by operators.
4. `ObjectiveFunction` — a forward score and future optimization target with explicit constraints.
5. `Observation` — a typed, versioned product derived from a run.

`SequenceIR` remains authoritative for scanner-level channels, but is subordinate to `ExperimentGraph`. Named sequences are presets, not subclasses of a common sequence base. See [ADR-0001](adr/ADR-0001-five-kernel-contracts.md).

## 3. Three-layer IR diagram

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
- Sequence IR preserves scanner event meaning and the existing eight-channel `SequenceIR` DNA (`rf_amp`, `rf_phase`, `gx`, `gy`, `gz`, `adc_gate`, `nco_freq`, `nco_phase`).
- Physics IR is a versioned typed operator stream compiled from scheduled events.

A compiler may emit representation spans such as `BlochSpan` and `EPGSpan`. ssEPG receives its own path rather than an EPG feature flag. See [ADR-0002](adr/ADR-0002-three-layer-ir.md).

## 4. Kernel responsibilities and exclusions

The experiment kernel in `packages/mrqlab_experiment` owns:

- graph construction, validation, and presets
- Sequence Compiler (`Experiment IR → Sequence IR`)
- Physics Compiler vocabulary (`Physics IR` records and spans)
- capability negotiation and representation selection
- `Observation` / `ResultGraph` assembly and provenance
- `ObjectiveFunction` v0 scalar evaluation
- `DisturbanceStack` schema, slider mapping, and reselection explanation

The kernel does **not** own Bloch/EPG mathematics, recon algorithms, optimizer search, or UI. Numerical physics stays in `packages/physics`. Recon stays in `packages/recon`. `SimulationEngine.simulate(SequenceIR, Phantom, ScannerModel, EngineOptions) -> SimResult` is wrapped, not rewritten.

## 5. Capability matrix; representation versus operator

Representation is not operator. Bloch, EPG, PDG, ssEPG, and density matrix are representations. RF, relaxation, gradient/shift, exchange, diffusion, flow, off-resonance, and chemical shift are operators. There is no `BaseSimulator → AdvancedSimulator` inheritance tree.

Every representation/engine descriptor exposes a set drawn from:

```text
hard_rf | shaped_rf | exchange | diffusion | flow | off_resonance
spatial_encoding | steady_state | differentiable | multi_pool | multi_species
configuration_states | magnetization_states
```

Selection is set inclusion over required capabilities. Missing capabilities fail closed.

| Representation | Available in v0.1 | Supports | Role |
|---|---|---|---|
| Bloch | yes | hard_rf, off_resonance, spatial_encoding, magnetization_states | SE/GRE Cartesian magnetization |
| EPG | yes | hard_rf, configuration_states, steady_state | TSE/CPMG echo trains |
| Spectral | yes | hard_rf, off_resonance, multi_pool, magnetization_states | Independent fat/water pools |
| ssEPG | no | hard_rf, shaped_rf, configuration_states, spatial_encoding | Dedicated future slice-selective path |
| EPG-X | no | hard_rf, configuration_states, exchange, multi_pool | EPG state plus exchange operators |
| PDG | no | hard_rf, configuration_states, spatial_encoding, off_resonance | Pathway ↔ spatial image bridge |
| Density matrix | no | (future MRS base) | Liouville–von Neumann propagation |

## 6. Observation/ResultGraph and provenance

`Observation` is a discriminated, JSON-ready record: `id`, `kind`, `schema_version`, `data`, `axes`, `units`, `derived_from`, `provenance`.

v0 kinds are `signal`, `k_trajectory`, `image`, `magnetization`, `configurations`, `echo_train`, `sar`, and `objective_score`. `ResultGraph` contains observations plus explicit `derived_from`, `engine`, and `recon` edges.

`build_result_graph` emits **exactly** the products listed in `ReadoutSpec.products`, in that order. Unknown products fail closed. Provenance records experiment hash, selected engine, selected representation, assumptions, seed, and work estimate.

The kernel wraps existing `SimResult`. `/simulate` remains a compatibility endpoint and uses the same application service as canonical `/experiments/run`.

## 7. Disturbance Stack and reselection

The Reality Slider is UX sugar over a typed `DisturbanceStack`. Each disturbance has identity, kind, domain, enabled state, parameters, and required capabilities. See [ADR-0004](adr/ADR-0004-disturbance-stack.md).

Teaching examples:

```text
TSE ideal             → EPG
+ slice_profile       → ssEPG recommendation (unavailable in v0)
+ exchange            → EPG-X/hybrid recommendation (unavailable in v0)
+ spatial b0_map      → PDG recommendation (provider seam only)
```

Unavailable physics is reported explicitly. The kernel does not silently fall back to a physically incomplete result.

## 8. Workspace shell, Linked Lens, and shared cursors

The Next.js application is a workspace shell. Dashboard Explore, Editor, and Signal Lab share one experiment state.

- Explore is clinical-first: cards lead with contrast intent; sequence names are secondary `Uses:` text.
- Editor uses Linked Lens (SYSTEM / PHYSICS / STATE / OBSERVATION).
- Shared cursors are named exactly `cursorTime`, `selectedEvent`, `selectedState`, `selectedVoxel`, and `selectedEcho`.
- Signal Lab proves the TSE teaching chain: refocusing FA → EPG states → echo train → k-space weighting → tissue contrast → SAR.

Golden-ratio values are design tokens, not a universal mechanical ratio.

## 9. Modular monolith and incremental packages/mrqlab_experiment → core target

Deployed v1 shape:

```text
ONE Python process: experiment kernel + physics engines + recon + optimization ports + FastAPI
ONE Next.js application
```

Microkernel describes in-process code boundaries, not microservices. Implementation begins in `packages/mrqlab_experiment` and wraps existing `packages/sequence-ir`, `packages/physics`, `packages/recon`, and `services/api`. `core/` is the documented target rename, reached incrementally with re-export shims. See [ADR-0005](adr/ADR-0005-modular-monolith.md).

## 10. Compatibility API and offline agent-tool boundary

- Keep `POST /simulate` compatible indefinitely.
- Canonical endpoints are `POST /experiments/validate` and `POST /experiments/run`.
- `GET /presets` feeds clinical Explore cards.
- `/simulate` builds an implicit experiment and calls the same service as `/experiments/run`.

AI Lab is last. This wave publishes schemas only for tools over `ExperimentGraph` (`docs/agent-tools/`). No runtime agent and no network dependency are introduced. The simulator core remains offline-capable.
