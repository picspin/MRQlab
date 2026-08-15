# MRQLab Experiment Kernel — Locked Architecture (Q&A merged)

> **For Codex (gpt-5.6-sol + superpowers `writing-plans`):** Expand into
> `docs/superpowers/plans/YYYY-MM-DD-experiment-kernel.md` +
> `docs/superpowers/specs/experiment-kernel.md` + ADRs under `docs/adr/`.
> Planning only until user says 开工.
>
> **Sources of truth (merged):**
> 1. User diagram + elevation message (Experiment center)
> 2. `Question.txt` (teaching → reality → inverse; EPG-X; ssEPG; Floquet; 4-layer UI)
> 3. **Q&A arch clarification** (full GPT Answer, 24 sections) — now readable
> 4. Prior Hermes brief `2026-08-15_023347-experiment-kernel-architecture.md`
> 5. Repo state PR#3 physics microkernel (keep DNA, elevate center)
>
> **Author/git:** Xiaolei <zxl1412@gmail.com>; picspin SSH key.
> **Deploy shape:** modular monolith (ONE Python process + Next.js), not microservices.

---

## One-line product thesis

**Form a hypothesis → design an MR experiment → understand state evolution → observe consequence → optimize toward a clinical/physical objective.**

Not: “watch a sequence simulator.”

---

## Five stable kernel contracts (LOCKED)

These five are the long-lived center. Everything else is a plugin or view.

| # | Contract | Role |
|---|---|---|
| 1 | **`ExperimentGraph`** | User/clinical + system experiment structure (nodes/edges). **Above** SequenceIR. |
| 2 | **`PhysicsOperator`** | `apply(state, event, context) → state` — RF, Relax, Grad/Shift, Exchange, Diff, Flow, ChemShift… |
| 3 | **`StateRepresentation`** | Bloch / EPG / PDG / DensityMatrix / … — **not** a class hierarchy of “AdvancedSimulator” |
| 4 | **`ObjectiveFunction`** | Clinical/physical goals + constraints (contrast, SAR, time…) for forward score & inverse |
| 5 | **`Observation`** | Signal products: k-space, FID, image, spectrum, state-graph views |

**SequenceIR is necessary but demoted:** scanner-level event stream under ExperimentGraph.
At DCE/ASL/CEST/MRS scale you simulate the **experiment**, not a pulse class tree.

```text
CLINICAL / EXPERIMENT INTENT   "What contrast do I want?"
            ↓
SYSTEM LAYER                   "What sequence/graph does it?"
            ↓
PHYSICS LAYER                  "What happens to magnetization?"
            ↓
STATE LAYER                    "Which pathways/states produce it?"
            ↓
OBSERVATION LAYER              "What signal/image/spectrum results?"
            ↓
OPTIMIZATION LOOP              "How should I change the experiment?"  → top
```

---

## Critical conceptual corrections (must appear in ARCHITECTURE.md)

### C1 — EPG is forward, not inverse

EPG / EPG-X / ssEPG are **efficient forward models**.

“Dark-blood → solve TI/FA/TE/TR” is:

```text
θ* = argmin_θ  L( S_engine(θ), S_target )
θ = (TR, TE, TI, α1, α2, …)
```

- Classic EPG → grid / Bayesian / CMA-ES  
- Differentiable EPG → ∇_θ L (Adam/LBFGS) — **later**, torch infra  
- **Optimizer is a first-class plugin**, not hidden in AI Lab  
- AI helps **define objectives** and explain; does not replace optimizer

### C2 — Representation ≠ Operator

| Representation (state) | Operators (physics actions) |
|---|---|
| Bloch state | RF, Relaxation, Gradient, … |
| EPG (+ PDG / ssEPG / EPG-X as related config domains) | Exchange, Diffusion, Flow, ChemShift, … |
| Density matrix | (+ Floquet as **accelerator**, not MRS engine itself) |

EPG-X = EPG state + ExchangeOperator — not a greenfield simulator.

### C3 — Engines form a capability matrix, not a skill tree

Bloch ⊄ junior, EPG ⊄ senior. Dual/hybrid OK.

```text
supports:
  shaped_rf | exchange | diffusion | flow | off_resonance
  spatial_encoding | steady_state | differentiable
  multi_pool | multi_species
```

Kernel (+ Physics Compiler) selects representation by experiment + disturbances.

Examples:

| Experiment need | Representation |
|---|---|
| TSE + hard RF | EPG |
| TSE + shaped slice RF | ssEPG / hybrid Bloch–EPG |
| CEST | Bloch–McConnell |
| MRF + crushers + slice profile | ssEPG |
| 2D GRE + arbitrary field map | Bloch / PDG |
| periodic heteronuclear SS | density matrix (+ Floquet accelerator) |

### C4 — Floquet is not “the MRS engine”

MRS base: Hamiltonian + density matrix + Liouville–von Neumann (+ relaxation).

Floquet = `PeriodicSequenceAccelerator` / `SteadyStateSolver` for periodic modules.

PRESS/STEAM/semi-LASER/J-coupled/x-nuclei stay natural under density-matrix path.

### C5 — ssEPG is its own representation/compiler path

Not `epg.enable_slice_profile=True`.

ssEPG (Ostenson et al.) + emerging **slice-profile-enabled PDG** align with:

```text
segment sequence → choose best representation → compile operators → propagate
```

Physics Compiler emits spans: `BlochSpan` | `EPGSpan` | `PDGSpan` | …

### C6 — PDG bridges abstract pathways ↔ spatial image formation

```text
EPG (fast, abstract) ── PDG ── Bloch (spatial, expensive)
```

UI STATE layer shows EPG/PDG/exchange graphs; OBSERVATION shows signal/k/image/spectrum.
MRS observation can be FID→spectrum **without** image.

---

## Three-layer IR (LOCKED architecture boundary)

```text
Experiment IR          user/clinical meaning
      ↓  Sequence Compiler
Sequence IR            scanner event graph (today’s SequenceIR DNA)
      ↓  Physics Compiler
Physics IR             RF_ROTATION, FREE_EVOLUTION, EXCHANGE, EPG_SHIFT, …
      ↓
StateRepresentation plugins + Operators
      ↓
Observation products
```

### Experiment IR (examples of meaning, not class names)

- “T2-weighted dark blood / 3T / carotid / blood suppress / wall preserve”
- Nodes can include clinical/system ops beyond pure RF: Preparation, Exchange, Flow, Diffusion, Injection, Readout

### ExperimentGraph (internal structure)

```text
nodes: RF | Gradient | Delay | ADC | Preparation | Exchange | Flow
       | Diffusion | Injection | Readout | …
edges: temporal | dependency | state-transition
```

**Forbidden long-term:** `SpinEchoSequence` / `CESTSequence` / … class explosion.  
**Allowed:** named **presets/plugins** that *build* an ExperimentGraph + defaults.

SE/TSE as graphs:

```text
SE:  Excitation → FreeEvolution → Refocusing → Readout
TSE: Excitation → [Refocus → Evolve → Echo] × ETL
CEST: Sat train → BM exchange → Readout → Z-spectrum
ASL: Label → Transit → Exchange → PLD → Readout
DCE: Injection → PK → T1(t) → Sequence → Signal(t)
```

### Sequence IR

Keep current 8-channel validated event graph as scanner-level IR.  
Templates SE/TSE/GRE remain **compilers into SequenceIR**, then upward into ExperimentGraph presets.

### Physics IR

Operator stream / spans — evolves from today’s scheduler `Operator` union.
Must stay kernel-owned scheduling + units + caps.

---

## Kernel responsibilities (unchanged list, sharper)

Kernel implements **only**:

- experiment lifecycle  
- typed state (five contracts + Sample/Scanner)  
- operator scheduling  
- unit system  
- reproducibility / provenance  
- engine **discovery** + capability negotiation  
- constraints  
- result / observation graph  

Kernel does **not** implement Bloch, EPG, CEST, MRS internals, or optimizer algorithms.

---

## Disturbance Stack (upgrades Reality Slider)

Reality is **not** only a 0–100 slider. Slider may remain UX sugar over a stack:

```text
Ideal
+ thermal noise
+ B0 map / B1+ map
+ gradient delay / eddy / nonlinearity
+ motion / flow / diffusion
+ chemical exchange
+ susceptibility / coil sensitivities / ADC imperfection
```

Each item = **Disturbance Plugin** (`type`, `domain`, params).

**Teaching gold:** stack changes can trigger engine reselection:

```text
TSE default EPG
  + slice profile     → suggest ssEPG
  + exchange          → EPG-X / hybrid
  + spatial B0        → PDG
```

User learns *why* representation complexity grows.

---

## Optimization (first-class, not AI Lab)

### ObjectiveSpec examples

```text
blood < 5%; wall > 60%; muscle > 45%
scan time < 4 min; SAR < limit
```

```text
J(θ) = w1 S_blood - w2 S_wall + w3 T_scan + λ C_SAR
```

### Optimizer plugins

GridSearch | RandomSearch | Bayesian | CMA-ES | GradientOptimizer  

Physics interchangeable under same Objective:

```text
EPG → CMA-ES
Differentiable EPG → Adam/LBFGS
```

### Pedagogy rules

- Show **why** a solution, not only θ*  
- Prefer **Pareto frontier** (contrast vs time vs SAR vs SNR) over single “AI best”  
- Contrast Lab: target tissue bars → Optimize → landscape + candidates + explanations  
- Signal Lab: parameter → physics → signal → contrast **live chain** (killer feature)

MVP may only **record** Objective + simple forward scores; full optimizers later — but **ports exist in architecture now**.

---

## Frontend: Workspace shell + microfrontends

Not a traditional single SPA blob forever.

### Shell owns

Router · Workspace manager · Experiment state · Undo/redo · Persistence · Plugin registry · Command palette

### Workspaces (same Experiment State)

```text
dashboard/          Explore · Build · Resume
editor/             cockpit (instrumental skeuomorphism)
signal-lab/         killer feedback chain
contrast-lab/       objective-first optimization teaching
optimization-lab/
ai-lab/             last; tools over graph — not chatbot-first
```

**Dashboard → Editor = change workspace, not open a new simulator.**

### Dashboard Explore cards (clinical first)

Not GRE/SE/TSE tiles as primary:

- T1 Contrast — why WM bright?  
- Dark Blood — suppress flow, keep wall  
- Dixon — water/fat  
- T2 Mapping — estimate T2  

Secondary line: `Uses: IR / TSE / GRE / multi-echo…`

### Editor = cockpit

**Instrumental skeuomorphism** (not fake leather/screws):

- knobs = real continuous params  
- meters = real SAR / duty  
- scope timeline = real waveforms  
- Bloch globe = real state observer  

Visual: precision MRI console × synth × scientific workstation.

### Golden Ratio = design tokens, not mechanical 1.618 everywhere

Editor chrome ~ `19% | 62% | 19%`; canvas split timeline ~38% / viz ~62%.

### Linked Lens System (not four permanent quadrants)

Default:

```text
Sequence
Physics | Observation
```

Lens focus (e.g. EPG) expands STATE; RF click fans out Bloch rotation / EPG transition / signal contribution.

**Shared cursors (must engineer early):**

```text
cursorTime | selectedEvent | selectedState | selectedVoxel | selectedEcho
```

### Four conceptual layers (naming locked for UI copy)

| Layer | Name | Content |
|---|---|---|
| SYSTEM | Sequence timeline | ExperimentGraph / SequenceIR |
| PHYSICS | Spin / rotating-frame | Bloch sphere, Mxy/Mz |
| STATE | Pathway graph | EPG / PDG / exchange |
| OBSERVATION | Products | signal / k-space / image / spectrum |

---

## AI Lab (last)

Tools see full ExperimentGraph:

```text
inspect_experiment | inspect_signal | compare_tissues
run_simulation | run_optimization
explain_epg_pathway | suggest_parameters | find_failure_mode
```

Answers via run→inspect pathways — not LLM guess.  
Optional later: literature / Pulseq / relaxometry / limits.  
**Simulator core always offline-capable.**

---

## Backend shape: Modular Monolith (LOCKED)

Microkernel = **code** architecture ≠ microservices.

v1:

```text
ONE Python process: core + engines + recon + optimization + FastAPI
Next.js web
```

Only later: API → job scheduler → GPU workers when jobs are heavy.

### Target repo layout (5-year shape; migrate gradually from packages/*)

```text
MRQLab/
  apps/web  apps/api
  core/{experiment,sequence,sample,scanner,operators,objectives,results,provenance}
  engines/{bloch,epg,pdg,ssepg,bloch_mcconnell,density_matrix}
  accelerators/{floquet,differentiable,gpu}
  disturbances/{b0,b1,noise,motion,flow,diffusion,eddy_current}
  optimization/{grid,bayesian,evolutionary,gradient}
  recon/{fft,nufft,sense}
  adapters/{pulseq,ismrmrd,marcos}
  plugins/{cases,experiments,tissues}
  packages/{schemas,units,protocol}
  docs/{architecture,physics,adr}
```

**Migration rule:** do not big-bang move on day one.  
Plan PR documents target tree; impl PRs may start as:

- `packages/experiment` (or `core/experiment`) wrapping existing physics  
- keep `packages/sequence-ir`, `packages/physics` working  
- re-export shims until cutover  

Codex must specify incremental move with green tests each step.

---

## MVP still must hold the line (v0.1 thesis)

**Do not ship Floquet / full CEST / MRS / DCE in first impl wave.**

Validate only:

| Preset | Must prove |
|---|---|
| **SE** | timeline ↔ Bloch ↔ signal ↔ image |
| **GRE** | gradient ↔ k-space ↔ contrast |
| **TSE** | RF train ↔ EPG ↔ echo train ↔ image contrast |

**TSE is the thesis test:** drag refocusing FA → EPG states rearrange → echo train changes → k-space weighting changes → tissue contrast changes (+ SAR meter moves).

One deep loop ≫ twenty shallow sequences.

---

## Physics plugin tiers (aligned with Q&A + prior brief)

| Tier | What | Notes |
|---|---|---|
| **P0 (now/next)** | ExperimentGraph light + three IR boundary docs; wrap SE/GRE/TSE; Bloch+EPG+Spectral as StateRepresentation+Operators; Observation graph; capability matrix stubs; Linked Lens cursors API fields; Disturbance Stack schema (ideal only) | Keep PR#3 numerical paths green |
| **P1** | Spectrum product; species/γ; diffusion op wiring; Objective v0 forward score; web wire Dashboard Explore + Editor lenses + Signal Lab minimal | |
| **P2** | EPG-X exchange op; PDG provider; Disturbance plugins that reselect engine; Contrast Lab stub | |
| **P3** | ssEPG / hybrid compiler spans; Pareto optimizers non-diff | |
| **P4** | Density matrix MRS path; Floquet accelerator; differentiable EPG; GPU workers | |

External: KomaMRI/MRzero/PyPulseq = adapters/engines only — **never domain model**.

---

## Suggested PR wave (for Codex task breakdown)

| PR | Scope |
|---|---|
| **Plan** | This lock → superpowers plan + spec + ADR-0001 five contracts + ADR-0002 three IR + ADR-0003 EPG≠inverse + ADR-0004 disturbances + ADR-0005 modular monolith |
| **A** | `ExperimentGraph` + Experiment IR types; SequenceIR remains; presets SE/GRE/TSE build graphs; `/experiments/validate|run` wrapping existing simulate |
| **B** | `PhysicsOperator` protocol alignment with current ops; `StateRepresentation` capability matrix; EngineInfo.supports[] |
| **C** | `Observation` / ResultGraph versioned products + provenance |
| **D** | `ObjectiveFunction` record + simple scores (no optimizer algos yet) |
| **E** | DisturbanceStack schema + Reality Slider maps to stack |
| **F** | Web: Shell routes Dashboard Explore cards + Editor Linked Lens + wire simulate |
| **G** | Signal Lab minimal live chain for TSE FA drag (may be progressive) |
| **H** | Agent tool schemas only |

---

## Open decisions Codex must lock in plan (no interview)

1. Incremental package path: introduce `core/` vs `packages/experiment` first — **prefer `packages/mrqlab_experiment` now, document `core/` as target rename**.  
2. ExperimentGraph v0 node set: start with RF/Grad/Delay/ADC/Readout/Loop only; Preparation/Exchange/… as reserved enums.  
3. Physics IR: formalize as typed op stream = today’s scheduler output + version field.  
4. Observation JSON schema in `packages/schemas`.  
5. Keep `/simulate` forever-compat; new `/experiments/*` is canonical.

---

## Codex writing-plans requirements

- Read and announce superpowers `writing-plans`  
- Skip brainstorming — **fully locked by this doc + Q&A**  
- Output: `docs/superpowers/plans/YYYY-MM-DD-experiment-kernel.md`  
- Spec: `docs/superpowers/specs/experiment-kernel.md`  
- ADRs listed above  
- Bite-sized TDD tasks, exact paths, full code, no TBD  
- **No product code** in plan branch beyond docs  
- Branch: `feature/experiment-kernel-plan`  
- Explicit handoff: litellm subagents implement; Codex global review  
- Anti-scope: no Floquet/CEST/MRS/DCE implementation tasks in MVP tasks — only seams/ADRs  

---

## Acceptance (plan quality)

- [ ] Five contracts named exactly as locked  
- [ ] Three-layer IR boundary diagram  
- [ ] EPG≠inverse + Optimizer plugin called out  
- [ ] Representation vs Operator split  
- [ ] Capability matrix not inheritance tree  
- [ ] Disturbance Stack replaces sole Reality Slider narrative  
- [ ] Workspace shell + Explore clinical-first dashboard  
- [ ] Linked Lens + shared cursors  
- [ ] Modular monolith repo target + incremental migration  
- [ ] MVP SE/GRE/TSE thesis tests explicit  
- [ ] Every impl task: fail test → code → pass → commit  

---

## Handoff after plan (wait for user)

1. Open plan-only PR  
2. 开工 → litellm subagents per task  
3. Codex executing-plans on Mac (when SSH OK)

## Blockers for Codex spawn

- Mac Tailscale SSH currently times out (needs user auth)  
- When Mac OK: stage this file + Q&A copy onto Mac repo and run `codex exec` writing-plans
