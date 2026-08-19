# Experiment Kernel v0.1 Retrospective

**Date:** 2026-08-17  
**Tree:** `feature/experiment-kernel-docs` @ `bc12018` on `origin/main` @ `7229f1a` (PR #12 H merged)  
**Gate:** pytest 142 passed · web 4 passed · typecheck · build · anti-scope clean  
**Independent dual-axis:** dispatched (spec + standards, `code1-gpt-5.5`)

Task 12 (Acceptance docs) is implemented and pushed, **not yet on `main`**.

---

## What landed (plan map)

| Wave | PR | Commit / merge | Scope |
|---|---|---|---|
| Plan | #4 | docs/spec/ADRs | lock |
| A | #5 | ExperimentGraph, presets, compiler, `/experiments/*` | Tasks 1–2 |
| B | #6 | capabilities + Physics IR vocabulary | Tasks 3–4 |
| C | #7 | Observation / ResultGraph | Task 5 |
| D | #8 | ObjectiveFunction v0 | Task 6 |
| E | #9 | DisturbanceStack | Task 7 |
| 7.5 | #10 | ExecutionPlan, copy-on-resolve, exact products | hardening |
| F | #11 | Workspace shell, Explore, Linked Lens | Tasks 8–9 |
| G | (in #12 stack) `00dea9e` | TSE FA + configurations/echo_train/sar + Signal Lab | Task 10 |
| H | #12 | agent tool JSON schemas | Task 11 |
| Acceptance | docs branch `bc12018` | ARCHITECTURE / PHYSICS / ROADMAP / README | Task 12 |

---

## Acceptance vs live tree

| # | Criterion | Verdict | Evidence |
|---|---|---|---|
| 1 | Five contract names in schemas, docs, tests | **PASS** | `ExperimentGraph`, `PhysicsOperator`, `StateRepresentation`, `ObjectiveFunction`, `Observation` present. Nit: `PhysicsOperator` not in `__all__`. |
| 2 | Experiment → Sequence → Physics IR explicit + versioned | **PASS-WITH-NITS** | `schema_version="1.0"` on graph / PhysicsIR / ResultGraph. `compile_physics_ir` exists but is **not** on `run_experiment` path. |
| 3 | SE/GRE/TSE numerical tests green | **PASS** | pytest 142. |
| 4 | Capability mismatch + reserved nodes fail closed | **PASS** | `test_capabilities.py`, `test_graph_compiler.py`. |
| 5 | `/simulate` and `/experiments/run` share one path | **PASS** | both call `run_experiment`. `/simulate` → `_legacy_response`. |
| 6 | ResultGraph wraps SimResult + typed provenance | **PASS-WITH-NITS** | wrap + provenance from plan. `derived_from` / `recon` edges exist. **`kind="engine"` edges never emitted.** |
| 7 | Objective v0 scores, no optimizer | **PASS** | `evaluate_objective` scalar only. No search imports. |
| 8 | Disturbance explains reselection | **PASS** | `slice_profile` → `unavailable_representation` / `EPG → ssEPG`. |
| 9 | Dashboard / Editor / Signal Lab share typed state + cursors | **PASS-WITH-NITS** | `WorkspaceProvider` + five cursor names. No undo / redo / persistence / command palette. Linked Lens is labels. Explore cards do not load presets. |
| 10 | TSE thesis covered by API, state, UI tests | **PASS-WITH-NITS** | `test_tse_thesis.py` is a real backend delta. UI test is mocked. `k-space weighting` is an empty label. `echo_train` = `abs(signal)`; `sar` = relative `echoes * (FA/180)²`. |
| 11 | No Floquet/CEST/MRS/DCE, no microservice, no runtime agent | **PASS** | `rg` clean. One `FastAPI(`. Schemas only. |

**Program verdict: PASS-WITH-NITS.** v0.1 hold line is met. Do not open a new feature wave to “finish” nits.

---

## Architecture that actually shipped

```text
ExperimentGraph
    → compile_sequence (reserved-node gate + SequenceIR / TemplateRef)
    → plan_experiment (capabilities ∪ disturbances → ExecutionPlan)
    → get_engine(plan.engine).simulate(SequenceIR, Phantom, Scanner, Options)
    → KernelRun(deep-copied graph, sequence, SimResult, plan)
    → build_result_graph (exactly readout.products)

/simulate  = implicit graph + same run_experiment + legacy JSON
/experiments/run = copy-on-resolve + snapshot flags only if product requested
```

This is a **façade kernel**, not a new physics stack. Correct for ADR-0001 / wrap-not-rewrite.

Three-layer IR is **documented and compile-able**, not **executed**. Physics IR is a typed recording of the existing scheduler. Numerical path still consumes `SequenceIR` directly. That is the honest architecture, and docs should keep saying so.

---

## What worked

1. Spec-driven + TDD + one-wave-one-PR kept the five names stable.
2. 7.5 was the right mid-program hardening: ExecutionPlan, no request aliasing, exact products. Without it Wave G would have been theatre.
3. Fail-closed seams (ssEPG / EPG-X / PDG / reserved nodes / reserved objective terms) held. No invented physics.
4. `/simulate` compatibility survived the elevation.
5. Anti-scope held: no Sequence class tree, no AdvancedSimulator, one process.

---

## What drifted (honest)

1. **Graph is metadata, not the compiler input.** Active nodes/edges do not drive `compile_sequence`. Templates / `SequenceIR` do. Spec allowed this for v0; it is now the largest conceptual gap.
2. **Physics IR is a sidecar.** `run_experiment` never calls `compile_physics_ir`.
3. **Frontend is a routing shell, not a workspace product.** Cursors exist; lenses do not project ResultGraph; Explore does not bind presets; Signal Lab mutates a fetched preset in place (`app/signal-lab/page.tsx`).
4. **Thesis products are teaching proxies.** `echo_train` is `|signal|`; `sar` is metadata-relative. Fine for v0 if docs stay explicit.
5. **UI tests do not hit the kernel.** Backend thesis test does.

---

## Backlog (parked hardening — not the next feature wave)

Do **not** absorb these into an unplanned Task 13 unless asked.

### P1 — contract honesty

| ID | Item | Why |
|---|---|---|
| B1 | Invoke `compile_physics_ir` on the run path (or record the IR on `KernelRun`) so the three-layer claim is executable | Spec § three-layer IR |
| B2 | Emit `ResultEdge(kind="engine")` or drop that vocabulary from docs | Spec Observation/ResultGraph |
| B3 | Export `PhysicsOperator` from `mrqlab_experiment.__all__` | Task 12 name gate |
| B4 | Merge Task 12 docs PR | Acceptance not on `main` |

### P1 — 7.5 leftovers still true

| ID | Item |
|---|---|
| B5 | `validate_experiment` = compile + capabilities only; nested isochromats/pools can validate then fail on run |
| B6 | `SampleSpec` accepts non-finite floats |
| B7 | `constraints.matrix` enforced only in API |
| B8 | Nodes/edges (except reserved kinds) do not compile |
| B9 | No repo-wide `frozen=True` |
| B10 | Duplicate `readout.products` ids allowed |
| B11 | `ObjectiveTerm.observation="echo_train"` still reserved (products unlocked in G) |

### P2 — teaching surface

| ID | Item |
|---|---|
| B12 | Explore cards load preset → workspace experiment |
| B13 | Linked Lens projects live ResultGraph / SequenceIR, not static labels |
| B14 | Signal Lab must not mutate the fetched preset; use `model_copy` / rebuild |
| B15 | Real (non-mocked) Signal Lab integration test, or keep mock and say so |
| B16 | `k-space weighting` is a real observation or stop claiming the full chain in UI |
| B17 | Undo / redo / persistence / command palette — spec shell list; still absent |

### Explicitly later (not backlog for v0.1)

Contrast Lab, Optimization Lab, AI Lab runtime, ssEPG / EPG-X / PDG physics, Floquet / CEST / MRS / DCE, optimizer plugins, `core/` rename, microservices.

---

## Recommendation

v0.1 program is **acceptably closed** once Task 12 docs land.

Next work, if any, should be a **named hardening slice** (B1–B16), not “Task 13”. Do not start Contrast Lab or AI runtime until the user picks a slice.
