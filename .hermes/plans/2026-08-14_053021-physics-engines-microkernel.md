# MRQLab Physics Engines Microkernel — Follow-up Implementation Plan

> **For Hermes:** Use subagent-driven-development (or Codex Cloud) to implement this plan task-by-task. Do **not** merge UI work into this branch unless a test needs a thin API expose.

**Goal:** Turn the MVP `SimulationEngine` stubs into a real **microkernel + plugin** physics layer, with three first-class engines — **Bloch**, **EPG** (classic + X-path hooks), **Spectral/PDG-facing** — sharing one operator algebra, fed only by `SequenceIR`, emitting one `SimResult`.

**Architecture:** Kernel owns IR walk, caps, registry, and operator contracts. Engines are plugins that compose operators over different state representations (isochromat vector / EPG configuration tensor / spectral multi-pool / later PDG graph). Sequence templates, API, recon, and web stay outside the kernel.

**Tech Stack:** Python 3.12+, numpy (MVP/default), optional torch later for PDG/diff; pydantic SequenceIR; pytest; reference-only clones under `/opt/data/tmp/mrq-refs/` (not vendored into runtime).

**Base branch:** `feature/mrqlab-mvp` @ `8a2277b` (PR #1). Work on `feature/physics-microkernel` cut from that tip (or from `main` after #1 merges).

**Out of scope this follow-up:** real MaRCoS/Red Pitaya acquisition, heavy MRzero/torch default install, full multi-slice parallel-TX, clinical validation, web polish.

---

## 0. Current state (facts)

| Piece | Status |
|---|---|
| `packages/physics/mrqlab_physics/base.py` | Thin ABC: `simulate(seq, phantom, scanner, options) -> SimResult` |
| `engines.py` | `BlochEngine` = single isochromat, instantaneous RF about x, crude T1/T2/off-res; `EPGEngine`/`SpectralEngine` = `NotImplementedError` stubs |
| `registry.py` | name → instance dict |
| `sequence-ir` | MaRCoS-like channels: `rf_amp/phase, gx/gy/gz, adc_gate, nco_*` |
| Templates | SE / TSE / GRE compilers (TSE is repeated 180s, not true EPG) |
| Tests | 7 green; physics only checks “signal nonempty” + stub raises |

**Debt called out in PR review (must address here):**
1. RF instantaneous / no phase axis / no hard-pulse substeps  
2. No multi-isochromat; `matrix` unused  
3. Runtime cap is sequence duration, not work estimate  
4. EPG/Spectral not real  

---

## 1. Reference map (read-only assets)

Local clones (already pulled where noted):

| Asset | Path / URL | What to steal (algorithms, not code license-copy wholesale) |
|---|---|---|
| Classic EPG (Python) | `/opt/data/tmp/mrq-refs/epg` · [imr-framework/epg](https://github.com/imr-framework/epg) | `rf_rotation`, `relaxation`, `grad_shift`, Ω = `[F+, F-, Z]` per order |
| EPG-X (MATLAB) | `/opt/data/tmp/mrq-refs/EPG-X` · [mriphysics/EPG-X](https://github.com/mriphysics/EPG-X) | Sparse shift matrices; state layouts BM/MT; `E_diff` diffusion weights; TSE/GRE drivers; multi-pool ops |
| Pulseq | `/opt/data/tmp/mrq-refs/pulseq` | Block/event timing model, RF/grad/ADC semantics |
| PyPulseq | `/opt/data/tmp/mrq-refs/pypulseq` | Python block API parity; later IR↔`.seq` export only |
| MaRCoS | `/opt/data/tmp/mrq-refs/marcos_client` (+ flocra/ocra-pulseq) | **Event-stream DNA**: timed buffers TX_I/Q, grad, RX gate, NCO/DDS — IR channel set already mirrors this |
| pulseq-zero / PDG | `/opt/data/tmp/mrq-refs/pulseq-zero` · [pulseq-frame/pulseq-zero](https://github.com/pulseq-frame/pulseq-zero) | PDG as fast analytical Bloch; differentiable path later via MRzeroCore — **adapter**, not kernel dependency |

**Papers (operators / state spaces):**

1. **Weigel 2015** — EPG pure & simple (F+/F−/Z, RF / shift / relax).  
2. **Malik 2018 / EPG-X** — MT + Bloch–McConnell configuration states.  
3. **Pruessmann 2021** doi:10.1002/mrm.29101 — *Configuration space representation* / continuous configuration model (CCM); EPG as discrete special case.  
4. **Endres / Möbius et al. 2024** doi:10.1002/mrm.30055 — *Phase distribution graphs (PDG)*: EPG extended with dephased-state spatial encoding, echo *shapes*, full differentiability in flip/phase/G/time; PyTorch + state selection.

**License note:** Re-implement operators from equations + tests against reference numerical outputs. Do **not** paste MATLAB/GPL blobs into the package. Cite papers + upstream repos in `docs/PHYSICS.md`.

---

## 2. Target architecture (microkernel)

```text
                    ┌─────────────────────────────────────┐
                    │           Physics Kernel              │
                    │  registry · caps · IR scheduler       │
                    │  operator Protocol · units · errors   │
                    └───────────────┬─────────────────────┘
                                    │ uses
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
        BlochPlugin            EPGPlugin            SpectralPlugin
        (isochromats)     (config orders k)     (multi-pool / PDG-facing)
              │                     │                     │
              └────────── shared ops library ─────────────┘
                 rf · relax · free_precess · grad_shift
                 spoil · sample_adc · exchange · diffuse
                                    │
 SequenceIR ──► IR→OpStream ──► Engine.simulate ──► SimResult
 Phantom / ScannerModel / EngineOptions ───────────►┘
```

### 2.1 Deep seams (stable interfaces)

**A. `SimulationEngine` (existing, keep small)**  
`simulate(sequence, phantom, scanner, options) -> SimResult`

**B. New: `Operator` protocol** (kernel-level, engine-agnostic *intent*)

```python
# packages/physics/mrqlab_physics/ops/types.py
class Op(BaseModel):
    t: float          # absolute time [s]
    dt: float = 0.0   # duration [s] (0 = instantaneous)

class RfOp(Op):
    alpha_rad: float
    phi_rad: float = 0.0
    # later: b1_waveform: ndarray | None

class RelaxOp(Op): ...
class ShiftOp(Op):
    dk: tuple[int, int, int] = (0, 0, 0)  # config-space steps; Bloch maps to phase
class GradIntervalOp(Op):
    g: tuple[float, float, float]  # T/m or teaching units via ScannerModel
class AdcSampleOp(Op):
    nco_phase_rad: float = 0.0
class SpoilOp(Op): ...
```

**C. `StateBackend` protocol** (what plugins implement)

```python
class StateBackend(Protocol):
    def apply_rf(self, alpha: float, phi: float) -> None: ...
    def apply_relax(self, dt: float, t1: float, t2: float) -> None: ...
    def apply_shift(self, dk: Sequence[int]) -> None: ...
    def apply_offres(self, dt: float, hz: float) -> None: ...
    def transverse(self) -> complex: ...   # observable / F0
    def snapshot(self) -> Any: ...
```

**D. `SimResult` extension (backward compatible)**

```python
@dataclass
class SimResult:
    signal: np.ndarray
    k_trajectory: np.ndarray
    magnetization: np.ndarray | None = None
    configurations: Any | None = None   # EPG Ω history (teaching view)
    meta: dict[str, Any] = field(default_factory=dict)
    timing: dict[str, float] = field(default_factory=dict)
```

### 2.2 Plugin packaging layout

```text
packages/physics/mrqlab_physics/
  __init__.py                 # public: get_engine, list_engines, models
  base.py                     # SimulationEngine ABC
  models.py                   # Phantom, Scanner, Options, SimResult
  registry.py                 # entry-point aware registry
  kernel/
    scheduler.py              # SequenceIR → list[Op]
    caps.py                   # work estimate + matrix/runtime guards
    units.py                  # deg/rad, s/ms, grad scale
  ops/
    rf.py                     # Weigel T(φ,α) 3×3 + hard-pulse splitter
    relax.py                  # E1/E2 + regrowth
    shift.py                  # EPG shift; Bloch phase from ∫G
    sample.py                 # ADC + NCO demod
    diffuse.py                # EPG-X style b-value weights (phase 2)
    exchange.py               # BM/MT hooks (phase 3)
  backends/
    bloch.py                  # multi-isochromat M ∈ R^(N,3)
    epg.py                    # Ω[k] classic 3-state
    epg_x.py                  # stub layout for BM/MT (phase 3)
    spectral.py               # multi-pool isochromat / Lorentzian (phase 2–3)
    pdg.py                    # optional adapter facade → MRzero/PDG (phase 3+)
  engines/
    bloch_engine.py
    epg_engine.py
    spectral_engine.py
  plugins.py                  # load entry_points group "mrqlab.physics_engines"
```

External plugins later: `pyproject.toml` →  
`[project.entry-points."mrqlab.physics_engines"]`  
`my_pdg = mypkg.engine:PDGEngine`

### 2.3 Engine → state-space mapping (product truth)

| Engine | State | Best teaching sequences | Reference spine |
|---|---|---|---|
| **Bloch** | isochromats M_xyz(r,Δω) | SE, GRE, bSSFP intro, slice profile (hard pulses) | any Bloch textbook + current MVP |
| **EPG** | config orders F_k, Z_k | TSE/CPMG, RF spoiling, hyperecho intuition | Weigel; imr-framework/epg; EPG-X single-pool |
| **Spectral** | multi-pool / chemical shift / MT-lite | MRS peaks, CEST z-spec *lite*, fat/water | EPG-X MT/BM layouts; later full BM |
| **PDG** (later plugin) | phase-distribution graph | arbitrary Pulseq, echo shapes, differentiable opt | Endres 2024; pulseq-zero + MRzeroCore |

MVP product path stays: **SE/GRE → Bloch**, **TSE → EPG** (once EPG real). Spectral registered with a minimal two-pool demo, not full CEST.

---

## 3. Operator contracts (implement from refs)

### 3.1 RF — Weigel / EPG `rf_rotation(φ, α)`

For each configuration order k (and for Bloch as the k=0 spatial sample):

\[
\begin{bmatrix} F^+ \\ F^- \\ Z \end{bmatrix}
\leftarrow
T(\phi,\alpha)
\begin{bmatrix} F^+ \\ F^- \\ Z \end{bmatrix}
\]

with (angles in radians; match [imr-framework/epg `rf_rotation`](https://github.com/imr-framework/epg)):

```text
T00 = cos²(α/2)
T01 = e^{+2iφ} sin²(α/2)
T02 = -i e^{+iφ} sin(α)
T10 = e^{-2iφ} sin²(α/2)
T11 = cos²(α/2)
T12 = +i e^{-iφ} sin(α)
T20 = -i/2 e^{-iφ} sin(α)
T21 = +i/2 e^{+iφ} sin(α)
T22 = cos(α)
```

**Bloch path:** same rotation in Cartesian after converting (F+,F−,Z)↔(Mx,My,Mz), or direct Rodrigues about axis `(cos φ, sin φ, 0)`.

**Hard-pulse approximation (Bloch, options.rf_mode=`hard`):** subdivide finite RF window from IR into N instantaneous flips + free precession (Endres leaves full non-instantaneous for future; we still teach finite duration).

### 3.2 Relaxation

`E1 = exp(-dt/T1)`, `E2 = exp(-dt/T2)`  
k=0: Z ← E1·Z + (1-E1)·M0; F± ← E2·F±  
k≠0: no regrowth on Z_k.

### 3.3 Gradient / shift

**EPG:** integer `dk` shift of F populations; Z fixed; Hermitian re-fold at F0 (Weigel; EPG-X `EPG_shift_matrices`).  
**Bloch:** `φ += γ · G · r · dt` (+ optional ΔB0).  
**IR scheduler rule:** between RF/ADC events, integrate gx/gy/gz; EPG quantizes dephase to nearest teaching `dk` using `EngineOptions.epg_dk_scale` (document assumption).

### 3.4 Diffusion (EPG phase 2)

Port *semantics* of EPG-X `E_diff` / `EPG_diffusion_weights`: diagonal attenuations b_L(k), b_T(k) on longitudinal/transverse configs. Requires `Phantom.d_iso` and gradient intervals with G=0 gaps included (sum τ = TR).

### 3.5 Exchange / MT (Spectral / EPG-X phase 3)

State layouts from EPG-X README:
- MT: `[F0A F0A* Z0A Z0B F1A …]` (Z only on bound pool)  
- BM: 6 states/order `[F0A F0A* Z0A F0B F0B* Z0B …]`  
Shift matrices: `EPGX_BM_shift_matrices`, `EPGX_MT_shift_matrices`.

### 3.6 PDG (phase 3+ adapter)

Do **not** reimplement full PDG in-kernel first. Provide:
- `PDGEngine` plugin that either (a) translates IR → minimal mr0 sequence when `MRQLAB_INSTALL_HEAVY=1`, or (b) stays stub with message pointing to Endres + pulseq-zero.
- Kernel remains numpy-first for teaching Cloud/Pi.

---

## 4. IR → operator stream (kernel scheduler)

**File:** `kernel/scheduler.py`

Algorithm:
1. Merge all channel timestamps → sorted unique knots `t[i]`.
2. At each knot, emit instantaneous ops: RF edges (use `rf_amp` deg + `rf_phase` deg), ADC rising/falling (sample grid inside gate using `options.dwell_time` + NCO).
3. Between knots, emit `GradIntervalOp` + `RelaxOp` with `dt = t[i+1]-t[i]`.
4. Optional: coalesce zero-gradient pure relax.

**Units (lock in `units.py` + tests):**
- IR `rf_amp` stays **degrees** (current templates); convert at boundary.  
- Time always **seconds**.  
- Grad teaching units: dimensionless template ±1 → `ScannerModel.gradient_scale` (document; later mT/m).

**Caps (`kernel/caps.py`):**
```text
work ≈ n_isochromats * n_time_steps * cost_engine
      + n_epg_orders^2 * n_pulses   # EPG
reject if work > options.max_work or n_isochromats > SIM_MAX_MATRIX^2
```
Replace misuse of `SIM_MAX_RUNTIME` as duration check; keep env knobs but interpret as **wall-clock soft budget** measured around `simulate()`.

---

## 5. Phantom / options upgrades

```python
@dataclass
class Isochromat:
    m0: float = 1.0
    t1: float = 1.0
    t2: float = 0.1
    df_hz: float = 0.0
    r: tuple[float, float, float] = (0.0, 0.0, 0.0)
    d_iso: float = 0.0          # m^2/s, optional
    pool: str = "water"         # spectral

@dataclass
class Phantom:
    spins: list[Isochromat] = field(default_factory=lambda: [Isochromat()])
    # convenience ctor keeps old fields as single-spin sugar
    t1: float = 1.0
    ...
```

`EngineOptions` adds:
- `engine`-specific: `epg_kmax`, `epg_dk_scale`, `rf_mode: instant|hard`, `hard_pulse_n`
- `max_work: int`, `return_configurations: bool`

---

## 6. Step-by-step tasks

### Task 1: Branch + docs spine

**Objective:** Create branch and physics design doc so implementers share one map.

**Files:**
- Create: `docs/PHYSICS.md` (operator equations, refs, state layouts, non-goals)
- Modify: `docs/ARCHITECTURE.md` (microkernel diagram + plugin entry points)
- Modify: `docs/ROADMAP.md` (this follow-up as “Physics v1”)

**Steps:**
1. `git checkout -b feature/physics-microkernel` from PR#1 tip.  
2. Write `docs/PHYSICS.md` with §2–3 of this plan condensed + citations.  
3. Commit: `docs: physics microkernel design spine`

---

### Task 2: Package layout move (no behavior change)

**Objective:** Split `engines.py` into package dirs without breaking imports.

**Files:**
- Create: `mrqlab_physics/engines/{bloch_engine,epg_engine,spectral_engine,__init__}.py`
- Create: `mrqlab_physics/kernel/`, `ops/`, `backends/` (`__init__.py` only first)
- Modify: `registry.py`, `__init__.py`
- Keep shim: `engines.py` re-export for one release

**Test:** existing `pytest tests/test_physics.py tests/test_api.py` still 7 passed.

**Commit:** `refactor(physics): split engines package for microkernel`

---

### Task 3: Units + caps + work estimator

**Files:**
- Create: `kernel/units.py`, `kernel/caps.py`
- Modify: `models.EngineOptions`, `services/api` simulate path if it dual-checks duration
- Test: `tests/test_caps.py`

```python
def test_caps_reject_huge_matrix():
    with pytest.raises(ValueError, match="work|matrix"):
        estimate_or_raise(n_spins=10_000, n_steps=10_000, engine="bloch")
```

**Commit:** `feat(physics): work-based simulation caps`

---

### Task 4: Shared RF / relax operators + golden tests vs epg ref

**Objective:** Numpy ops matching imr-framework/epg numerics within 1e-10 on known angles.

**Files:**
- Create: `ops/rf.py`, `ops/relax.py`
- Create: `tests/test_ops_rf_relax.py`
- Optional fixture: generate expected T matrices independently (do not import GPL if any; epg is check license — imr-framework/epg is typically open; still reimplement)

**Cases:**
- α=90°, φ=0: Mz→My style checks in Cartesian  
- α=180°, φ=90°: sign patterns on F±  
- relax dt=T2*ln2 → transverse ×0.5  

**Commit:** `feat(physics): Weigel RF and relax operators`

---

### Task 5: IR scheduler → Op stream

**Files:**
- Create: `kernel/scheduler.py`
- Test: `tests/test_scheduler.py` on `build_sequence("SE")`  
  Assert: one ~90 RF, one ~180 RF, ADC samples near TE, relax/grad intervals cover [0,TR].

**Commit:** `feat(physics): SequenceIR to operator stream scheduler`

---

### Task 6: Bloch backend multi-isochromat rewrite

**Objective:** Replace loop in current `BlochEngine` with backend applying ops; support N spins and RF phase.

**Files:**
- Create: `backends/bloch.py`
- Modify: `engines/bloch_engine.py`
- Modify: `models.Phantom` sugar
- Tests:
  - SE echo peak near TE for T2-weighted decay  
  - off-resonance fan → FID dephase  
  - RF phase 90° rotates about y  

```python
def test_se_echo_forms():
    seq = build_sequence("SE", {"te": 0.04, "tr": 0.2})
    r = get_engine("bloch").simulate(seq, Phantom(t2=0.08), ScannerModel(), EngineOptions(dwell_time=5e-4))
    assert abs(r.signal).max() > 0.1
```

**Commit:** `feat(physics): multi-isochromat Bloch engine via operators`

---

### Task 7: EPG backend classic (kmax, shift, RF, relax)

**Objective:** Real `EPGEngine` for discrete RF + integer shifts; TSE echo train amplitudes.

**Files:**
- Create: `backends/epg.py`, `ops/shift.py`
- Modify: `engines/epg_engine.py`
- Tests: `tests/test_epg_tse.py`
  - Ideal 90y–180x CPMG: odd echoes ~ stable (within relax)  
  - Compare echo mags vs hand-computed 2–3 pulse pathway  
  - `kmax` pruning does not crash; meta includes `kmax`, `n_orders`

**Scheduler bridge:** `ShiftOp.dk` from integrated crusher area via `epg_dk_scale` (default: each TSE crusher → dk=1).

**Commit:** `feat(physics): classic EPG engine for TSE teaching`

---

### Task 8: Wire engine auto-pick + API

**Objective:** Templates declare preferred engine; API can override.

**Files:**
- Modify: `sequence` templates metadata `preferred_engine`: SE/GRE→`bloch`, TSE→`epg`
- Modify: `services/api/mrqlab_api/main.py` simulate body `engine: str | None = None`
- Modify: `list_engines()` → `available: true` for bloch+epg
- Tests: API simulate TSE with engine=epg returns samples; unknown engine 400

**Commit:** `feat(api): select bloch/epg engines end-to-end`

---

### Task 9: Spectral engine v0 (two-pool isochromat)

**Objective:** Not full CEST — two chemical-shift pools, independent Bloch, summed signal; proves third plugin.

**Files:**
- Create: `backends/spectral.py`, `engines/spectral_engine.py`
- Phantom: `spins` with `df_hz` + `pool` weights  
- Test: fat/water 3.5 ppm @ 1.5 T → beat in FID  

**Commit:** `feat(physics): spectral two-pool engine v0`

---

### Task 10: Registry entry points + plugin smoke

**Files:**
- Modify: `registry.py` load `importlib.metadata.entry_points(group="mrqlab.physics_engines")`
- Create: `tests/test_registry_plugins.py` with monkeypatched entry point  
- Doc: how to add PDG plugin without touching kernel  

**Commit:** `feat(physics): entry-point plugin loading`

---

### Task 11: EPG-X hooks (diffusion + BM layout stubs)

**Objective:** Land structure, not full biology.

**Files:**
- Create: `ops/diffuse.py` (numpy port of weight formulas; cite Malik)  
- Create: `backends/epg_x.py` with state layout constants + `NotImplementedError` for full BM simulate OR minimal exchange-free dual-pool F states  
- Doc section in PHYSICS.md  
- Test: diffusion weights monotonic in k and D  

**Commit:** `feat(physics): EPG-X diffusion weights and BM layout stubs`

---

### Task 12: PDG adapter stub + reference notebook/script

**Files:**
- Create: `backends/pdg.py` / `engines/pdg_engine.py` registered `available=False` unless heavy extras  
- Create: `docs/references.md` linking local `/opt/data/tmp/mrq-refs/*` and papers  
- Create: `scripts/compare_epg_ref.py` optional offline compare  

**Commit:** `docs(physics): PDG adapter seam and reference index`

---

### Task 13: Cross-engine consistency suite

**Objective:** Where physics overlap, engines agree.

**Tests:** `tests/test_cross_engine.py`
- Single spin, no gradient, one 90° pulse: Bloch |Mxy| ≈ EPG |F0|  
- SE with crushers disabled / dk=0 path: echo time alignment  

**Commit:** `test(physics): cross-engine consistency gates`

---

### Task 14: Performance + teaching meta

- `SimResult.meta`: `engine`, `n_spins`, `n_ops`, `kmax`, `assumptions[]`  
- Reality-slider hooks later read `assumptions`  
- Benchmark mark: TSE 16 echoes EPG < 100 ms on CPU for default kmax  

**Commit:** `feat(physics): rich meta and basic perf guard`

---

## 7. Files likely to change (summary)

| Path | Action |
|---|---|
| `packages/physics/mrqlab_physics/**` | major expand |
| `packages/sequence-ir/mrqlab_sequence/templates.py` | preferred_engine metadata |
| `services/api/mrqlab_api/main.py` | engine select + cap errors |
| `tests/test_*.py` | many new |
| `docs/{ARCHITECTURE,ROADMAP,PHYSICS,references}.md` | design |
| `pyproject.toml` | packages + optional extras `epg`, `heavy` |
| `README.md` | engine table |

---

## 8. Validation

```bash
cd /opt/data/workspace/MRQlab
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'   # numpy pydantic fastapi pytest httpx
make test                 # or: pytest -q
# expected after full plan: >>7 tests, bloch+epg+spectral available
```

Manual golden:
1. `build_sequence("TSE", {echoes:8})` + EPG → decaying echo train plot data in meta/signal  
2. Same sequence + Bloch multi-isochromat with crushers → qualitatively similar envelope (not bit-identical)  
3. `/engines` lists availability flags correctly  

---

## 9. Risks & decisions

| Risk | Mitigation |
|---|---|
| EPG dk quantization from arbitrary IR grads is ambiguous | Teaching default: template-emitted crushers carry `metadata.dk`; scheduler prefers explicit dk tags on events (extend IR if needed) |
| License contamination from MATLAB/Python refs | Reimplement + cite; no file copy |
| PDG/torch too heavy for Cloud/Pi | Adapter + extras; kernel numpy |
| Over-building BM/CEST | Spectral v0 = two-pool only; BM stub |
| TSE template still “fake crushers” | Task 7 may add `metadata={"dk":1}` on grad events — small IR extension allowed |

**Open questions for user (non-blocking defaults in parentheses):**
1. EPG dk: explicit IR metadata tags (**default**) vs pure area quantization?  
2. PDG: stub-only this follow-up (**default**) vs optional MRzero extra?  
3. Merge PR#1 to main before this branch (**yes**)?  

---

## 10. Suggested execution order for agents

1. Tasks 1–2 (docs + layout)  
2. Tasks 3–5 (caps, ops, scheduler)  
3. Task 6 Bloch rewrite (keeps product alive)  
4. Task 7–8 EPG + API  
5. Task 9 Spectral v0  
6. Tasks 10–14 plugins, EPG-X hooks, PDG seam, consistency  

After each task: pytest green + commit. No drive-by web CSS.

---

## 11. One-slide mental model

> **Kernel** = event-stream physics OS (schedule, units, caps, registry).  
> **Operators** = syscalls (RF, relax, shift, sample).  
> **Engines** = process implementations over different address spaces (isochromats / k-configs / pools / later PDG graphs).  
> **SequenceIR** = only userland bytecode. MaRCoS taught us the bytecode shape; Weigel/EPG-X/PDG teach the syscalls; pulseq-zero shows a future optimized runtime — we don’t embed it in the kernel.
