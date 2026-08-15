# MRQLab Next Wave — Core Contracts + Spectrum Path

> **Status:** Hermes locked brief for Codex `writing-plans` (gpt-5.6-sol).  
> **Mode:** Planning only. No product code until user says 开工.  
> **Handoff:** After plan lands, implementation via litellm subagents; Codex keeps global plan/review.

## Goal

Stabilize the three domain contracts that make every later modality a natural extension:

1. `SequenceIR` — unified MR experiment event model  
2. `SimulationEngine` — kernel-owned façade + backend plugins  
3. `SimResult` — stable consumer contract for recon/web/agent tools  

Then land the first **Spectrum / CEST / x-nuclei-ready** spectral path on top of those contracts, without adopting KomaMRI / MRzero / PyPulseq as MRQLab’s domain model.

## Non-goals (this wave)

- Not a full KomaMRI/MRzero clone
- Not scanner/MaRCoS acquisition
- Not production CEST quantification / clinical MRS fitting
- Not internal Agent runtime yet — only **tool boundary design**
- Not rewriting the skeuomorphic UI into a full rotating-frame lab (may stub hooks)

## Positioning (locked)

| Layer | MRQLab owns | External systems role |
|---|---|---|
| Domain model | SequenceIR, Phantom/Scanner, EngineOptions, SimResult | — |
| Physics microkernel | schedule, units, caps, ADC/NCO, registry | — |
| Built-in engines | Bloch / classic EPG / Spectral(+CEST/x-nuclei evolution) | teaching-grade |
| Optional backends | EnginePlugin / PDGProvider adapters | KomaMRI, MRzero, PyPulseq export/import, PDG libs |
| UX | interactive teaching + multi-engine explainability | MRSeqStudio-like designer may inspire UX, not the model |
| Agent | tool schemas over IR/simulate/result | future |

**Differentiation vs MRSeqStudio (arXiv:2512.00011):** they are KomaMRI backend + web designer. MRQLab is **unified experiment model + multi-physics engines + teaching interaction + future agent tools**.

## Maturity snapshot (as of PR #3 @ 9f309e1)

### EPG engine — ~55–65% teaching v1, not research-complete

**Present**
- Classic single-pool `(F+, F-, Z)` with bounded `kmax`
- Weigel-style RF matrix, signed Shift, T1/T2 + off-resonance on configs
- Metadata-first `epg_dk_events` (integer dk); area quantization fallback
- TSE template emits preferred_engine=`epg` + dk events
- Observe F+(k=0); configuration snapshots optional
- EPG-X layout zeros + explicit unavailable for BM/MT
- Diffusion helper seam (not wired to teaching gradients)

**Gaps**
- Only gx-oriented teaching shifts in templates; no full 3-axis configuration physics story
- No stimulated-echo pedagogy views / order occupancy UI
- No multi-pool EPG / CEST-EPG
- GradInterval is a no-op in EPGBackend (by design for classic EPG, but limits hybrid demos)
- No spoiler/crusher first-class IR ops beyond gradient channels + metadata dk
- No PDG built-in (adapter only)

### Bloch + rotating frame — backend yes, frontend mostly shell

**Backend present**
- Multi-isochromat Cartesian `Mxyz`
- Instantaneous RF as Rodrigues rotation about `(cos φ, sin φ, 0)` — rotating-frame transverse axis
- Per-spin T1/T2, off-resonance precession, spatial GradInterval phase
- Weighted observe → `Mx+1jMy`
- SE/GRE default to Bloch

**Frontend**
- `apps/web` is skeuomorphic **static bench**: knobs, timeline placeholder, CRT labels including “BLOCH SPHERE”
- No live API wiring, no Mxy(t)/sphere animation, no engine selector, no IR inspector
- Reality Slider is local React state only

**Verdict:** rotating-frame **physics path exists** in backend; **interactive rotating-frame teaching surface is not built**.

### Spectral engine — fat/water v0 only (~30% toward CEST/x-nuclei spectrum engine)

**Present**
- Independent chemical-shift pools expanded to Bloch isochromats
- ppm → Hz via γ·B0
- Explicit assumptions: no exchange / no MT / no CEST sat / no fitted MRS lineshapes

**Missing for “MR Spectrum Engine for CEST & x-nuclei”**
- Multi-pool exchange (Bloch–McConnell)
- Saturation / continuous RF / MT pools
- X-nuclei γ and species registry (13C, 23Na, 31P, …)
- Spectrum axis (ppm/Hz), window functions, simple Lorentzian display product
- SequenceIR support for sat pulses / offset frequency schedules as first-class metadata
- Engine selection + phantom pool schema in API/UI beyond raw dict

### SequenceIR — good skeleton, not yet modality-complete

**Present**
- Pydantic event graph: rf_amp/phase, gx/gy/gz, adc_gate, nco_freq/phase
- Ordered events, duration bounds
- Templates SE/TSE/GRE + FID demo
- metadata bag (`preferred_engine`, `epg_dk_events`, te/tr/echoes)

**Gaps for natural SE→…→MRS extension**
- No typed metadata schema (versioned) for engine hints, sat trains, diffusion b-values, ASL labels, species
- No import/export adapters (Pulseq / PyPulseq) — correctly not domain core, but needed as **ports**
- No units profile on IR (teaching vs physical gradient units)
- No explicit RF shape / hard-pulse vs soft-pulse model beyond instantaneous amp events
- No multi-TR loop / outer phase-encode structure beyond single TR duration teaching graphs

### SimulationEngine — strong microkernel core

**Present**
- Kernel-owned `simulate(SequenceIR, Phantom, Scanner, Options) -> SimResult`
- preflight → schedule → run_backend → caps → meta assembly
- EnginePlugin entry points; rejects full-engine plugins that bypass kernel
- Built-ins: bloch / epg / spectral

**Gaps**
- Options still EPG-centric fields mixed with global options
- No capability negotiation (`supports: exchange|diffusion|x_nucleus`)
- No progressive fidelity / Reality Slider mapping into options
- PDGAdapter bypasses EnginePlugin path (special case)

### SimResult — minimal but stable enough to harden now

**Present**
- `signal`, `k_trajectory`, optional `magnetization`/`configurations`, `meta`, `timing`
- API strips snapshots; returns real/imag signal + FFT mag

**Gaps**
- No versioned schema / JSON schema export
- No spectrum product (`ppm_axis`, `spectrum`)
- No explanation payload (which ops, which engine assumptions)
- No agent-friendly stable error taxonomy
- Recon coupling still “FFT if any samples” only

## Core design priorities (must land before modality sprawl)

### P0 — Contract freeze (this PR wave)

1. **SequenceIR v1.1**
   - Keep channels as source of truth
   - Add `metadata_schema_version`
   - Typed optional blocks (Pydantic models, still serialized inside metadata or sibling fields):
     - `engine_hint`
     - `epg` (dk events, kmax hint)
     - `diffusion` (b-value placeholders)
     - `spectral` (species, pools ref, sat offsets)
     - `asl` / `cest` stubs as closed enums + forward-compatible dicts
   - Template compilers remain the only product path for SE/TSE/GRE; FID stays test helper

2. **SimulationEngine contract doc + capability flags**
   - `EngineInfo`: name, available, capabilities[], assumptions[]
   - Keep kernel ownership of schedule/caps/ADC/NCO/result
   - External compute backends = EnginePlugin **or** explicit Adapter with same SimResult

3. **SimResult v1.1**
   - Required: `schema_version`, `signal`, `k_trajectory`, `meta.engine`, `meta.signal_convention`, `meta.assumptions`
   - Optional products: `magnetization`, `configurations`, `spectrum` (new), `explanations` (new, light)
   - API response model mirrors SimResult products explicitly (no ad-hoc drift)

### P1 — Spectrum engine foundation (same or immediate next PR)

- Extend Spectral path toward **CEST & x-nuclei readiness** without claiming full CEST:
  - Species / gyromagnetic ratio table (1H default; 13C/23Na/31P stubs)
  - Multi-pool phantom with optional exchange matrix (BM) behind capability flag
  - Saturation metadata on IR: offset_hz / offset_ppm list + B1 continuous approx **or** explicit “not in v1” with tests that refuse partial support
  - Spectrum builder from long FID ADC: window → FFT → ppm axis
  - Golden tests: fat/water beat; simple 2-pool exchange identity cases; refuse unsupported CEST if not implemented

### P2 — Bloch teaching loop (frontend)

- Wire web bench to `/engines`, `/sequences/build`, `/simulate`
- Minimal rotating-frame panel: Mxy(t) from signal; Bloch sphere from optional magnetization snapshots (local/dev only if API strips snaps — consider debug flag)
- Engine selector + assumption chips from EngineInfo
- IR timeline from SequenceIR channels (read-only)

### P3 — Agent tool boundary (design only in plan PR)

Stable tools (names locked early):
- `mrqlab.build_sequence`
- `mrqlab.list_engines`
- `mrqlab.simulate`
- `mrqlab.inspect_ir`
- `mrqlab.explain_result`

No agent autonomy in this wave — schemas + authz notes + side-effect policy only.

## Backend policy (locked)

- **Domain model ≠ KomaMRI/MRzero/PyPulseq**
- Allowed:
  - PyPulseq/Pulseq **import/export ports** later
  - KomaMRI/MRzero as **optional EnginePlugin providers** behind adapters
  - Reference numerical comparisons in tests/docs
- Forbidden:
  - Leaking Julia/torch types into SequenceIR/SimResult
  - Making MRQLab templates depend on external sequence DSLs

## Suggested PR slice

| PR | Title | Scope |
|---|---|---|
| **#4 plan** | docs: core contracts + spectrum roadmap | superpowers plan + locked spec only |
| **#4 impl** | feat(core): SequenceIR/SimResult v1.1 + engine capabilities | contracts, API models, tests |
| **#5** | feat(physics): spectrum products + x-nuclei species table | spectral path |
| **#6** | feat(web): wire bench to simulate + rotating-frame views | frontend teaching loop |
| **#7** | docs/tools: agent tool boundary schemas | no runtime agent |

(Exact task breakdown to be expanded by Codex writing-plans.)

## Implementation principles for Codex plan

- TDD, bite-sized tasks, exact paths, full code in plan
- NumPy-first; no new heavy deps without explicit optional extra
- Preserve `SimulationEngine.simulate` four-arg signature
- Prefer extending metadata with versioned schema over channel proliferation
- Refuse partial CEST/MT with explicit errors rather than silent wrong physics
- Author: `Xiaolei <zxl1412@gmail.com>`; push key picspin

## Acceptance themes

1. Contracts documented + schema tests green  
2. SE/TSE/GRE still pass; EPG TSE path unchanged or improved  
3. Spectral can emit spectrum product for FID-like ADC  
4. Engine list exposes capabilities  
5. Web can run one SE simulate and plot Mxy(t)  
6. Agent tool schemas published as docs/jsonschema only  

## Open questions for Codex to resolve inside the plan (not re-interview)

1. Put typed modality blocks as SequenceIR first-class optional fields vs versioned metadata-only?  
2. BM exchange in spectral engine now vs wait for EPG-X multi-pool? Prefer spectral BM for CEST teaching; keep EPG-X seam.  
3. API debug flag for snapshots vs always-off? Prefer `options.return_*` honored when under work cap.  
4. Spectrum product ownership: physics engine vs recon package? Prefer physics emits raw complex spectrum; recon may window/display later.

## References

- In-repo: `docs/PHYSICS.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, PR #3 microkernel
- Weigel 2015 EPG; Malik 2018 EPG-X; Pruessmann 2021; Möbius/Endres 2024 PDG
- KomaMRI (JuliaHealth) — optional backend inspiration
- MRSeqStudio arXiv:2512.00011 — web designer + KomaMRI backend (contrast, don’t copy domain)
- Local refs: `/opt/data/tmp/mrq-refs/{epg,EPG-X,pulseq,pypulseq,...}`
