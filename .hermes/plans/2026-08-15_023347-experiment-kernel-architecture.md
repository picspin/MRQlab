# MRQLab Experiment Kernel — Architecture Lock + Implementation Plan Brief

> **For Codex (gpt-5.6-sol + superpowers writing-plans):** Expand this into
> `docs/superpowers/plans/YYYY-MM-DD-experiment-kernel.md` + optional
> `docs/superpowers/specs/…`. Planning only until user says 开工.
>
> **For Hermes:** After Codex plan lands, implement via litellm subagents
> (one fresh subagent per task, two-stage review). Codex keeps global plan/review.
>
> **Status:** Hermes locked architecture elevation. Supersedes the narrower
> “SequenceIR + SimulationEngine + SimResult only” center from the prior brief
> (`2026-08-15_010327-core-ir-engine-result-and-spectrum.md`) — that brief’s
> contract work remains **necessary but no longer sufficient** as the product center.
>
> **Author / git:** Xiaolei <zxl1412@gmail.com>; push key `id_ed25519_picspin`.

---

## Goal

Elevate MRQLab’s long-lived center from **SimulationEngine** to an
**Experiment Kernel**:

```
Experiment
  = Sequence
  + Spin/Tissue Model
  + Scanner Model
  + Physics Engine
  + Objective
  + Readout
```

SE / TSE / GRE / Dixon / flow / MRF / CEST / MRS are **not** separate product cores.
They are **named experiment compositions** (templates + capability plugins + objectives)
over one kernel.

This single center must serve, without forking the domain model:

1. **Teaching** — progressive fidelity, multi-layer visualization
2. **Forward simulation** — ideal → perturbed → application-specific
3. **Inverse / optimization** — objective-driven parameter search (later differentiable backends)
4. **Future complex physics** — EPG-X, ssEPG, PDG, Floquet/MRS, hybrid engines as plugins

---

## Architecture (locked)

```
                 MRQLab Experiment Kernel
                            │
      ┌─────────────────────┼──────────────────────┐
      │                     │                      │
      ↓                     ↓                      ↓
 Sequence Model        Sample Model           Scanner Model
      │                     │                      │
      └──────────────┬──────┴─────────────┬────────┘
                     │                    │
                     ↓                    ↓
              Physics Compiler      Constraint Engine
                     │
                     ↓
               Physics Engine(s)   ← capability plugins (NOT the kernel)
                     │
                     ↓
                Signal / State Model
                     │
          ┌──────────┼──────────┐
          ↓          ↓          ↓
       k-space     FID       State graph
          │          │          │
          ↓          ↓          ↓
       image      spectrum     EPG/PDG views
                     │
                     ↓
                  Objective
                     │
              ┌──────┴──────┐
              ↓             ↓
          Forward       Optimizer
          simulate       inverse (later)
```

### What the Kernel owns (and ONLY these)

| Responsibility | Notes |
|---|---|
| Experiment lifecycle | create / validate / compile / run / compare / snapshot |
| Typed state | Experiment, SequenceIR, Sample, Scanner, EngineRef, Objective, Readout, ResultGraph |
| Operator scheduling | event graph → operator stream (existing scheduler DNA) |
| Unit system | seconds, radians, teaching vs physical gradient units, γ/species |
| Reproducibility | seed, versions, provenance hash, assumption set |
| Engine discovery | registry + capability negotiation |
| Constraints | work caps, matrix caps, legality of engine×sample×sequence, Reality Slider bounds |
| Result graph | multi-product outputs + lineage edges (not a single ndarray dump) |
| Provenance | which template, engine, options, plugin versions produced which node |

### What the Kernel explicitly does NOT implement

- Bloch rotations
- EPG / EPG-X / ssEPG operators
- PDG internals
- CEST exchange / sat physics
- MRS Floquet propagators
- Image recon algorithms beyond thin product adapters
- Optimizer search loops (kernel only exposes Objective + evaluate hooks)

Those live in **capability plugins** behind stable ports.

### Layer map vs current monorepo

| Layer | Package (target) | Today (PR#3) | Elevation change |
|---|---|---|---|
| Sequence Model | `packages/sequence-ir` | SequenceIR + SE/TSE/GRE templates | Stay source-of-truth event graph; add typed experiment metadata blocks |
| Sample Model | `packages/physics` models → later `packages/sample` if split | Phantom / Isochromat / SpectralPool | Rename conceptually to Sample; multi-pool, species, exchange matrix optional |
| Scanner Model | physics models | ScannerModel (B0, grad scale) | Expand gradually (γ table, limits); still not hardware I/O |
| Physics Compiler | new kernel module | scheduler in physics | Promote schedule+units+preflight under Experiment Kernel façade |
| Constraint Engine | new | API env caps only | First-class constraint evaluation before run |
| Physics Engine plugins | physics backends/engines | Bloch/EPG/Spectral + PDG adapter | Capability-declared plugins; SimulationEngine becomes **run port**, not center |
| Signal / Result graph | SimResult → ResultGraph | flat SimResult | Versioned multi-product graph |
| Objective | new `packages/objective` or kernel submodule | none | Forward loss/contrast specs; inverse later |
| Readout / products | recon + physics products | FFT magnitude | k-space, FID, spectrum, image, state-graph views |
| Workspace frontend | `apps/web` | static skeuomorphic shell | Dashboard → Editor (4 layers) → progressive panels |
| Agent tools | docs/jsonschema first | none | Tools over Experiment, not raw engine classes |

**Dependency direction (locked):**

```
sequence-ir → sample/scanner models → experiment-kernel → physics plugins → product adapters → API → web
```

External systems (KomaMRI, MRzero, PyPulseq, torch EPG) may only appear as
**optional plugins / import-export ports**, never as the domain model
(consistent with prior MRSeqStudio differentiation).

---

## Domain objects (v1 contracts)

### `Experiment` (center)

```text
Experiment
  id, name, schema_version
  intent: teaching | clinical_contrast | physics | custom
  sequence: SequenceIR | TemplateRef
  sample: SampleModel
  scanner: ScannerModel
  engine: EngineRef { name, options, required_capabilities[] }
  objective: Objective | null          # null = pure forward teaching run
  readout: ReadoutSpec                 # which products to materialize
  constraints: ConstraintSet           # caps, fidelity tier, reality level
  metadata: ProvenanceHints
```

SE/TSE/GRE/Dixon/flow/MRF/CEST/MRS = **presets** that fill this object
(template + default sample + preferred engine + default objective/readout).

### `SequenceIR` (unchanged DNA, extended metadata)

Keep 8-channel event graph as sequence source of truth.
Add `metadata_schema_version` + typed optional blocks (Pydantic), either as
first-class optional fields or versioned metadata (Codex must pick one and lock):

- `engine_hint`
- `epg` (dk events, kmax hint)
- `diffusion`
- `spectral` / `cest` / `asl` stubs
- `loop` / periodic module markers (Floquet readiness later)

### `SampleModel`

Superset of today’s Phantom:

- bulk T1/T2/PD/off-res
- isochromats[]
- pools[] with optional exchange
- species / nucleus (1H default; x-nuclei table)
- flow / motion placeholders (capability-gated)

### `ScannerModel`

B0, gradient_scale → later gmax, slew teaching limits, γ. **Never** acquisition sockets.

### `EngineRef` + capabilities

```text
capabilities examples:
  bloch.isochromat
  epg.classic
  epg.exchange          # EPG-X BM — later
  epg.slice_selective   # ssEPG — later
  pdg.external
  spectral.independent_pools
  spectral.bloch_mcconnell
  spectral.floquet      # MRS long-horizon — later
  differentiable        # torch backends — later
  inverse.epg_params    # later
```

Kernel selects/validates engine via **capability negotiation**, not stringly `if name==`.

### `Objective`

v1 shapes (forward-compatible; implement evaluate stubs early):

| Kind | Example | Use |
|---|---|---|
| `contrast_target` | dark-blood / fat-suppressed relative signal | teaching + later inverse FA/TI/TE/TR |
| `signal_match` | match reference FID/spectrum | fitting |
| `null` | no score | pure simulate |

v1 may only **record** objectives and compute simple scalar scores on products.
Full inverse optimizer is a later plugin (`Optimizer` port).

### `ReadoutSpec` → `ResultGraph`

Products (nodes), not one blob:

- `signal` (complex time samples)
- `k_trajectory`
- `image` (via recon adapter)
- `spectrum` (ppm/Hz axis + complex/magnitude)
- `magnetization` / `configurations` (state graph; optional, cap-gated)
- `explanations` (assumptions, engine, op counts)
- `objective_score` (optional)
- edges: `derived_from`, `engine`, `recon`

Migrate today’s `SimResult` → **leaf/adapter** of ResultGraph for backward compat
during transition (`SimResult` remains valid physics-port return; kernel wraps it).

### `ConstraintEngine`

Before compile/run:

- work/matrix/ADC caps (existing)
- engine capabilities ⊇ experiment required_capabilities
- sample features supported (e.g. exchange requires BM-capable engine)
- Reality Slider tier → allowed perturbation set
- refuse partial physics with **explicit errors** (no silent wrong CEST)

---

## Physics plugin roadmap (backend foundation)

Priority matches teaching + extendability (from Question.txt), not “implement all now”.

| Tier | Plugin | Why | Inverse / notes |
|---|---|---|---|
| **P0 now** | Classic Bloch multi-isochromat | rotating-frame teaching; almost all sequences at high cost | forward |
| **P0 now** | Classic EPG | TSE / variable FA; cheap contrast design | metadata dk; inverse later |
| **P0 now** | Spectral independent pools | fat/water; spectrum product | forward |
| **P1** | EPG diffusion wiring | real tissue response demos | Stanford EPG ref |
| **P1** | Spectral BM / CEST-ready sat metadata | CEST teaching path; refuse if incomplete | |
| **P1** | x-nuclei γ/species table | spectrum engine foundation | |
| **P2** | EPG-X (BM/MT) multi-compartment | Dixon-like multi-pool; exchange | mriphysics/EPG-X |
| **P2** | PDG provider adapter (real provider optional) | Endres/Möbius differentiable spatial Bloch family | external |
| **P3** | ssEPG | soft-pulse × slice/crusher; MRF fidelity | k-space soft RF |
| **P3** | Floquet / periodic MRS engine | steady-state, banding, x-nuclei repeated modules | hybrid EPG later |
| **P4** | Differentiable EPG (torch) | auto-search TI/FA under contrast agents | mri-sim-py/epg; heavy infra later |
| **Ports only** | PyPulseq import/export, KomaMRI/MRzero EnginePlugin | never domain core | |

**Reality Slider mapping (conceptual):**

```
IDEAL  → instantaneous RF, no exchange, perfect gradients, single pool
  …    → off-res, multi-isochromat, classic EPG orders
  …    → diffusion, spoiler realism, multi-pool
REAL   → ssEPG / soft pulse, BM/MT, optional external high-fidelity backend
```

Slider adjusts **ConstraintSet + default engine/options**, not a second simulator.

---

## Frontend: progressive workspace (not one page forever)

### Navigation spine

```
Dashboard  →  Experiment Workspace (Editor)  →  Advanced panels
   │                    │
   │                    ├─ System layer: sequence diagram / IR timeline
   │                    ├─ Physics layer: rotating frame / Bloch sphere
   │                    ├─ Abstract layer: EPG/PDG configuration graph
   │                    └─ Reality layer: image / spectrum / contrast readout
   │
   └─ Clinical contrast entry points (not raw pulse names only):
        T1w GRE, T2w SE, T1/T2 mapping, Dixon, flow, CEST, custom…
```

### UX principles (locked)

- Skeuomorphic bench + **Golden Ratio** panel rhythm (existing visual DNA)
- Progressive disclosure: Beginner / Clinical / Physics / Hardware(**learning only**)
- Four linked views driven by **same Experiment + ResultGraph**, not four apps
- Reality Slider → constraints/fidelity (backend-backed when wired)
- Placeholders OK for AI Lab / special experiments; **decouple** from core teaching loop
- Frontend never owns SequenceIR semantics (ARCHITECTURE.md unchanged)

### Frontend delivery slices

1. Wire Dashboard case → `POST /sequences/build` + `POST /simulate` (or new `/experiments/run`)
2. Mxy(t) + magnitude image from ResultGraph
3. Engine selector + capability/assumption chips
4. Read-only IR timeline
5. Bloch sphere from optional magnetization (debug/cap-gated)
6. EPG order occupancy view when configurations present
7. Spectrum panel when spectral product present

---

## API evolution

Keep existing endpoints during transition; add Experiment-centric API:

| Endpoint | Role |
|---|---|
| `GET /engines` | + capabilities[] / assumptions[] |
| `POST /sequences/build` | keep |
| `POST /simulate` | keep as thin wrapper → Experiment(null objective) |
| **`POST /experiments/validate`** | constraints + capability check |
| **`POST /experiments/run`** | full Experiment → ResultGraph |
| **`GET /presets`** | clinical/teaching experiment presets |
| `GET /health` | keep |

Agent tool boundary (schemas only this wave):

- `mrqlab.list_presets`
- `mrqlab.build_experiment`
- `mrqlab.validate_experiment`
- `mrqlab.run_experiment`
- `mrqlab.inspect_ir`
- `mrqlab.explain_result`

---

## Suggested PR wave (Codex must task-split to 2–5 min steps)

| PR | Branch | Scope |
|---|---|---|
| **Plan** | `feature/experiment-kernel-plan` | this architecture → superpowers plan + locked spec in `docs/` |
| **A** | `feature/experiment-kernel` | Experiment + ResultGraph + Constraint types; wrap existing simulate; tests; docs ARCHITECTURE elevation |
| **B** | `feature/engine-capabilities` | EngineInfo capabilities; negotiation; SimResult schema_version + assumptions |
| **C** | `feature/spectrum-products` | spectrum node; species table; BM/CEST refuse-or-implement policy |
| **D** | `feature/workspace-wire` | web Dashboard→run→4-view stubs live data |
| **E** | `feature/objectives-v0` | Objective record + simple contrast_score on products (no optimizer yet) |
| **F** | `docs/agent-tools` | JSON schemas only |

**Do not** implement torch differentiable EPG, ssEPG, or Floquet MRS in A–E.
Land seams + refuse tests so future plugins don’t reshape the kernel.

---

## Relation to prior physics microkernel (PR#2/#3)

**Keep:**

- SequenceIR event-stream DNA
- Kernel-owned schedule / units / caps / ADC/NCO
- EnginePlugin descriptor model (not full SimulationEngine entry points)
- Bloch / EPG / Spectral built-ins
- PDG external provider seam
- NumPy-first teaching physics

**Elevate:**

- Product center: `SimulationEngine.simulate(...)` becomes **Physics run port**
  invoked by `ExperimentKernel.run(experiment) -> ResultGraph`
- Multi-product ResultGraph + Objective + Constraints first-class
- Frontend and agent talk **Experiment**, not engine class names
- Capability negotiation replaces ad-hoc `preferred_engine` as the long-term router
  (`preferred_engine` remains a convenience default inside presets)

---

## Non-goals (this elevation wave)

- Scanner / MaRCoS / Red Pitaya acquisition
- Clinical diagnostic claims
- Full CEST quantification / MRS clinical fitting
- Torch/GPU differentiable stack
- Cloning KomaMRI/MRzero/MRSeqStudio domain models
- Shipping a working inverse optimizer (design Objective port only)
- AI Lab runtime

---

## Acceptance themes

1. Spec + ARCHITECTURE state: center = Experiment Kernel; engines are plugins
2. Existing SE/TSE/GRE simulate path still green via compatibility wrapper
3. `Experiment` round-trips validate → run → ResultGraph with provenance
4. Capability mismatch fails closed with explicit error
5. Spectral path can attach spectrum product OR explicitly refuse CEST/BM
6. Web can run one preset and show at least signal + image products
7. Agent tool schemas published; no agent autonomy required
8. Docs list plugin roadmap (EPG-X, ssEPG, PDG, Floquet, torch) as **future ports**

---

## Open decisions for Codex to lock inside the plan (no human interview if resolvable)

1. **Package layout:** new `packages/experiment` vs `packages/physics/mrqlab_physics/experiment/` for v1 — prefer new package if import cycles threaten; else nested module for smaller PR.
2. **Typed modality blocks:** first-class SequenceIR fields vs versioned metadata-only — prefer versioned metadata + Pydantic parse helpers in v1 to avoid breaking wire model.
3. **ResultGraph storage:** in-memory dataclass graph vs JSON-ready Pydantic tree — prefer Pydantic tree for API/agent.
4. **Objective v0:** contrast ratio on echo peaks vs full time-series loss — prefer echo/peak contrast helpers for teaching presets.
5. **API:** add `/experiments/run` now vs only wrap `/simulate` — prefer add `/experiments/run` + keep `/simulate`.

---

## Inputs Codex must read on Mac checkout

- This brief
- Prior brief: `.hermes/plans/2026-08-15_010327-core-ir-engine-result-and-spectrum.md`
- `docs/ARCHITECTURE.md`, `docs/PHYSICS.md`, `docs/ROADMAP.md`
- `packages/physics/mrqlab_physics/{base,registry,models}.py`
- `packages/physics/mrqlab_physics/kernel/{scheduler,runner}.py`
- `packages/sequence-ir/mrqlab_sequence/{models,templates}.py`
- `services/api/mrqlab_api/main.py`
- `apps/web/app/page.tsx`
- User `Question.txt` themes (teaching → reality slider; EPG inverse later; EPG-X; ssEPG; Floquet MRS; 4-layer editor)
- **Note:** User also attached encrypted `Q&A with arch clarification.md` (WeChat binary, entropy~8). Content **unreadable** on gateway. If Mac has a plaintext copy, merge those Q&A rulings; otherwise treat this brief + Question.txt + user diagram as authoritative.

---

## Codex writing-plans requirements

- Announce use of superpowers `writing-plans`
- Skip brainstorming interview — scope locked here
- Save plan under `docs/superpowers/plans/YYYY-MM-DD-experiment-kernel.md`
- Optional locked spec under `docs/superpowers/specs/`
- Bite-sized TDD tasks, exact paths, full code, no TBD
- **Planning only** — no `packages/**` product edits in plan PR
- Branch `feature/experiment-kernel-plan`; author Xiaolei; do not push unless asked after review
- Explicit handoff section: subagent-driven implementation via litellm models after user 开工

---

## Verification (plan PR itself)

- [ ] Architecture diagram + kernel responsibility table in docs
- [ ] Migration note from SimulationEngine-centered wording
- [ ] Plugin roadmap table with tier P0–P4
- [ ] Frontend progressive workspace spine documented
- [ ] Task list covers contracts → API → web wire → objectives v0
- [ ] Every task has failing test → implement → pass → commit steps

---

## Handoff options (after plan lands — wait for user)

1. Open plan-only PR
2. 开工 with litellm subagents task-by-task (Codex reviews)
3. Codex executing-plans on Mac (anti-stall; picspin git)
