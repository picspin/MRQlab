# Physics Engines Microkernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a NumPy-first physics microkernel that schedules `SequenceIR` once and runs production Bloch, classic EPG, and fat/water spectral engines through the existing unified simulation API.

**Architecture:** The microkernel converts the MaRCoS-like event stream into typed operators, enforces units and work caps, executes backend state machines, and discovers engines. Built-in and entry-point plugins own only their state representation and operator application, while recon, API, and web remain consumers of `SimResult` and never bind to a concrete engine.

**Tech Stack:** Python >=3.11, NumPy >=1.26, Pydantic >=2, FastAPI >=0.110, pytest >=8, `importlib.metadata`; no required torch, MRzero, pulseq-zero, PyPulseq, SciPy, or SigPy dependency.

**Spec:** `docs/superpowers/specs/2026-08-14-physics-engines-microkernel.md`

## Global Constraints

- Preserve the dependency direction `sequence-ir → physics → recon → api → web`.
- Preserve `SimulationEngine.simulate(sequence: SequenceIR, phantom: Phantom, scanner: ScannerModel, options: EngineOptions) -> SimResult` as the public engine seam.
- Keep `SequenceIR` as the sole event source with channels `rf_amp`, `rf_phase`, `gx`, `gy`, `gz`, `adc_gate`, `nco_freq`, and `nco_phase`.
- Interpret IR RF amplitude and phase as degrees, convert once at the scheduler boundary, and use radians inside physics.
- Interpret all public time values as seconds.
- Interpret existing gradient values as dimensionless teaching units multiplied by `ScannerModel.gradient_scale` in Hz/m.
- Prefer `SequenceIR.metadata["epg_dk_events"]` for EPG shifts; use gradient-area quantization only when explicit tags are absent.
- Reject work from estimated operator count × backend state width before allocating backend arrays; do not use sequence duration as a runtime proxy.
- Keep NumPy as the only physics array runtime in the default install.
- Reimplement equations and cite sources; do not copy or vendor upstream repository code.
- Keep PDG behind a provider adapter seam and keep Bloch–McConnell/MT behind explicit typed EPG-X extension errors.
- Keep this educational only: no clinical claims, scanner safety claims, acquisition control, MaRCoS hardware connection, or Red Pitaya integration.
- Every task begins with a failing test, implements the smallest passing behavior, runs focused tests, runs the relevant regression set, and creates one reviewable commit.

---

## File and Module Map

| Path | Action | Single responsibility |
|---|---|---|
| `packages/physics/mrqlab_physics/base.py` | Modify | Stable engine ABC and availability metadata only. |
| `packages/physics/mrqlab_physics/models.py` | Modify | Public phantom, isochromat, spectral-pool, scanner, options, and result dataclasses. |
| `packages/physics/mrqlab_physics/engines.py` | Delete | Replaced by the import-compatible `engines` package. |
| `packages/physics/mrqlab_physics/engines/__init__.py` | Create | Re-export built-in engine classes from focused modules. |
| `packages/physics/mrqlab_physics/engines/bloch_engine.py` | Create | Bloch engine orchestration; no Bloch state math. |
| `packages/physics/mrqlab_physics/engines/epg_engine.py` | Create | EPG engine orchestration; no EPG state math. |
| `packages/physics/mrqlab_physics/engines/spectral_engine.py` | Create | Spectral engine orchestration; no pool state math. |
| `packages/physics/mrqlab_physics/kernel/units.py` | Create | Degree/radian and teaching-gradient conversions. |
| `packages/physics/mrqlab_physics/kernel/caps.py` | Create | Pure work estimator and pre-allocation rejection. |
| `packages/physics/mrqlab_physics/kernel/scheduler.py` | Create | Deterministic `SequenceIR` → typed operator tuple conversion. |
| `packages/physics/mrqlab_physics/kernel/runner.py` | Create | Backend-neutral operator execution, ADC collection, k-trajectory, and snapshots. |
| `packages/physics/mrqlab_physics/ops/types.py` | Create | Immutable `RfOp`, `Relax`, `Shift`, `GradInterval`, and `AdcSample` contracts. |
| `packages/physics/mrqlab_physics/ops/rf.py` | Create | Weigel EPG RF matrix and Cartesian Rodrigues rotation. |
| `packages/physics/mrqlab_physics/ops/relax.py` | Create | T1/T2 exponential factors and validation. |
| `packages/physics/mrqlab_physics/ops/sample.py` | Create | Shared NCO demodulation convention. |
| `packages/physics/mrqlab_physics/ops/diffuse.py` | Create | EPG-X-compatible diffusion attenuation hook. |
| `packages/physics/mrqlab_physics/backends/protocol.py` | Create | Minimal state-backend protocol consumed by the runner. |
| `packages/physics/mrqlab_physics/backends/bloch.py` | Create | Vectorized multi-isochromat Cartesian state. |
| `packages/physics/mrqlab_physics/backends/epg.py` | Create | Bounded classic signed-order configuration state. |
| `packages/physics/mrqlab_physics/backends/spectral.py` | Create | Pool expansion and chemical-shift Bloch state. |
| `packages/physics/mrqlab_physics/backends/epg_x.py` | Create | BM/MT layouts and explicit unsupported-feature seams. |
| `packages/physics/mrqlab_physics/backends/pdg.py` | Create | Provider protocol and optional PDG adapter; not a built-in engine. |
| `packages/physics/mrqlab_physics/registry.py` | Replace | Built-in factories plus `mrqlab.physics_engines` entry-point discovery. |
| `packages/sequence-ir/mrqlab_sequence/templates.py` | Modify | Preferred-engine and explicit EPG shift metadata emitted by templates. |
| `services/api/mrqlab_api/main.py` | Modify | Optional engine selection and server-owned maximum-work cap. |
| `pyproject.toml` | Modify | Discover subpackages and declare the entry-point group contract in docs metadata. |
| `tests/physics/` | Create | Focused unit, golden, backend, plugin, seam, and consistency tests. |
| `tests/test_api.py` | Modify | Engine override, automatic TSE selection, and cap HTTP tests. |
| `docs/PHYSICS.md` | Create | Equations, conventions, assumptions, citations, and extension boundaries. |
| `docs/ARCHITECTURE.md` | Modify | Microkernel ownership and dependency diagram. |
| `docs/ROADMAP.md` | Modify | Mark three engines as physics v1 and retain richer models as later work. |
| `README.md` | Modify | User-visible engine table and selection examples. |

## Stable Contracts Used by Every Task

```python
# packages/physics/mrqlab_physics/ops/types.py
from dataclasses import dataclass
from typing import TypeAlias

@dataclass(frozen=True, slots=True)
class RfOp:
    t: float
    alpha_rad: float
    phase_rad: float

@dataclass(frozen=True, slots=True)
class Relax:
    t: float
    dt: float

@dataclass(frozen=True, slots=True)
class Shift:
    t: float
    dk: tuple[int, int, int]
    source: str

@dataclass(frozen=True, slots=True)
class GradInterval:
    t: float
    dt: float
    gradient: tuple[float, float, float]

@dataclass(frozen=True, slots=True)
class AdcSample:
    t: float
    nco_frequency_hz: float
    nco_phase_rad: float

Operator: TypeAlias = RfOp | Relax | Shift | GradInterval | AdcSample
```

```python
# packages/physics/mrqlab_physics/backends/protocol.py
from typing import Protocol
import numpy as np
from ..ops.types import AdcSample, Operator

class StateBackend(Protocol):
    def apply(self, op: Operator) -> None: ...
    def observe(self, op: AdcSample) -> complex: ...
    def snapshot(self) -> np.ndarray: ...
```

The scheduler ordering at a timestamp is `RfOp`, `Shift`, `AdcSample`, then interval `Relax` and `GradInterval`. Thus an ADC at `t` observes all evolution ending at `t`, but none of the interval beginning at `t`. `RfOp` is an instantaneous hard-pulse contract in this follow-up; finite-waveform RF is outside the locked scope.

### Task 1: Split the Physics Layout Without Changing Behavior

**Files:**
- Delete: `packages/physics/mrqlab_physics/engines.py`
- Create: `packages/physics/mrqlab_physics/engines/__init__.py`
- Create: `packages/physics/mrqlab_physics/engines/bloch_engine.py`
- Create: `packages/physics/mrqlab_physics/engines/epg_engine.py`
- Create: `packages/physics/mrqlab_physics/engines/spectral_engine.py`
- Create: `packages/physics/mrqlab_physics/kernel/__init__.py`
- Create: `packages/physics/mrqlab_physics/ops/__init__.py`
- Create: `packages/physics/mrqlab_physics/backends/__init__.py`
- Modify: `packages/physics/mrqlab_physics/base.py`
- Modify: `pyproject.toml`
- Test: `tests/physics/test_layout.py`

**Interfaces:**
- Consumes: Existing `SimulationEngine`, `Phantom`, `ScannerModel`, `EngineOptions`, and `SimResult` imports.
- Produces: `mrqlab_physics.engines.{BlochEngine, EPGEngine, SpectralEngine}` and recursively discoverable package modules.

- [ ] **Step 1: Write the failing package-layout test**

```python
# tests/physics/test_layout.py
from mrqlab_physics.engines.bloch_engine import BlochEngine
from mrqlab_physics.engines.epg_engine import EPGEngine
from mrqlab_physics.engines.spectral_engine import SpectralEngine

def test_engine_modules_are_importable_from_split_package():
    assert BlochEngine.name == "bloch"
    assert EPGEngine.name == "epg"
    assert SpectralEngine.name == "spectral"
```

- [ ] **Step 2: Run the test and verify the old module layout fails**

Run: `python3.11 -m pytest tests/physics/test_layout.py -q`

Expected: FAIL during collection because `mrqlab_physics.engines` is a module, not a package.

- [ ] **Step 3: Move the existing engines into focused modules and add availability metadata**

```python
# packages/physics/mrqlab_physics/base.py
from abc import ABC, abstractmethod
from mrqlab_sequence import SequenceIR
from .models import EngineOptions, Phantom, ScannerModel, SimResult

class SimulationEngine(ABC):
    name: str
    description: str
    available: bool = True

    @abstractmethod
    def simulate(
        self,
        sequence: SequenceIR,
        phantom: Phantom,
        scanner: ScannerModel,
        options: EngineOptions,
    ) -> SimResult: ...
```

Use this exact behavior-preserving Bloch module until Task 5 replaces its solver:

```python
# packages/physics/mrqlab_physics/engines/bloch_engine.py
import time
import numpy as np
from ..base import SimulationEngine
from ..models import EngineOptions, Phantom, ScannerModel, SimResult

class BlochEngine(SimulationEngine):
    name = "bloch"
    description = "MVP single-isochromat Bloch simulation"

    def simulate(self, sequence, phantom: Phantom, scanner: ScannerModel, options: EngineOptions):
        started = time.perf_counter()
        dt = options.dwell_time
        times = np.arange(0, sequence.duration + dt / 2, dt)
        magnetization = np.empty((len(times), 3))
        state = np.array([0.0, 0.0, phantom.proton_density])
        pulses = sequence.channel("rf_amp")
        pulse_index = 0
        for index, t in enumerate(times):
            while pulse_index < len(pulses) and pulses[pulse_index].time <= t + dt / 2:
                alpha = np.deg2rad(pulses[pulse_index].value)
                x, y, z = state
                state = np.array([
                    x,
                    y * np.cos(alpha) - z * np.sin(alpha),
                    y * np.sin(alpha) + z * np.cos(alpha),
                ])
                pulse_index += 1
            if index:
                phase = 2 * np.pi * phantom.off_resonance_hz * dt
                transverse = (state[0] + 1j * state[1]) * np.exp(-dt / phantom.t2 + 1j * phase)
                state = np.array([
                    transverse.real,
                    transverse.imag,
                    phantom.proton_density - (
                        phantom.proton_density - state[2]
                    ) * np.exp(-dt / phantom.t1),
                ])
            magnetization[index] = state
        windows: list[tuple[float, float]] = []
        active = None
        for event in sequence.channel("adc_gate"):
            if event.value and active is None:
                active = event.time
            elif not event.value and active is not None:
                windows.append((active, event.time))
                active = None
        sample_mask = np.array([any(start <= t < stop for start, stop in windows) for t in times])
        signal = (magnetization[:, 0] + 1j * magnetization[:, 1])[sample_mask]
        return SimResult(
            signal=signal,
            magnetization=magnetization if options.return_magnetization else None,
            k_trajectory=np.zeros((len(signal), 3)),
            meta={"engine": self.name, "samples": len(signal)},
            timing={"simulation_seconds": time.perf_counter() - started},
        )
```

Use these exact transitional modules for the two later replacements:

```python
# packages/physics/mrqlab_physics/engines/epg_engine.py
from ..base import SimulationEngine

class EPGEngine(SimulationEngine):
    name = "epg"
    description = "Classic extended phase graph"
    available = False

    def simulate(self, sequence, phantom, scanner, options):
        raise NotImplementedError("epg engine requires the classic EPG backend")
```

```python
# packages/physics/mrqlab_physics/engines/spectral_engine.py
from ..base import SimulationEngine

class SpectralEngine(SimulationEngine):
    name = "spectral"
    description = "Independent chemical-shift pools"
    available = False

    def simulate(self, sequence, phantom, scanner, options):
        raise NotImplementedError("spectral engine requires spectral pools")
```

```python
# packages/physics/mrqlab_physics/engines/__init__.py
from .bloch_engine import BlochEngine
from .epg_engine import EPGEngine
from .spectral_engine import SpectralEngine

__all__ = ["BlochEngine", "EPGEngine", "SpectralEngine"]
```

Create `kernel/__init__.py`, `ops/__init__.py`, and `backends/__init__.py` with `__all__: list[str] = []`. Delete both the existing `[tool.setuptools]` explicit package table and `[tool.setuptools.package-dir]` table, then add discovery:

```toml
[tool.setuptools.packages.find]
where = ["packages/sequence-ir", "packages/physics", "packages/recon", "services/api"]
include = ["mrqlab_sequence*", "mrqlab_physics*", "mrqlab_recon*", "mrqlab_api*"]
```

- [ ] **Step 4: Run layout and current regressions**

Run: `python3.11 -m pytest tests/physics/test_layout.py tests/test_physics.py -q`

Expected: PASS with 5 tests; the existing API suite may still require a clean editable environment because the workstation global `httpx` is incompatible.

- [ ] **Step 5: Commit the behavior-preserving split**

```bash
git add pyproject.toml packages/physics/mrqlab_physics tests/physics/test_layout.py
git commit -m "refactor(physics): split engine package layout"
```

### Task 2: Add Public Models, Unit Conversions, and Work Caps

**Files:**
- Modify: `packages/physics/mrqlab_physics/models.py`
- Create: `packages/physics/mrqlab_physics/kernel/units.py`
- Create: `packages/physics/mrqlab_physics/kernel/caps.py`
- Modify: `packages/physics/mrqlab_physics/__init__.py`
- Test: `tests/physics/test_models_caps.py`

**Interfaces:**
- Consumes: Python dataclasses and NumPy array result types.
- Produces: `Isochromat`, `SpectralPool`, `Phantom.resolved_isochromats()`, validated `EngineOptions`, `deg_to_rad`, `estimate_work`, and `enforce_work_limit`.

- [ ] **Step 1: Write failing tests for compatibility, units, and pre-allocation rejection**

```python
# tests/physics/test_models_caps.py
import numpy as np
import pytest
from mrqlab_physics import EngineOptions, Isochromat, Phantom
from mrqlab_physics.kernel.caps import enforce_work_limit, estimate_work
from mrqlab_physics.kernel.units import deg_to_rad

def test_legacy_phantom_resolves_to_one_isochromat():
    spins = Phantom(t1=0.9, t2=0.08, proton_density=0.7, off_resonance_hz=12).resolved_isochromats()
    assert spins == (Isochromat(t1=0.9, t2=0.08, proton_density=0.7, off_resonance_hz=12),)

def test_ir_degrees_convert_once_at_boundary():
    assert deg_to_rad(180.0) == pytest.approx(np.pi)

def test_engine_work_models_state_width():
    assert estimate_work("bloch", n_ops=10, n_isochromats=4, epg_kmax=8, n_pools=1) == 40
    assert estimate_work("epg", n_ops=10, n_isochromats=1, epg_kmax=8, n_pools=1) == 510
    assert estimate_work("spectral", n_ops=10, n_isochromats=3, epg_kmax=8, n_pools=2) == 60

def test_work_cap_rejects_before_backend_allocation():
    with pytest.raises(ValueError, match="estimated work 510 exceeds max_work 500"):
        enforce_work_limit("epg", 10, 1, EngineOptions(epg_kmax=8, max_work=500), 1)
```

- [ ] **Step 2: Run the focused tests and verify missing symbols fail**

Run: `python3.11 -m pytest tests/physics/test_models_caps.py -q`

Expected: FAIL during import because `Isochromat`, `kernel.units`, and `kernel.caps` do not exist.

- [ ] **Step 3: Implement the complete public dataclasses**

```python
# packages/physics/mrqlab_physics/models.py
from dataclasses import dataclass, field
from typing import Any
import numpy as np

@dataclass(frozen=True, slots=True)
class Isochromat:
    t1: float = 1.0
    t2: float = 0.1
    proton_density: float = 1.0
    off_resonance_hz: float = 0.0
    position_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    weight: float = 1.0

    def __post_init__(self):
        if self.t1 <= 0 or self.t2 <= 0:
            raise ValueError("isochromat t1 and t2 must be positive")
        if self.proton_density < 0 or self.weight < 0:
            raise ValueError("isochromat proton_density and weight must be non-negative")

@dataclass(frozen=True, slots=True)
class SpectralPool:
    name: str
    fraction: float
    chemical_shift_ppm: float
    t1: float
    t2: float

    def __post_init__(self):
        if self.fraction < 0 or self.t1 <= 0 or self.t2 <= 0:
            raise ValueError("spectral pool fraction must be non-negative and relaxation times positive")

@dataclass(slots=True)
class Phantom:
    t1: float = 1.0
    t2: float = 0.1
    proton_density: float = 1.0
    off_resonance_hz: float = 0.0
    isochromats: tuple[Isochromat, ...] = ()
    pools: tuple[SpectralPool, ...] = ()

    def resolved_isochromats(self) -> tuple[Isochromat, ...]:
        if self.isochromats:
            return self.isochromats
        return (Isochromat(self.t1, self.t2, self.proton_density, self.off_resonance_hz),)

@dataclass(frozen=True, slots=True)
class ScannerModel:
    b0_t: float = 1.5
    gradient_scale: float = 1.0

    def __post_init__(self):
        if self.b0_t <= 0 or self.gradient_scale < 0:
            raise ValueError("scanner b0_t must be positive and gradient_scale non-negative")

@dataclass(frozen=True, slots=True)
class EngineOptions:
    dwell_time: float = 0.001
    return_magnetization: bool = True
    return_configurations: bool = False
    epg_kmax: int = 64
    epg_dk_scale: float = 0.001
    max_work: int = 2_000_000

    def __post_init__(self):
        if self.dwell_time <= 0 or self.epg_dk_scale <= 0:
            raise ValueError("dwell_time and epg_dk_scale must be positive")
        if self.epg_kmax < 0 or self.max_work < 1:
            raise ValueError("epg_kmax must be non-negative and max_work positive")

@dataclass(slots=True)
class SimResult:
    signal: np.ndarray
    k_trajectory: np.ndarray
    magnetization: np.ndarray | None = None
    configurations: np.ndarray | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    timing: dict[str, float] = field(default_factory=dict)
```

Export `Isochromat` and `SpectralPool` from `mrqlab_physics.__init__` alongside the existing names.

- [ ] **Step 4: Implement units and deterministic integer work formulas**

```python
# packages/physics/mrqlab_physics/kernel/units.py
import numpy as np

def deg_to_rad(value: float) -> float:
    return float(np.deg2rad(value))

def gradient_hz_per_m(value: float, scale: float) -> float:
    return float(value * scale)
```

```python
# packages/physics/mrqlab_physics/kernel/caps.py
from ..models import EngineOptions

def estimate_work(
    engine: str,
    n_ops: int,
    n_isochromats: int,
    epg_kmax: int,
    n_pools: int,
) -> int:
    if min(n_ops, n_isochromats, n_pools) < 0:
        raise ValueError("work dimensions must be non-negative")
    widths = {
        "bloch": n_isochromats,
        "epg": 3 * (2 * epg_kmax + 1),
        "spectral": n_isochromats * n_pools,
    }
    try:
        return int(n_ops * widths[engine])
    except KeyError:
        raise ValueError(f"no work model for engine {engine!r}") from None

def enforce_work_limit(
    engine: str,
    n_ops: int,
    n_isochromats: int,
    options: EngineOptions,
    n_pools: int,
) -> int:
    work = estimate_work(engine, n_ops, n_isochromats, options.epg_kmax, n_pools)
    if work > options.max_work:
        raise ValueError(f"estimated work {work} exceeds max_work {options.max_work}")
    return work
```

- [ ] **Step 5: Run focused and legacy physics tests**

Run: `python3.11 -m pytest tests/physics/test_models_caps.py tests/test_physics.py -q`

Expected: PASS with 8 tests.

- [ ] **Step 6: Commit the models and kernel policy**

```bash
git add packages/physics/mrqlab_physics tests/physics/test_models_caps.py
git commit -m "feat(physics): add units models and work caps"
```

### Task 3: Implement Shared Operator Contracts and Golden Math

**Files:**
- Create: `packages/physics/mrqlab_physics/ops/types.py`
- Create: `packages/physics/mrqlab_physics/ops/rf.py`
- Create: `packages/physics/mrqlab_physics/ops/relax.py`
- Create: `packages/physics/mrqlab_physics/ops/sample.py`
- Modify: `packages/physics/mrqlab_physics/ops/__init__.py`
- Test: `tests/physics/test_ops_golden.py`

**Interfaces:**
- Consumes: Internal radians, seconds, NumPy Cartesian arrays, and EPG state vectors ordered `(F+, F-, Z)`.
- Produces: The five immutable operator classes, `Operator`, `epg_rf_matrix`, `rotate_cartesian`, `relaxation_factors`, and `demodulate`.

- [ ] **Step 1: Write independent golden tests for phase convention and relaxation**

```python
# tests/physics/test_ops_golden.py
import numpy as np
import pytest
from mrqlab_physics.ops.relax import relaxation_factors
from mrqlab_physics.ops.rf import epg_rf_matrix, rotate_cartesian
from mrqlab_physics.ops.sample import demodulate
from mrqlab_physics.ops.types import AdcSample, GradInterval, Relax, RfOp, Shift

def test_operator_contract_fields_are_explicit():
    assert RfOp(0.0, np.pi / 2, 0.0).alpha_rad == pytest.approx(np.pi / 2)
    assert Relax(0.0, 0.01).dt == 0.01
    assert Shift(0.01, (1, 0, 0), "metadata").source == "metadata"
    assert GradInterval(0.0, 0.01, (1.0, 0.0, 0.0)).gradient[0] == 1.0
    assert AdcSample(0.02, 0.0, 0.0).t == 0.02

def test_epg_rf_90_x_has_weigel_coefficients():
    matrix = epg_rf_matrix(np.pi / 2, 0.0)
    expected = np.array([
        [0.5, 0.5, -1j],
        [0.5, 0.5, 1j],
        [-0.5j, 0.5j, 0.0],
    ])
    np.testing.assert_allclose(matrix, expected, atol=1e-12)

def test_cartesian_rf_phase_changes_rotation_axis():
    state = np.array([[0.0, 0.0, 1.0]])
    np.testing.assert_allclose(rotate_cartesian(state, np.pi / 2, 0.0), [[0.0, -1.0, 0.0]], atol=1e-12)
    np.testing.assert_allclose(rotate_cartesian(state, np.pi / 2, np.pi / 2), [[1.0, 0.0, 0.0]], atol=1e-12)

def test_relaxation_half_life_and_nco_demodulation():
    e1, e2 = relaxation_factors(np.log(2), 2 * np.log(2), np.log(2))
    assert e1 == pytest.approx(2 ** -0.5)
    assert e2 == pytest.approx(0.5)
    assert demodulate(1 + 0j, t=0.25, frequency_hz=1.0, phase_rad=0.0) == pytest.approx(-1j)
```

- [ ] **Step 2: Run the golden file and verify imports fail**

Run: `python3.11 -m pytest tests/physics/test_ops_golden.py -q`

Expected: FAIL during import because the operator modules do not exist.

- [ ] **Step 3: Add the exact operator contracts from the Stable Contracts section**

```python
# packages/physics/mrqlab_physics/ops/types.py
from dataclasses import dataclass
from typing import TypeAlias

@dataclass(frozen=True, slots=True)
class RfOp:
    t: float
    alpha_rad: float
    phase_rad: float

@dataclass(frozen=True, slots=True)
class Relax:
    t: float
    dt: float

@dataclass(frozen=True, slots=True)
class Shift:
    t: float
    dk: tuple[int, int, int]
    source: str

@dataclass(frozen=True, slots=True)
class GradInterval:
    t: float
    dt: float
    gradient: tuple[float, float, float]

@dataclass(frozen=True, slots=True)
class AdcSample:
    t: float
    nco_frequency_hz: float
    nco_phase_rad: float

Operator: TypeAlias = RfOp | Relax | Shift | GradInterval | AdcSample
```

```python
# packages/physics/mrqlab_physics/ops/__init__.py
from .types import AdcSample, GradInterval, Operator, Relax, RfOp, Shift

__all__ = ["AdcSample", "GradInterval", "Operator", "Relax", "RfOp", "Shift"]
```

- [ ] **Step 4: Implement RF, relaxation, and demodulation math**

```python
# packages/physics/mrqlab_physics/ops/rf.py
import numpy as np

def epg_rf_matrix(alpha_rad: float, phase_rad: float) -> np.ndarray:
    c2 = np.cos(alpha_rad / 2.0) ** 2
    s2 = np.sin(alpha_rad / 2.0) ** 2
    sa = np.sin(alpha_rad)
    ca = np.cos(alpha_rad)
    p1 = np.exp(1j * phase_rad)
    p2 = np.exp(2j * phase_rad)
    return np.array([
        [c2, p2 * s2, -1j * p1 * sa],
        [np.conj(p2) * s2, c2, 1j * np.conj(p1) * sa],
        [-0.5j * np.conj(p1) * sa, 0.5j * p1 * sa, ca],
    ], dtype=np.complex128)

def rotate_cartesian(state: np.ndarray, alpha_rad: float, phase_rad: float) -> np.ndarray:
    axis = np.array([np.cos(phase_rad), np.sin(phase_rad), 0.0])
    cosine = np.cos(alpha_rad)
    sine = np.sin(alpha_rad)
    projection = state @ axis
    return (
        state * cosine
        + np.cross(np.broadcast_to(axis, state.shape), state) * sine
        + projection[:, None] * axis * (1.0 - cosine)
    )
```

```python
# packages/physics/mrqlab_physics/ops/relax.py
import numpy as np

def relaxation_factors(dt: float, t1: float, t2: float) -> tuple[float, float]:
    if dt < 0 or t1 <= 0 or t2 <= 0:
        raise ValueError("dt must be non-negative and relaxation times positive")
    return float(np.exp(-dt / t1)), float(np.exp(-dt / t2))
```

```python
# packages/physics/mrqlab_physics/ops/sample.py
import numpy as np

def demodulate(value: complex, t: float, frequency_hz: float, phase_rad: float) -> complex:
    return complex(value * np.exp(-1j * (2.0 * np.pi * frequency_hz * t + phase_rad)))
```

- [ ] **Step 5: Run golden and model tests**

Run: `python3.11 -m pytest tests/physics/test_ops_golden.py tests/physics/test_models_caps.py -q`

Expected: PASS with 8 tests.

- [ ] **Step 6: Commit shared operator algebra**

```bash
git add packages/physics/mrqlab_physics/ops tests/physics/test_ops_golden.py
git commit -m "feat(physics): add shared operator contracts"
```

### Task 4: Build the IR Scheduler and Backend-Neutral Runner

**Files:**
- Create: `packages/physics/mrqlab_physics/kernel/scheduler.py`
- Create: `packages/physics/mrqlab_physics/kernel/runner.py`
- Create: `packages/physics/mrqlab_physics/backends/protocol.py`
- Test: `tests/physics/test_scheduler_runner.py`

**Interfaces:**
- Consumes: `SequenceIR`, `EngineOptions`, the five operator contracts, and `StateBackend`.
- Produces: `schedule(sequence, options) -> tuple[Operator, ...]`, `RuntimeTrace`, and `run_backend(backend, operators, return_snapshots) -> RuntimeTrace`.

- [ ] **Step 1: Write failing scheduler and runner tests**

```python
# tests/physics/test_scheduler_runner.py
import numpy as np
import pytest
from mrqlab_sequence import build_sequence
from mrqlab_physics import EngineOptions
from mrqlab_physics.kernel.runner import run_backend
from mrqlab_physics.kernel.scheduler import schedule
from mrqlab_physics.ops.types import AdcSample, GradInterval, Relax, RfOp, Shift

class RecordingBackend:
    def __init__(self):
        self.applied = []

    def apply(self, op):
        self.applied.append(op)

    def observe(self, op):
        return 1.0 + 0.0j

    def snapshot(self):
        return np.array([len(self.applied)], dtype=float)

def test_scheduler_pairs_rf_phase_and_samples_adc_dwell_grid():
    sequence = build_sequence("SE", {"te": 0.02, "tr": 0.1})
    sequence.metadata["epg_dk_events"] = [{"time": 0.005, "dk": [1, 0, 0]}]
    operators = schedule(sequence, EngineOptions(dwell_time=0.001))
    rf = [op for op in operators if isinstance(op, RfOp)]
    adc = [op for op in operators if isinstance(op, AdcSample)]
    shifts = [op for op in operators if isinstance(op, Shift)]
    assert [op.alpha_rad for op in rf] == pytest.approx([np.pi / 2, np.pi])
    assert [op.t for op in adc] == pytest.approx([0.02, 0.021])
    assert shifts == [Shift(0.005, (1, 0, 0), "metadata")]
    assert sum(op.dt for op in operators if isinstance(op, Relax)) == pytest.approx(0.1)
    assert sum(op.dt for op in operators if isinstance(op, GradInterval)) == pytest.approx(0.1)

def test_runner_samples_after_prior_intervals_and_tracks_k():
    sequence = build_sequence("GRE", {"te": 0.02, "tr": 0.1})
    operators = schedule(sequence, EngineOptions(dwell_time=0.001))
    backend = RecordingBackend()
    trace = run_backend(backend, operators, return_snapshots=True)
    assert trace.signal.tolist() == [1.0 + 0.0j, 1.0 + 0.0j]
    assert trace.k_trajectory.shape == (2, 3)
    assert trace.snapshots.shape[0] == len(operators)
```

- [ ] **Step 2: Run the file and verify scheduler imports fail**

Run: `python3.11 -m pytest tests/physics/test_scheduler_runner.py -q`

Expected: FAIL during import because `kernel.scheduler` and `kernel.runner` do not exist.

- [ ] **Step 3: Implement deterministic event merging and metadata-first shifts**

```python
# packages/physics/mrqlab_physics/kernel/scheduler.py
from bisect import bisect_right
import numpy as np
from mrqlab_sequence import SequenceIR
from ..models import EngineOptions
from ..ops.types import AdcSample, GradInterval, Operator, Relax, RfOp, Shift
from .units import deg_to_rad

def _value_at(events, t: float, default: float = 0.0) -> float:
    times = [event.time for event in events]
    index = bisect_right(times, t) - 1
    return default if index < 0 else float(events[index].value)

def _adc_sample_times(sequence: SequenceIR, dwell: float) -> tuple[float, ...]:
    starts: list[float] = []
    samples: list[float] = []
    active: float | None = None
    for event in sequence.channel("adc_gate"):
        if event.value and active is None:
            active = event.time
        elif not event.value and active is not None:
            count = max(0, int(np.ceil((event.time - active) / dwell - 1e-12)))
            samples.extend(active + index * dwell for index in range(count))
            starts.append(active)
            active = None
    if active is not None:
        raise ValueError("adc_gate must close before sequence end")
    return tuple(samples)

def _metadata_shifts(sequence: SequenceIR) -> dict[float, list[Shift]]:
    shifts: dict[float, list[Shift]] = {}
    for raw in sequence.metadata.get("epg_dk_events", []):
        t = float(raw["time"])
        values = tuple(int(value) for value in raw["dk"])
        if len(values) != 3 or not 0 <= t <= sequence.duration:
            raise ValueError("each epg_dk_event requires time in range and three integer dk values")
        shifts.setdefault(t, []).append(Shift(t=t, dk=values, source="metadata"))
    return shifts

def schedule(sequence: SequenceIR, options: EngineOptions) -> tuple[Operator, ...]:
    rf_amp = sequence.channel("rf_amp")
    rf_phase = sequence.channel("rf_phase")
    gradients = tuple(sequence.channel(name) for name in ("gx", "gy", "gz"))
    nco_frequency = sequence.channel("nco_freq")
    nco_phase = sequence.channel("nco_phase")
    adc_times = _adc_sample_times(sequence, options.dwell_time)
    explicit_shifts = _metadata_shifts(sequence)
    event_times = {
        0.0,
        sequence.duration,
        *adc_times,
        *explicit_shifts.keys(),
        *(event.time for channel in sequence.channels for event in channel.events),
    }
    knots = sorted(event_times)
    rf_at: dict[float, list[float]] = {}
    for event in rf_amp:
        rf_at.setdefault(event.time, []).append(float(event.value))
    adc_set = set(adc_times)
    operators: list[Operator] = []
    use_area_fallback = not explicit_shifts

    for index, t in enumerate(knots):
        for alpha_deg in rf_at.get(t, []):
            operators.append(RfOp(t, deg_to_rad(alpha_deg), deg_to_rad(_value_at(rf_phase, t))))
        operators.extend(explicit_shifts.get(t, ()))
        if t in adc_set:
            operators.append(AdcSample(t, _value_at(nco_frequency, t), deg_to_rad(_value_at(nco_phase, t))))
        if index == len(knots) - 1:
            continue
        next_t = knots[index + 1]
        dt = next_t - t
        gradient = tuple(_value_at(channel, t) for channel in gradients)
        operators.append(Relax(t, dt))
        operators.append(GradInterval(t, dt, gradient))
        if use_area_fallback:
            dk = tuple(int(np.rint(value * dt / options.epg_dk_scale)) for value in gradient)
            if dk != (0, 0, 0):
                operators.append(Shift(next_t, dk, "gradient_area"))
    return tuple(operators)
```

- [ ] **Step 4: Implement the backend protocol and shared execution loop**

```python
# packages/physics/mrqlab_physics/backends/protocol.py
from typing import Protocol
import numpy as np
from ..ops.types import AdcSample, Operator

class StateBackend(Protocol):
    def apply(self, op: Operator) -> None: ...
    def observe(self, op: AdcSample) -> complex: ...
    def snapshot(self) -> np.ndarray: ...
```

```python
# packages/physics/mrqlab_physics/kernel/runner.py
from dataclasses import dataclass
import numpy as np
from ..backends.protocol import StateBackend
from ..ops.types import AdcSample, GradInterval, Operator

@dataclass(slots=True)
class RuntimeTrace:
    signal: np.ndarray
    k_trajectory: np.ndarray
    snapshots: np.ndarray | None

def run_backend(
    backend: StateBackend,
    operators: tuple[Operator, ...],
    return_snapshots: bool,
) -> RuntimeTrace:
    signal: list[complex] = []
    trajectory: list[np.ndarray] = []
    snapshots: list[np.ndarray] = []
    k = np.zeros(3, dtype=float)
    for op in operators:
        backend.apply(op)
        if isinstance(op, GradInterval):
            k = k + np.asarray(op.gradient) * op.dt
        if isinstance(op, AdcSample):
            signal.append(backend.observe(op))
            trajectory.append(k.copy())
        if return_snapshots:
            snapshots.append(backend.snapshot())
    snapshot_array = np.stack(snapshots) if snapshots else None
    trajectory_array = np.asarray(trajectory, dtype=float).reshape((-1, 3))
    return RuntimeTrace(np.asarray(signal, dtype=np.complex128), trajectory_array, snapshot_array)
```

- [ ] **Step 5: Run scheduler, operator, and model tests**

Run: `python3.11 -m pytest tests/physics/test_scheduler_runner.py tests/physics/test_ops_golden.py tests/physics/test_models_caps.py -q`

Expected: PASS with 10 tests.

- [ ] **Step 6: Commit the microkernel scheduler and runner**

```bash
git add packages/physics/mrqlab_physics/kernel packages/physics/mrqlab_physics/backends/protocol.py tests/physics/test_scheduler_runner.py
git commit -m "feat(physics): schedule sequence IR operators"
```

### Task 5: Rewrite Bloch as a Multi-Isochromat Plugin

**Files:**
- Create: `packages/physics/mrqlab_physics/backends/bloch.py`
- Replace: `packages/physics/mrqlab_physics/engines/bloch_engine.py`
- Test: `tests/physics/test_bloch_engine.py`
- Modify: `tests/test_physics.py`

**Interfaces:**
- Consumes: `Phantom.resolved_isochromats`, scheduled operators, `run_backend`, and `enforce_work_limit`.
- Produces: Vectorized `BlochBackend` and a production `BlochEngine` returning combined complex signal, `(n_ops, n_isochromats, 3)` optional history, 3-D k-trajectory, work metadata, and timing.

- [ ] **Step 1: Write failing RF-axis, dephasing, and work-meta tests**

```python
# tests/physics/test_bloch_engine.py
import numpy as np
import pytest
from mrqlab_sequence import Channel, Event, SequenceIR, build_sequence
from mrqlab_physics import EngineOptions, Isochromat, Phantom, ScannerModel
from mrqlab_physics.engines import BlochEngine

def _channel(name, values):
    return Channel(name=name, events=[Event(time=t, value=v) for t, v in values])

def test_rf_phase_90_rotates_z_toward_positive_x():
    sequence = SequenceIR(name="phase", duration=0.01, channels=[
        _channel("rf_amp", [(0.0, 90.0)]),
        _channel("rf_phase", [(0.0, 90.0)]),
        _channel("adc_gate", [(0.0, 1.0), (0.001, 0.0)]),
    ])
    result = BlochEngine().simulate(sequence, Phantom(), ScannerModel(), EngineOptions())
    assert result.signal[0].real == pytest.approx(1.0, abs=1e-12)
    assert result.signal[0].imag == pytest.approx(0.0, abs=1e-12)

def test_symmetric_isochromats_dephase_at_quarter_period():
    sequence = SequenceIR(name="fan", duration=0.251, channels=[
        _channel("rf_amp", [(0.0, 90.0)]),
        _channel("rf_phase", [(0.0, 0.0)]),
        _channel("adc_gate", [(0.25, 1.0), (0.251, 0.0)]),
    ])
    phantom = Phantom(isochromats=(
        Isochromat(t1=100, t2=100, off_resonance_hz=-1, weight=0.5),
        Isochromat(t1=100, t2=100, off_resonance_hz=1, weight=0.5),
    ))
    result = BlochEngine().simulate(sequence, phantom, ScannerModel(), EngineOptions())
    assert abs(result.signal[0]) < 0.01
    assert result.meta["n_isochromats"] == 2
    assert result.meta["estimated_work"] > 0

def test_se_and_gre_remain_primary_bloch_templates():
    for name in ("SE", "GRE"):
        result = BlochEngine().simulate(
            build_sequence(name, {"te": 0.02, "tr": 0.1}),
            Phantom(), ScannerModel(), EngineOptions(),
        )
        assert result.signal.size == 2
```

- [ ] **Step 2: Run the focused file and verify missing multi-isochromat behavior fails**

Run: `python3.11 -m pytest tests/physics/test_bloch_engine.py -q`

Expected: FAIL because the moved MVP engine has no `Isochromat` vector state and ignores RF phase.

- [ ] **Step 3: Implement the complete vectorized Bloch backend**

```python
# packages/physics/mrqlab_physics/backends/bloch.py
import numpy as np
from ..models import Isochromat, ScannerModel
from ..ops.relax import relaxation_factors
from ..ops.rf import rotate_cartesian
from ..ops.sample import demodulate
from ..ops.types import AdcSample, GradInterval, Operator, Relax, RfOp, Shift

class BlochBackend:
    def __init__(self, spins: tuple[Isochromat, ...], scanner: ScannerModel):
        self.spins = spins
        self.scanner = scanner
        self.state = np.zeros((len(spins), 3), dtype=float)
        self.state[:, 2] = [spin.proton_density for spin in spins]
        self.weights = np.asarray([spin.weight for spin in spins], dtype=float)
        self.positions = np.asarray([spin.position_m for spin in spins], dtype=float)

    def apply(self, op: Operator) -> None:
        if isinstance(op, RfOp):
            self.state = rotate_cartesian(self.state, op.alpha_rad, op.phase_rad)
        elif isinstance(op, Relax):
            for index, spin in enumerate(self.spins):
                e1, e2 = relaxation_factors(op.dt, spin.t1, spin.t2)
                transverse = (self.state[index, 0] + 1j * self.state[index, 1])
                transverse *= e2 * np.exp(2j * np.pi * spin.off_resonance_hz * op.dt)
                self.state[index, 0:2] = (transverse.real, transverse.imag)
                self.state[index, 2] = spin.proton_density - (
                    spin.proton_density - self.state[index, 2]
                ) * e1
        elif isinstance(op, GradInterval):
            gradient_hz_per_m = np.asarray(op.gradient) * self.scanner.gradient_scale
            phase = 2.0 * np.pi * (self.positions @ gradient_hz_per_m) * op.dt
            transverse = (self.state[:, 0] + 1j * self.state[:, 1]) * np.exp(1j * phase)
            self.state[:, 0] = transverse.real
            self.state[:, 1] = transverse.imag
        elif isinstance(op, (Shift, AdcSample)):
            return

    def observe(self, op: AdcSample) -> complex:
        transverse = self.state[:, 0] + 1j * self.state[:, 1]
        total_weight = self.weights.sum()
        value = 0j if total_weight == 0 else np.sum(self.weights * transverse) / total_weight
        return demodulate(value, op.t, op.nco_frequency_hz, op.nco_phase_rad)

    def snapshot(self) -> np.ndarray:
        return self.state.copy()
```

- [ ] **Step 4: Replace Bloch orchestration with schedule/cap/run/result assembly**

```python
# packages/physics/mrqlab_physics/engines/bloch_engine.py
import time
from ..backends.bloch import BlochBackend
from ..base import SimulationEngine
from ..kernel.caps import enforce_work_limit
from ..kernel.runner import run_backend
from ..kernel.scheduler import schedule
from ..models import EngineOptions, Phantom, ScannerModel, SimResult

class BlochEngine(SimulationEngine):
    name = "bloch"
    description = "Vectorized multi-isochromat Bloch simulation"

    def simulate(self, sequence, phantom: Phantom, scanner: ScannerModel, options: EngineOptions) -> SimResult:
        started = time.perf_counter()
        operators = schedule(sequence, options)
        spins = phantom.resolved_isochromats()
        work = enforce_work_limit(self.name, len(operators), len(spins), options, 1)
        trace = run_backend(BlochBackend(spins, scanner), operators, options.return_magnetization)
        return SimResult(
            signal=trace.signal,
            k_trajectory=trace.k_trajectory * scanner.gradient_scale,
            magnetization=trace.snapshots,
            meta={
                "engine": self.name,
                "samples": int(trace.signal.size),
                "n_isochromats": len(spins),
                "n_ops": len(operators),
                "estimated_work": work,
                "assumptions": ["instantaneous RF", "dimensionless teaching gradients"],
            },
            timing={"simulation_seconds": time.perf_counter() - started},
        )
```

Replace the old stub expectation in `tests/test_physics.py` with `assert get_engine("bloch").available is True`; EPG receives its own production test in Task 6.

- [ ] **Step 5: Run Bloch, scheduler, golden, and legacy physics tests**

Run: `python3.11 -m pytest tests/physics/test_bloch_engine.py tests/physics/test_scheduler_runner.py tests/physics/test_ops_golden.py tests/test_physics.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the Bloch rewrite**

```bash
git add packages/physics/mrqlab_physics tests/physics/test_bloch_engine.py tests/test_physics.py
git commit -m "feat(physics): add multi-isochromat Bloch engine"
```

### Task 6: Implement a Real Classic EPG Engine for Echo Trains

**Files:**
- Create: `packages/physics/mrqlab_physics/backends/epg.py`
- Replace: `packages/physics/mrqlab_physics/engines/epg_engine.py`
- Test: `tests/physics/test_epg_engine.py`

**Interfaces:**
- Consumes: Weigel RF matrix, `Relax`, integer x-component `Shift.dk`, ADC/NCO contract, scheduler, runner, and `EngineOptions.epg_kmax`.
- Produces: `EPGBackend` with signed orders `[-kmax, +kmax]`, observable `F+_0`, optional configuration history, and an available `EPGEngine`.

- [ ] **Step 1: Write failing hand-constructed CPMG and pruning tests**

```python
# tests/physics/test_epg_engine.py
import numpy as np
import pytest
from mrqlab_sequence import Channel, Event, SequenceIR
from mrqlab_physics import EngineOptions, Phantom, ScannerModel
from mrqlab_physics.engines import EPGEngine

def _channel(name, values):
    return Channel(name=name, events=[Event(time=t, value=v) for t, v in values])

def _cpmg_sequence():
    return SequenceIR(
        name="CPMG",
        duration=0.021,
        channels=[
            _channel("rf_amp", [(0.0, 90.0), (0.01, 180.0)]),
            _channel("rf_phase", [(0.0, 0.0), (0.01, 90.0)]),
            _channel("adc_gate", [(0.02, 1.0), (0.021, 0.0)]),
        ],
        metadata={"epg_dk_events": [
            {"time": 0.005, "dk": [1, 0, 0]},
            {"time": 0.015, "dk": [1, 0, 0]},
        ]},
    )

def test_classic_epg_refocuses_shifted_configuration():
    result = EPGEngine().simulate(
        _cpmg_sequence(), Phantom(t1=1000, t2=1000), ScannerModel(),
        EngineOptions(epg_kmax=4, return_configurations=True),
    )
    assert abs(result.signal[0]) == pytest.approx(1.0, abs=1e-4)
    assert result.configurations.shape[1:] == (3, 9)
    assert result.meta["n_orders"] == 9

def test_epg_kmax_prunes_out_of_range_states_without_growth():
    sequence = _cpmg_sequence()
    sequence.metadata["epg_dk_events"] = [{"time": 0.005, "dk": [5, 0, 0]}]
    result = EPGEngine().simulate(sequence, Phantom(), ScannerModel(), EngineOptions(epg_kmax=1))
    assert result.signal.shape == (1,)
    assert result.meta["kmax"] == 1
    assert result.meta["available"] is True
```

- [ ] **Step 2: Run the EPG file and verify the transitional engine fails**

Run: `python3.11 -m pytest tests/physics/test_epg_engine.py -q`

Expected: FAIL with `NotImplementedError: epg engine requires the classic EPG backend`.

- [ ] **Step 3: Implement bounded signed-order configuration states**

```python
# packages/physics/mrqlab_physics/backends/epg.py
import numpy as np
from ..models import Phantom
from ..ops.relax import relaxation_factors
from ..ops.rf import epg_rf_matrix
from ..ops.sample import demodulate
from ..ops.types import AdcSample, GradInterval, Operator, Relax, RfOp, Shift

def _translate(values: np.ndarray, delta: int) -> np.ndarray:
    output = np.zeros_like(values)
    if abs(delta) >= values.size:
        return output
    if delta > 0:
        output[delta:] = values[:-delta]
    elif delta < 0:
        output[:delta] = values[-delta:]
    else:
        output[:] = values
    return output

class EPGBackend:
    def __init__(self, phantom: Phantom, kmax: int):
        self.phantom = phantom
        self.kmax = kmax
        self.zero = kmax
        self.omega = np.zeros((3, 2 * kmax + 1), dtype=np.complex128)
        self.omega[2, self.zero] = phantom.proton_density

    def apply(self, op: Operator) -> None:
        if isinstance(op, RfOp):
            self.omega = epg_rf_matrix(op.alpha_rad, op.phase_rad) @ self.omega
        elif isinstance(op, Relax):
            e1, e2 = relaxation_factors(op.dt, self.phantom.t1, self.phantom.t2)
            phase = np.exp(2j * np.pi * self.phantom.off_resonance_hz * op.dt)
            self.omega[0] *= e2 * phase
            self.omega[1] *= e2 * np.conj(phase)
            self.omega[2] *= e1
            self.omega[2, self.zero] += self.phantom.proton_density * (1.0 - e1)
        elif isinstance(op, Shift):
            dk = op.dk[0]
            self.omega[0] = _translate(self.omega[0], dk)
            self.omega[1] = _translate(self.omega[1], -dk)
        elif isinstance(op, (GradInterval, AdcSample)):
            return

    def observe(self, op: AdcSample) -> complex:
        return demodulate(self.omega[0, self.zero], op.t, op.nco_frequency_hz, op.nco_phase_rad)

    def snapshot(self) -> np.ndarray:
        return self.omega.copy()
```

- [ ] **Step 4: Replace the EPG engine with production orchestration**

```python
# packages/physics/mrqlab_physics/engines/epg_engine.py
import time
from ..backends.epg import EPGBackend
from ..base import SimulationEngine
from ..kernel.caps import enforce_work_limit
from ..kernel.runner import run_backend
from ..kernel.scheduler import schedule
from ..models import EngineOptions, Phantom, ScannerModel, SimResult

class EPGEngine(SimulationEngine):
    name = "epg"
    description = "Classic bounded-order extended phase graph"
    available = True

    def simulate(self, sequence, phantom: Phantom, scanner: ScannerModel, options: EngineOptions) -> SimResult:
        started = time.perf_counter()
        operators = schedule(sequence, options)
        work = enforce_work_limit(self.name, len(operators), 1, options, 1)
        trace = run_backend(EPGBackend(phantom, options.epg_kmax), operators, options.return_configurations)
        return SimResult(
            signal=trace.signal,
            k_trajectory=trace.k_trajectory * scanner.gradient_scale,
            configurations=trace.snapshots,
            meta={
                "engine": self.name,
                "available": True,
                "samples": int(trace.signal.size),
                "n_ops": len(operators),
                "estimated_work": work,
                "kmax": options.epg_kmax,
                "n_orders": 2 * options.epg_kmax + 1,
                "assumptions": ["classic single-pool EPG", "metadata-first integer dk"],
            },
            timing={"simulation_seconds": time.perf_counter() - started},
        )
```

- [ ] **Step 5: Run EPG plus the shared kernel suite**

Run: `python3.11 -m pytest tests/physics/test_epg_engine.py tests/physics/test_scheduler_runner.py tests/physics/test_ops_golden.py -q`

Expected: PASS.

- [ ] **Step 6: Commit classic EPG**

```bash
git add packages/physics/mrqlab_physics/backends/epg.py packages/physics/mrqlab_physics/engines/epg_engine.py tests/physics/test_epg_engine.py
git commit -m "feat(physics): add classic EPG echo engine"
```

### Task 7: Emit Explicit TSE Shifts and Select Engines Through the API

**Files:**
- Modify: `packages/sequence-ir/mrqlab_sequence/templates.py`
- Modify: `services/api/mrqlab_api/main.py`
- Modify: `tests/test_api.py`
- Create: `tests/physics/test_template_metadata.py`

**Interfaces:**
- Consumes: Template `SequenceIR.metadata`, `get_engine(name)`, and the server-owned `SIM_MAX_MATRIX` and new `SIM_MAX_WORK` limits.
- Produces: `preferred_engine` metadata (`SE/GRE → bloch`, `TSE → epg`), explicit TSE `epg_dk_events`, `SimulateRequest.engine: str | None`, and HTTP 422 errors for unknown engines or excessive estimated work.

- [ ] **Step 1: Write failing template and API-selection tests**

```python
# tests/physics/test_template_metadata.py
from mrqlab_sequence import build_sequence

def test_templates_declare_backend_without_embedding_backend_code():
    assert build_sequence("SE").metadata["preferred_engine"] == "bloch"
    assert build_sequence("GRE").metadata["preferred_engine"] == "bloch"
    tse = build_sequence("TSE", {"te": 0.02, "tr": 0.1, "echoes": 2})
    assert tse.metadata["preferred_engine"] == "epg"
    assert tse.metadata["epg_dk_events"] == [
        {"time": 0.005, "dk": [1, 0, 0]},
        {"time": 0.015, "dk": [1, 0, 0]},
        {"time": 0.025, "dk": [1, 0, 0]},
        {"time": 0.035, "dk": [1, 0, 0]},
    ]
    assert [event.value for event in tse.channel("rf_phase")] == [0.0, 90.0, 90.0]
```

Append these tests to `tests/test_api.py`:

```python
def test_tse_uses_preferred_epg_engine_when_request_omits_engine():
    response = client.post("/simulate", json={
        "template": {"template": "TSE", "params": {"te": 0.02, "tr": 0.1, "echoes": 2}},
        "options": {"epg_kmax": 8},
    })
    assert response.status_code == 200
    assert response.json()["meta"]["engine"] == "epg"
    assert len(response.json()["signal"]) == 4

def test_explicit_engine_overrides_template_preference():
    response = client.post("/simulate", json={
        "template": {"template": "TSE", "params": {"te": 0.02, "tr": 0.1}},
        "engine": "bloch",
    })
    assert response.status_code == 200
    assert response.json()["meta"]["engine"] == "bloch"

def test_unknown_engine_is_a_validation_error():
    response = client.post("/simulate", json={
        "template": {"template": "GRE"},
        "engine": "missing",
    })
    assert response.status_code == 422
    assert "unknown engine" in response.json()["detail"]

def test_server_work_cap_cannot_be_raised_by_request(monkeypatch):
    monkeypatch.setattr("mrqlab_api.main.MAX_WORK", 1)
    response = client.post("/simulate", json={
        "template": {"template": "GRE"},
        "options": {"max_work": 999999},
    })
    assert response.status_code == 422
    assert "estimated work" in response.json()["detail"]
```

- [ ] **Step 2: Run metadata and API tests and verify selection fails**

Run in a clean Python >=3.11 editable environment: `python -m pytest tests/physics/test_template_metadata.py tests/test_api.py -q`

Expected: FAIL because templates lack engine/shift metadata, request engine defaults to Bloch, and the API still checks duration through `SIM_MAX_RUNTIME`.

- [ ] **Step 3: Add preferred engine, CPMG RF phases, and exact shift times**

Replace the final construction section of `build_sequence` with:

```python
    rf_phases = [0.0] + ([90.0] * (len(rf) - 1) if kind in {"SE", "TSE"} else [0.0] * (len(rf) - 1))
    metadata = {"template": kind, "te": te, "tr": tr, "echoes": echoes,
                "preferred_engine": "epg" if kind == "TSE" else "bloch"}
    if kind == "TSE":
        metadata["epg_dk_events"] = [
            {"time": center - 0.75 * te, "dk": [1, 0, 0]}
            for n in range(echoes)
            for center in (te * (n + 1),)
        ] + [
            {"time": center - 0.25 * te, "dk": [1, 0, 0]}
            for n in range(echoes)
            for center in (te * (n + 1),)
        ]
        metadata["epg_dk_events"].sort(key=lambda event: event["time"])
    return SequenceIR(name=kind, duration=tr, channels=[
        _ch("rf_amp", rf), _ch("rf_phase", list(zip((t for t, _ in rf), rf_phases))),
        _ch("gx", gx), _ch("gy", []), _ch("gz", [(0, 1), (.001, 0)]),
        _ch("adc_gate", adc), _ch("nco_freq", [(0, 0)]), _ch("nco_phase", [(0, 0)]),
    ], metadata=metadata)
```

- [ ] **Step 4: Replace duration-as-runtime policy with an engine-aware server work cap**

Use these exact API declarations and route body changes:

```python
# services/api/mrqlab_api/main.py additions/replacements
from dataclasses import replace

MAX_MATRIX = int(os.getenv("SIM_MAX_MATRIX", "64"))
MAX_WORK = int(os.getenv("SIM_MAX_WORK", "2000000"))

class SimulateRequest(BaseModel):
    sequence: SequenceIR | None = None
    template: TemplateRequest | None = None
    engine: str | None = None
    phantom: dict[str, Any] = Field(default_factory=dict)
    scanner: dict[str, float] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    matrix: int = Field(default=32, ge=1)

    @model_validator(mode="after")
    def one_source(self):
        if (self.sequence is None) == (self.template is None):
            raise ValueError("provide exactly one of sequence or template")
        return self

@app.post("/simulate")
def simulate(request: SimulateRequest):
    if request.matrix > MAX_MATRIX:
        raise HTTPException(422, f"matrix exceeds SIM_MAX_MATRIX ({MAX_MATRIX})")
    try:
        sequence = request.sequence or build_sequence(request.template.template, request.template.params)
        requested_options = EngineOptions(**request.options)
        options = replace(requested_options, max_work=min(requested_options.max_work, MAX_WORK))
        engine_name = request.engine or str(sequence.metadata.get("preferred_engine", "bloch"))
        result = get_engine(engine_name).simulate(
            sequence, Phantom(**request.phantom), ScannerModel(**request.scanner), options,
        )
    except (ValueError, TypeError, NotImplementedError) as exc:
        raise HTTPException(422, str(exc)) from exc
    recon = fft_reconstruct(result.signal) if result.signal.size else np.array([])
    return {
        "signal": [{"real": float(value.real), "imag": float(value.imag)} for value in result.signal],
        "k_trajectory": result.k_trajectory.tolist(),
        "reconstruction_magnitude": np.abs(recon).tolist(),
        "meta": result.meta,
        "timing": result.timing,
    }
```

Delete `MAX_RUNTIME` and its duration/dwell check. Keep `matrix` as the bounded reconstruction/UI request dimension; physics work is independently bounded by `max_work`.

- [ ] **Step 5: Run template, API, EPG, and Bloch tests**

Run: `python -m pytest tests/physics/test_template_metadata.py tests/test_api.py tests/physics/test_epg_engine.py tests/physics/test_bloch_engine.py -q`

Expected: PASS in the clean editable environment.

- [ ] **Step 6: Commit metadata-driven engine selection**

```bash
git add packages/sequence-ir/mrqlab_sequence/templates.py services/api/mrqlab_api/main.py tests/test_api.py tests/physics/test_template_metadata.py
git commit -m "feat(api): select physics engine from sequence metadata"
```

### Task 8: Implement Spectral v0 as Independent Fat/Water Pools

**Files:**
- Create: `packages/physics/mrqlab_physics/backends/spectral.py`
- Replace: `packages/physics/mrqlab_physics/engines/spectral_engine.py`
- Modify: `services/api/mrqlab_api/main.py`
- Test: `tests/physics/test_spectral_engine.py`

**Interfaces:**
- Consumes: `Phantom.pools`, base isochromats, `ScannerModel.b0_t`, proton gyromagnetic ratio `42_577_478.518 Hz/T`, Bloch operator semantics, scheduler, runner, and work caps.
- Produces: Independent non-exchanging chemical-shift pools and an available `SpectralEngine`; no CEST saturation, exchange, MT, or MRS lineshape fitting.

- [ ] **Step 1: Write a failing equal-fat/water cancellation test**

```python
# tests/physics/test_spectral_engine.py
import pytest
from mrqlab_sequence import Channel, Event, SequenceIR
from mrqlab_physics import EngineOptions, Phantom, ScannerModel, SpectralPool
from mrqlab_physics.engines import SpectralEngine

GAMMA_HZ_PER_T = 42_577_478.518

def _channel(name, values):
    return Channel(name=name, events=[Event(time=t, value=v) for t, v in values])

def test_equal_fat_water_pools_cancel_at_half_beat():
    scanner = ScannerModel(b0_t=1.5)
    delta_hz = 3.5e-6 * GAMMA_HZ_PER_T * scanner.b0_t
    sample_time = 0.5 / delta_hz
    sequence = SequenceIR(name="fat-water", duration=sample_time + 1e-5, channels=[
        _channel("rf_amp", [(0.0, 90.0)]),
        _channel("rf_phase", [(0.0, 0.0)]),
        _channel("adc_gate", [(sample_time, 1.0), (sample_time + 1e-5, 0.0)]),
    ])
    phantom = Phantom(pools=(
        SpectralPool("water", 0.5, 0.0, 100.0, 100.0),
        SpectralPool("fat", 0.5, -3.5, 100.0, 100.0),
    ))
    result = SpectralEngine().simulate(sequence, phantom, scanner, EngineOptions(dwell_time=1e-5))
    assert abs(result.signal[0]) < 1e-4
    assert result.meta["pools"] == ["water", "fat"]
    assert result.meta["model"] == "independent chemical-shift pools"

def test_spectral_requires_at_least_one_pool():
    with pytest.raises(ValueError, match="at least one spectral pool"):
        SpectralEngine().simulate(
            SequenceIR(name="empty", duration=0.01, channels=[]),
            Phantom(), ScannerModel(), EngineOptions(),
        )
```

- [ ] **Step 2: Run the spectral file and verify the transitional engine fails**

Run: `python3.11 -m pytest tests/physics/test_spectral_engine.py -q`

Expected: FAIL with `NotImplementedError: spectral engine requires spectral pools`.

- [ ] **Step 3: Expand pools into Bloch-compatible isochromats**

```python
# packages/physics/mrqlab_physics/backends/spectral.py
from ..models import Isochromat, Phantom, ScannerModel
from .bloch import BlochBackend

GAMMA_HZ_PER_T = 42_577_478.518

def spectral_isochromats(phantom: Phantom, scanner: ScannerModel) -> tuple[Isochromat, ...]:
    if not phantom.pools:
        raise ValueError("spectral engine requires at least one spectral pool")
    if sum(pool.fraction for pool in phantom.pools) <= 0:
        raise ValueError("spectral pool fractions must sum to a positive value")
    expanded: list[Isochromat] = []
    for base in phantom.resolved_isochromats():
        for pool in phantom.pools:
            expanded.append(Isochromat(
                t1=pool.t1,
                t2=pool.t2,
                proton_density=base.proton_density,
                off_resonance_hz=(
                    base.off_resonance_hz
                    + pool.chemical_shift_ppm * 1e-6 * GAMMA_HZ_PER_T * scanner.b0_t
                ),
                position_m=base.position_m,
                weight=base.weight * pool.fraction,
            ))
    return tuple(expanded)

class SpectralBackend(BlochBackend):
    def __init__(self, phantom: Phantom, scanner: ScannerModel):
        super().__init__(spectral_isochromats(phantom, scanner), scanner)
```

- [ ] **Step 4: Add spectral engine orchestration**

```python
# packages/physics/mrqlab_physics/engines/spectral_engine.py
import time
from ..backends.spectral import SpectralBackend
from ..base import SimulationEngine
from ..kernel.caps import enforce_work_limit
from ..kernel.runner import run_backend
from ..kernel.scheduler import schedule
from ..models import EngineOptions, Phantom, ScannerModel, SimResult

class SpectralEngine(SimulationEngine):
    name = "spectral"
    description = "Independent fat/water chemical-shift pools"
    available = True

    def simulate(self, sequence, phantom: Phantom, scanner: ScannerModel, options: EngineOptions) -> SimResult:
        started = time.perf_counter()
        operators = schedule(sequence, options)
        base_spins = phantom.resolved_isochromats()
        work = enforce_work_limit(self.name, len(operators), len(base_spins), options, len(phantom.pools))
        trace = run_backend(SpectralBackend(phantom, scanner), operators, options.return_magnetization)
        return SimResult(
            signal=trace.signal,
            k_trajectory=trace.k_trajectory * scanner.gradient_scale,
            magnetization=trace.snapshots,
            meta={
                "engine": self.name,
                "available": True,
                "model": "independent chemical-shift pools",
                "pools": [pool.name for pool in phantom.pools],
                "n_isochromats": len(base_spins) * len(phantom.pools),
                "n_ops": len(operators),
                "estimated_work": work,
                "assumptions": ["no exchange", "instantaneous RF", "Lorentzian relaxation only"],
            },
            timing={"simulation_seconds": time.perf_counter() - started},
        )
```

- [ ] **Step 5: Parse nested pool/isochromat payloads at the API boundary**

Add the public model imports and use this helper:

```python
from mrqlab_physics import (
    EngineOptions, Isochromat, Phantom, ScannerModel, SpectralPool,
    get_engine, list_engines,
)

def _phantom_from_payload(payload: dict[str, Any]) -> Phantom:
    values = dict(payload)
    values["isochromats"] = tuple(Isochromat(**item) for item in values.get("isochromats", ()))
    values["pools"] = tuple(SpectralPool(**item) for item in values.get("pools", ()))
    return Phantom(**values)
```

In `/simulate`, replace `Phantom(**request.phantom)` with `_phantom_from_payload(request.phantom)`.

- [ ] **Step 6: Run all three engine suites and API tests**

Run: `python -m pytest tests/physics/test_bloch_engine.py tests/physics/test_epg_engine.py tests/physics/test_spectral_engine.py tests/test_api.py -q`

Expected: PASS in the clean editable environment.

- [ ] **Step 7: Commit spectral v0**

```bash
git add packages/physics/mrqlab_physics services/api/mrqlab_api/main.py tests/physics/test_spectral_engine.py
git commit -m "feat(physics): add fat-water spectral engine"
```

### Task 9: Discover External Engines Through Entry Points

**Files:**
- Replace: `packages/physics/mrqlab_physics/registry.py`
- Modify: `packages/physics/mrqlab_physics/__init__.py`
- Test: `tests/physics/test_registry_plugins.py`
- Modify: `tests/test_physics.py`

**Interfaces:**
- Consumes: Built-in engine classes and `importlib.metadata.entry_points(group="mrqlab.physics_engines")`.
- Produces: `get_engine`, `list_engines`, and `refresh_engines`; entry points may load a `SimulationEngine` instance or subclass and may not silently shadow a built-in name.

- [ ] **Step 1: Write failing discovery, duplicate-name, and descriptor tests**

```python
# tests/physics/test_registry_plugins.py
import pytest
from mrqlab_physics.base import SimulationEngine
from mrqlab_physics.registry import get_engine, list_engines, refresh_engines

class DemoEngine(SimulationEngine):
    name = "demo"
    description = "test plugin"
    def simulate(self, sequence, phantom, scanner, options):
        raise AssertionError("plugin smoke test does not execute simulation")

class FakeEntryPoint:
    name = "demo"
    value = "tests.fake:DemoEngine"
    def load(self):
        return DemoEngine

@pytest.fixture(autouse=True)
def restore_builtin_registry(monkeypatch):
    yield
    monkeypatch.undo()
    refresh_engines()

def test_entry_point_class_is_instantiated(monkeypatch):
    monkeypatch.setattr("mrqlab_physics.registry.entry_points", lambda group: [FakeEntryPoint()])
    refresh_engines()
    assert isinstance(get_engine("DEMO"), DemoEngine)
    descriptor = next(item for item in list_engines() if item["name"] == "demo")
    assert descriptor == {"name": "demo", "available": True, "description": "test plugin", "source": "entry-point"}

def test_plugin_cannot_shadow_builtin(monkeypatch):
    FakeEntryPoint.name = "bloch"
    monkeypatch.setattr("mrqlab_physics.registry.entry_points", lambda group: [FakeEntryPoint()])
    with pytest.raises(ValueError, match="duplicate physics engine 'bloch'"):
        refresh_engines()
    FakeEntryPoint.name = "demo"
```

- [ ] **Step 2: Run the registry file and verify `refresh_engines` is missing**

Run: `python3.11 -m pytest tests/physics/test_registry_plugins.py -q`

Expected: FAIL during import because `refresh_engines` does not exist.

- [ ] **Step 3: Replace the static instance map with validated factories and entry points**

```python
# packages/physics/mrqlab_physics/registry.py
from importlib.metadata import entry_points
from .base import SimulationEngine
from .engines import BlochEngine, EPGEngine, SpectralEngine

_BUILTIN_TYPES = (BlochEngine, EPGEngine, SpectralEngine)
_engines: dict[str, tuple[SimulationEngine, str]] | None = None

def _coerce_engine(candidate, entry_name: str) -> SimulationEngine:
    engine = candidate() if isinstance(candidate, type) else candidate
    if not isinstance(engine, SimulationEngine):
        raise TypeError(f"physics entry point {entry_name!r} did not load a SimulationEngine")
    if engine.name.lower() != entry_name.lower():
        raise ValueError(f"physics entry point {entry_name!r} loaded engine named {engine.name!r}")
    return engine

def _load_engines() -> dict[str, tuple[SimulationEngine, str]]:
    loaded = {engine.name: (engine, "built-in") for engine in (kind() for kind in _BUILTIN_TYPES)}
    for entry_point in entry_points(group="mrqlab.physics_engines"):
        name = entry_point.name.lower()
        if name in loaded:
            raise ValueError(f"duplicate physics engine {name!r}")
        loaded[name] = (_coerce_engine(entry_point.load(), entry_point.name), "entry-point")
    return loaded

def refresh_engines() -> None:
    global _engines
    _engines = _load_engines()

def _registry() -> dict[str, tuple[SimulationEngine, str]]:
    global _engines
    if _engines is None:
        refresh_engines()
    return _engines

def get_engine(name: str = "bloch") -> SimulationEngine:
    registry = _registry()
    try:
        return registry[name.lower()][0]
    except KeyError:
        choices = ", ".join(sorted(registry))
        raise ValueError(f"unknown engine {name!r}; choose from {choices}") from None

def list_engines() -> list[dict[str, str | bool]]:
    return [
        {"name": name, "available": engine.available,
         "description": engine.description, "source": source}
        for name, (engine, source) in sorted(_registry().items())
    ]
```

Export `refresh_engines` from `mrqlab_physics.__init__`. Update `tests/test_physics.py` to assert all three built-in descriptors have `available is True` and `source == "built-in"`.

- [ ] **Step 4: Run registry and engine regressions**

Run: `python3.11 -m pytest tests/physics/test_registry_plugins.py tests/test_physics.py tests/physics/test_bloch_engine.py tests/physics/test_epg_engine.py tests/physics/test_spectral_engine.py -q`

Expected: PASS.

- [ ] **Step 5: Commit plugin discovery**

```bash
git add packages/physics/mrqlab_physics tests/physics/test_registry_plugins.py tests/test_physics.py
git commit -m "feat(physics): discover engine entry points"
```

### Task 10: Add EPG-X Diffusion and BM/MT Extension Contracts

**Files:**
- Create: `packages/physics/mrqlab_physics/ops/diffuse.py`
- Create: `packages/physics/mrqlab_physics/backends/epg_x.py`
- Test: `tests/physics/test_epg_x_seams.py`

**Interfaces:**
- Consumes: Configuration order, configuration spacing in cycles/m, diffusion coefficient in m²/s, seconds, and bounded `kmax`.
- Produces: `diffusion_attenuation`, `EpgXLayout`, `epg_x_zeros`, and explicit `EpgXFeatureUnavailable` failures for Bloch–McConnell and MT evolution.

- [ ] **Step 1: Write failing tests for diffusion monotonicity and exact state layouts**

```python
# tests/physics/test_epg_x_seams.py
import numpy as np
import pytest
from mrqlab_physics.backends.epg_x import (
    EpgXFeatureUnavailable, EpgXLayout, apply_bloch_mcconnell,
    apply_magnetization_transfer, epg_x_zeros,
)
from mrqlab_physics.ops.diffuse import diffusion_attenuation

def test_configuration_diffusion_attenuation_is_bounded_and_monotone():
    weights = [diffusion_attenuation(order, 100.0, 0.8e-9, 0.01) for order in range(4)]
    assert weights[0] == 1.0
    assert all(0.0 < value <= 1.0 for value in weights)
    assert weights == sorted(weights, reverse=True)

def test_bm_and_mt_layout_shapes_are_stable():
    assert epg_x_zeros(EpgXLayout.BLOCH_MCCONNELL, kmax=2).shape == (6, 5)
    assert epg_x_zeros(EpgXLayout.MAGNETIZATION_TRANSFER, kmax=2).shape == (4, 5)

def test_unimplemented_biology_fails_at_named_seam():
    state = np.zeros((6, 5), dtype=np.complex128)
    with pytest.raises(EpgXFeatureUnavailable, match="Bloch-McConnell exchange is outside physics v1"):
        apply_bloch_mcconnell(state, dt=0.01)
    with pytest.raises(EpgXFeatureUnavailable, match="magnetization transfer is outside physics v1"):
        apply_magnetization_transfer(np.zeros((4, 5)), dt=0.01)
```

- [ ] **Step 2: Run the seam tests and verify modules are absent**

Run: `python3.11 -m pytest tests/physics/test_epg_x_seams.py -q`

Expected: FAIL during import because the diffusion and EPG-X modules do not exist.

- [ ] **Step 3: Implement the configuration-space diffusion propagator**

```python
# packages/physics/mrqlab_physics/ops/diffuse.py
import numpy as np

def diffusion_attenuation(
    order: int,
    dk_cycles_per_m: float,
    diffusion_m2_s: float,
    dt: float,
) -> float:
    if diffusion_m2_s < 0 or dt < 0 or dk_cycles_per_m < 0:
        raise ValueError("diffusion coefficient, dt, and dk spacing must be non-negative")
    wave_number_rad_per_m = 2.0 * np.pi * abs(order) * dk_cycles_per_m
    return float(np.exp(-diffusion_m2_s * wave_number_rad_per_m**2 * dt))
```

This is the diagonal free-diffusion propagator in configuration space. It is not wired into `EPGEngine` until a future spec defines physical gradient units and diffusion timing; landing it now makes that boundary executable without silently applying a teaching-unit gradient as T/m.

- [ ] **Step 4: Implement exact BM/MT state layout and failure contracts**

```python
# packages/physics/mrqlab_physics/backends/epg_x.py
from enum import Enum
import numpy as np

class EpgXFeatureUnavailable(NotImplementedError):
    pass

class EpgXLayout(str, Enum):
    BLOCH_MCCONNELL = "bloch-mcconnell"
    MAGNETIZATION_TRANSFER = "magnetization-transfer"

STATE_FIELDS = {
    EpgXLayout.BLOCH_MCCONNELL: ("F+a", "F-a", "Za", "F+b", "F-b", "Zb"),
    EpgXLayout.MAGNETIZATION_TRANSFER: ("F+a", "F-a", "Za", "Zb"),
}

def epg_x_zeros(layout: EpgXLayout, kmax: int) -> np.ndarray:
    if kmax < 0:
        raise ValueError("kmax must be non-negative")
    return np.zeros((len(STATE_FIELDS[layout]), 2 * kmax + 1), dtype=np.complex128)

def apply_bloch_mcconnell(state: np.ndarray, dt: float) -> None:
    if state.ndim != 2 or state.shape[0] != 6 or dt < 0:
        raise ValueError("Bloch-McConnell state must have shape (6, orders) and non-negative dt")
    raise EpgXFeatureUnavailable("Bloch-McConnell exchange is outside physics v1")

def apply_magnetization_transfer(state: np.ndarray, dt: float) -> None:
    if state.ndim != 2 or state.shape[0] != 4 or dt < 0:
        raise ValueError("magnetization-transfer state must have shape (4, orders) and non-negative dt")
    raise EpgXFeatureUnavailable("magnetization transfer is outside physics v1")
```

- [ ] **Step 5: Run seam, EPG, and operator tests**

Run: `python3.11 -m pytest tests/physics/test_epg_x_seams.py tests/physics/test_epg_engine.py tests/physics/test_ops_golden.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the EPG-X hooks**

```bash
git add packages/physics/mrqlab_physics/ops/diffuse.py packages/physics/mrqlab_physics/backends/epg_x.py tests/physics/test_epg_x_seams.py
git commit -m "feat(physics): define EPG-X extension seams"
```

### Task 11: Add a PDG Provider Adapter Without a Heavy Default Dependency

**Files:**
- Create: `packages/physics/mrqlab_physics/backends/pdg.py`
- Test: `tests/physics/test_pdg_adapter.py`

**Interfaces:**
- Consumes: The unified four-argument simulation call and a caller-supplied `PDGProvider`.
- Produces: `PDGAdapter` that delegates when a provider is present and raises `PDGProviderUnavailable` otherwise; it is deliberately absent from built-in registry descriptors.

- [ ] **Step 1: Write failing unavailable/delegation/registry tests**

```python
# tests/physics/test_pdg_adapter.py
import numpy as np
import pytest
from mrqlab_physics import EngineOptions, Phantom, ScannerModel, SimResult, list_engines
from mrqlab_physics.backends.pdg import PDGAdapter, PDGProviderUnavailable

class FakeProvider:
    def simulate(self, sequence, phantom, scanner, options):
        return SimResult(
            signal=np.array([1 + 0j]),
            k_trajectory=np.zeros((1, 3)),
            meta={"provider": "fake"},
        )

def test_pdg_adapter_has_explicit_unavailable_path():
    with pytest.raises(PDGProviderUnavailable, match="install and pass a PDGProvider"):
        PDGAdapter().simulate(None, Phantom(), ScannerModel(), EngineOptions())

def test_pdg_adapter_delegates_unified_contract():
    result = PDGAdapter(FakeProvider()).simulate(None, Phantom(), ScannerModel(), EngineOptions())
    assert result.signal.tolist() == [1 + 0j]
    assert result.meta == {"provider": "fake", "engine": "pdg"}

def test_pdg_is_not_a_default_builtin_engine():
    assert "pdg" not in {item["name"] for item in list_engines()}
```

- [ ] **Step 2: Run the adapter tests and verify the module is absent**

Run: `python3.11 -m pytest tests/physics/test_pdg_adapter.py -q`

Expected: FAIL during import because `backends.pdg` does not exist.

- [ ] **Step 3: Implement the provider protocol and adapter**

```python
# packages/physics/mrqlab_physics/backends/pdg.py
from typing import Protocol
from mrqlab_sequence import SequenceIR
from ..base import SimulationEngine
from ..models import EngineOptions, Phantom, ScannerModel, SimResult

class PDGProvider(Protocol):
    def simulate(
        self,
        sequence: SequenceIR,
        phantom: Phantom,
        scanner: ScannerModel,
        options: EngineOptions,
    ) -> SimResult: ...

class PDGProviderUnavailable(RuntimeError):
    pass

class PDGAdapter(SimulationEngine):
    name = "pdg"
    description = "External phase-distribution-graph provider adapter"

    def __init__(self, provider: PDGProvider | None = None):
        self.provider = provider
        self.available = provider is not None

    def simulate(self, sequence, phantom, scanner, options) -> SimResult:
        if self.provider is None:
            raise PDGProviderUnavailable(
                "PDG is optional; install and pass a PDGProvider implementation"
            )
        result = self.provider.simulate(sequence, phantom, scanner, options)
        result.meta = {**result.meta, "engine": self.name}
        return result
```

An MRzero/pulseq-zero integration later implements `PDGProvider` in an optional distribution and exposes `PDGAdapter(provider)` through the `mrqlab.physics_engines` entry-point group. The default MRQLab package does not import or probe either heavy library.

- [ ] **Step 4: Run adapter and registry tests**

Run: `python3.11 -m pytest tests/physics/test_pdg_adapter.py tests/physics/test_registry_plugins.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the optional PDG seam**

```bash
git add packages/physics/mrqlab_physics/backends/pdg.py tests/physics/test_pdg_adapter.py
git commit -m "feat(physics): add optional PDG provider seam"
```

### Task 12: Lock Cross-Engine Signal and Relaxation Consistency

**Files:**
- Create: `packages/physics/mrqlab_physics/kernel/conventions.py`
- Modify: `packages/physics/mrqlab_physics/engines/bloch_engine.py`
- Modify: `packages/physics/mrqlab_physics/engines/epg_engine.py`
- Modify: `packages/physics/mrqlab_physics/engines/spectral_engine.py`
- Create: `tests/physics/test_cross_engine.py`

**Interfaces:**
- Consumes: All three production engines and an overlap sequence with no gradient/shift ambiguity.
- Produces: One documented `SIGNAL_CONVENTION`, shared metadata key, and numerical gates for RF phase, ADC time, and T2 decay.

- [ ] **Step 1: Write failing cross-engine convention tests**

```python
# tests/physics/test_cross_engine.py
import numpy as np
import pytest
from mrqlab_sequence import Channel, Event, SequenceIR
from mrqlab_physics import EngineOptions, Phantom, ScannerModel, SpectralPool
from mrqlab_physics.engines import BlochEngine, EPGEngine, SpectralEngine
from mrqlab_physics.kernel.conventions import SIGNAL_CONVENTION

def _channel(name, values):
    return Channel(name=name, events=[Event(time=t, value=v) for t, v in values])

def _fid(sample_time=0.02):
    return SequenceIR(name="overlap-fid", duration=sample_time + 0.001, channels=[
        _channel("rf_amp", [(0.0, 90.0)]),
        _channel("rf_phase", [(0.0, 0.0)]),
        _channel("adc_gate", [(sample_time, 1.0), (sample_time + 0.001, 0.0)]),
    ], metadata={"epg_dk_events": []})

def test_bloch_epg_and_one_pool_spectral_agree_on_fid():
    sequence = _fid()
    options = EngineOptions(dwell_time=0.001, epg_kmax=2)
    phantom = Phantom(t1=1.0, t2=0.08, proton_density=0.7, off_resonance_hz=3.0)
    spectral = Phantom(
        t1=phantom.t1, t2=phantom.t2, proton_density=phantom.proton_density,
        off_resonance_hz=phantom.off_resonance_hz,
        pools=(SpectralPool("water", 1.0, 0.0, phantom.t1, phantom.t2),),
    )
    results = [
        BlochEngine().simulate(sequence, phantom, ScannerModel(), options),
        EPGEngine().simulate(sequence, phantom, ScannerModel(), options),
        SpectralEngine().simulate(sequence, spectral, ScannerModel(), options),
    ]
    np.testing.assert_allclose([result.signal[0] for result in results], results[0].signal[0], atol=1e-10)
    assert {result.meta["signal_convention"] for result in results} == {SIGNAL_CONVENTION}

def test_cross_engine_t2_decay_matches_analytic_value():
    sequence = _fid(sample_time=0.08)
    phantom = Phantom(t1=100, t2=0.08)
    options = EngineOptions(epg_kmax=1)
    bloch = BlochEngine().simulate(sequence, phantom, ScannerModel(), options)
    epg = EPGEngine().simulate(sequence, phantom, ScannerModel(), options)
    assert abs(bloch.signal[0]) == pytest.approx(np.exp(-1), rel=1e-6)
    assert abs(epg.signal[0]) == pytest.approx(np.exp(-1), rel=1e-6)
```

- [ ] **Step 2: Run the consistency file and verify the convention module is missing**

Run: `python3.11 -m pytest tests/physics/test_cross_engine.py -q`

Expected: FAIL during import because `kernel.conventions` does not exist.

- [ ] **Step 3: Define and emit one signal convention from every built-in engine**

```python
# packages/physics/mrqlab_physics/kernel/conventions.py
SIGNAL_CONVENTION = "Mx + 1j*My; positive off-resonance accumulates positive phase; NCO demodulates negative phase"
```

In each built-in engine module, import `SIGNAL_CONVENTION` and add this exact item to the `meta` dictionary:

```python
"signal_convention": SIGNAL_CONVENTION,
```

If the numerical assertion exposes a sign mismatch, correct the backend that violates the convention. The expected formulas are exact: Bloch off-resonance multiplies by `exp(+i 2π df dt)`, EPG `F+` does the same, and shared NCO demodulation multiplies by `exp(-i (2π f t + phase))`.

- [ ] **Step 4: Run consistency, all engine, scheduler, and golden tests**

Run: `python3.11 -m pytest tests/physics/test_cross_engine.py tests/physics/test_bloch_engine.py tests/physics/test_epg_engine.py tests/physics/test_spectral_engine.py tests/physics/test_scheduler_runner.py tests/physics/test_ops_golden.py -q`

Expected: PASS.

- [ ] **Step 5: Commit cross-engine gates**

```bash
git add packages/physics/mrqlab_physics/kernel/conventions.py packages/physics/mrqlab_physics/engines tests/physics/test_cross_engine.py
git commit -m "test(physics): lock cross-engine signal conventions"
```

### Task 13: Publish Physics Documentation and Run the Full Acceptance Gate

**Files:**
- Create: `docs/PHYSICS.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/ROADMAP.md`
- Modify: `README.md`
- Create: `tests/physics/test_physics_docs.py`

**Interfaces:**
- Consumes: The implemented module map, metadata conventions, entry-point group, and locked paper/repository reference index.
- Produces: User-facing engine boundaries, equations, citations, plugin example, limitations, and a full regression acceptance record.

- [ ] **Step 1: Write a failing documentation contract test**

```python
# tests/physics/test_physics_docs.py
from pathlib import Path

ROOT = Path(__file__).parents[2]

def test_physics_document_names_engines_contracts_and_primary_citations():
    text = (ROOT / "docs" / "PHYSICS.md").read_text()
    for required in (
        "BlochEngine", "EPGEngine", "SpectralEngine",
        "RfOp", "Relax", "Shift", "GradInterval", "AdcSample",
        "Weigel 2015", "Malik et al. 2018", "10.1002/mrm.29101",
        "10.1002/mrm.30055", "mrqlab.physics_engines",
        "not a clinical", "dimensionless teaching gradients",
    ):
        assert required in text
```

- [ ] **Step 2: Run the documentation test and verify the file is absent**

Run: `python3.11 -m pytest tests/physics/test_physics_docs.py -q`

Expected: FAIL with `FileNotFoundError` for `docs/PHYSICS.md`.

- [ ] **Step 3: Create `docs/PHYSICS.md` with the complete physics v1 contract**

```markdown
# Physics v1

MRQLab is a teaching MRI simulator, not a clinical scanner, safety simulator, or hardware controller. `SequenceIR` is the only event source. The physics microkernel converts its RF, gradient, ADC-gate, and NCO channels into `RfOp`, `Relax`, `Shift`, `GradInterval`, and `AdcSample`; plugins apply those operators to their own state.

## Engines

| Engine | State | Primary teaching use | Physics v1 boundary |
|---|---|---|---|
| `BlochEngine` | Cartesian `Mxyz` per weighted isochromat | SE, GRE, off-resonance and spatial dephasing | Instantaneous RF and dimensionless teaching gradients |
| `EPGEngine` | Signed classic `(F+, F-, Z)` configuration orders | TSE/CPMG echo trains | Single pool, bounded integer orders, metadata-first `dk` |
| `SpectralEngine` | Independent chemical-shift Bloch pools | Fat/water phase and beating | No exchange, MT, CEST saturation, or fitted MRS lineshapes |

All implement `simulate(SequenceIR, Phantom, ScannerModel, EngineOptions) -> SimResult`. Recon, API, and web consume `SimResult`; they do not import engine classes.

## Units and signal convention

- IR RF amplitude and phase are degrees; the scheduler converts them to radians.
- Time is seconds.
- Current gradients are dimensionless teaching gradients scaled by `ScannerModel.gradient_scale` in Hz/m.
- Signal is `Mx + 1j*My`; positive off-resonance accumulates positive phase and NCO demodulation removes phase with a negative exponential.
- EPG shifts prefer `SequenceIR.metadata["epg_dk_events"]`. Area quantization by `EngineOptions.epg_dk_scale` is a fallback for untagged IR.

## Operators

For RF flip `α` and phase `φ`, `RfOp` applies the Weigel classic EPG matrix to `(F+, F-, Z)` and the equivalent right-hand Rodrigues rotation about `(cos φ, sin φ, 0)` to Bloch states. `Relax` applies `E1 = exp(-dt/T1)`, `E2 = exp(-dt/T2)`, with equilibrium regrowth only at `Z0`. `Shift` translates `F+` by `+dk` and `F-` by `-dk`; `Z` is unchanged. `GradInterval` applies spatial phase in Bloch/spectral states and advances the shared k-trajectory. `AdcSample` observes the current transverse state and applies NCO demodulation.

## Work safety

Before backend allocation, the kernel estimates work as operator count times backend state width: isochromat count for Bloch, `3 × (2*kmax + 1)` for EPG, and isochromat count times pool count for spectral. The API clamps request `max_work` to `SIM_MAX_WORK=2000000` by default. `SIM_MAX_MATRIX=64` remains the reconstruction/UI dimension cap. Sequence duration is not treated as wall-clock runtime.

## Plugins

External distributions publish a `SimulationEngine` instance or subclass:

```toml
[project.entry-points."mrqlab.physics_engines"]
my_engine = "my_package.engine:MyEngine"
```

Names must match the entry-point name and may not shadow `bloch`, `epg`, or `spectral`. PDG uses `PDGAdapter` with a caller-supplied provider; torch, MRzero, and pulseq-zero are not default dependencies.

## Extension seams

`diffusion_attenuation` provides the diagonal configuration-space free-diffusion propagator but is not applied to teaching-unit gradients. `EpgXLayout` fixes Bloch–McConnell and magnetization-transfer state rows; their evolution functions raise explicit physics-v1 boundary errors. This prevents partially correct exchange or MT behavior from appearing as supported simulation.

## Algorithm references

- Weigel 2015, *Extended phase graphs: dephasing, RF pulses, and echoes—pure and simple* — classic RF, shift, relaxation, and echo semantics.
- Malik et al. 2018, EPG-X — multi-pool exchange/MT layouts and diffusion extension concepts.
- Pruessmann et al. 2021, doi:10.1002/mrm.29101 — configuration-space representation and discrete EPG framing.
- Endres/Möbius et al. 2024, doi:10.1002/mrm.30055 — phase distribution graphs and the future provider-adapter direction.
- Pulseq, PyPulseq, and MaRCoS — event timing and event-stream concepts.
- imr-framework/epg, mriphysics/EPG-X, and pulseq-zero/PDG — numerical/conceptual comparison targets; their source is not vendored or copied.
```

- [ ] **Step 4: Update architecture, roadmap, and README with exact status language**

Replace `docs/ARCHITECTURE.md`'s Engine plugin map with:

```markdown
## Physics microkernel

`SequenceIR → scheduler → operators → state backend → SimResult` is the physics path. The kernel owns scheduling, radians/seconds/teaching-gradient units, work caps, ADC/NCO collection, k-trajectory, and the `mrqlab.physics_engines` registry. Bloch, classic EPG, and spectral plugins own state and operator application. Recon, API, and web never branch on a backend class.

Built-in routing is SE/GRE → Bloch and TSE → EPG through `preferred_engine` metadata; an API request may override it. Spectral simulation is explicitly selected with pool data. PDG is an optional provider seam, while exchange and MT remain explicit EPG-X boundaries.
```

Replace the physics bullets under `docs/ROADMAP.md` with:

```markdown
- Physics v1: multi-isochromat Bloch, classic bounded-order EPG, and independent fat/water spectral pools behind one microkernel.
- Next fidelity: physical gradient units and diffusion wiring, then Bloch–McConnell/MT, CEST saturation, richer MRS, and an optional PDG provider distribution.
```

Add this table to `README.md` after the monorepo table:

```markdown
## Physics engines

| Name | Selection | Best fit |
|---|---|---|
| `bloch` | Default for SE/GRE | Multi-isochromat rotations, relaxation, off-resonance, and spatial phase |
| `epg` | Default for TSE | Classic configuration-state echo trains |
| `spectral` | Explicit request with pools | Independent fat/water chemical shift |

The HTTP request may set `"engine": "bloch" | "epg" | "spectral"`; if omitted, template metadata chooses. See [Physics v1](docs/PHYSICS.md) for units, assumptions, plugins, and limitations.
```

- [ ] **Step 5: Run the full acceptance suite from a clean supported environment**

Run:

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/python -m pytest -q
```

Expected: all legacy and new tests pass; `/engines` lists `bloch`, `epg`, and `spectral` as available built-ins; no default dependency imports torch, MRzero, pulseq-zero, PyPulseq, SciPy, or SigPy.

- [ ] **Step 6: Run static acceptance checks**

Run:

```bash
rg -n "BlochEngine|EPGEngine|SpectralEngine" packages/recon apps/web
rg -n "torch|MRzero|pulseq_zero|pypulseq|sigpy|scipy" packages/physics pyproject.toml
git status --short
```

Expected: the first two searches return no runtime coupling/import matches; `git status --short` shows only the files intentionally changed by Tasks 1–13.

- [ ] **Step 7: Commit documentation and acceptance tests**

```bash
git add README.md docs/PHYSICS.md docs/ARCHITECTURE.md docs/ROADMAP.md tests/physics/test_physics_docs.py
git commit -m "docs: publish physics microkernel contract"
```

## Self-Review Against the Locked Spec

### 1. Spec coverage

| Locked requirement | Implemented by |
|---|---|
| Microkernel/plugin layout and stable unified I/O | File map; Tasks 1, 4, 9 |
| Concrete `RfOp`, `Relax`, `Shift`, `GradInterval`, `AdcSample` | Stable Contracts; Task 3 |
| IR scheduler, units, ADC/NCO semantics | Tasks 2–4 |
| Work-based caps instead of duration proxy | Tasks 2 and 7 |
| RF phase axis and multi-isochromat Bloch | Task 5 |
| Real classic EPG and TSE metadata-first `dk` | Tasks 6 and 7 |
| API selection without recon/web backend coupling | Tasks 7, 9, 13 |
| Fat/water spectral v0 | Task 8 |
| Entry-point plugins | Task 9 |
| EPG-X diffusion/BM/MT seams | Task 10 |
| PDG adapter seam without heavy defaults | Task 11 |
| Cross-engine numerical consistency | Task 12 |
| Reimplementation/citations and teaching limitations | Task 13 |

Coverage result: every locked acceptance item maps to at least one independently testable task; there are no uncovered requirements.

### 2. Placeholder scan

All code steps contain concrete signatures, values, assertions, error text, commands, and expected outcomes. Deferred physics is represented only by executable, named boundary errors required by the spec; no vague implementation instructions or fill-in markers remain.

### 3. Type consistency

- Every engine keeps the four-argument `simulate(...)->SimResult` signature from `SimulationEngine`.
- `schedule` always returns `tuple[Operator, ...]`; `run_backend` consumes that exact type.
- All backends implement `apply`, `observe`, and `snapshot` from `StateBackend`.
- `SimResult.k_trajectory` is consistently `(n_adc, 3)` and complex signal is consistently `(n_adc,)`.
- `Phantom.isochromats` and `Phantom.pools` are tuples both in models and API parsing.
- `EngineOptions.epg_kmax`, `epg_dk_scale`, and `max_work` names are identical in caps, scheduler, engines, API, and tests.
- Registry descriptors consistently expose `name`, `available`, `description`, and `source`.
- The signal convention and NCO sign are identical in Bloch, EPG, spectral, cross-engine tests, and docs.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-14-physics-engines-microkernel.md`. Two execution options:

1. **Subagent-Driven (recommended)** — Use `superpowers:subagent-driven-development`; dispatch a fresh subagent per task and perform two-stage review between tasks.
2. **Inline Execution** — Use `superpowers:executing-plans`; execute task batches in this session with review checkpoints.

Choose one approach before product-code implementation begins.
