from collections.abc import Callable
from dataclasses import dataclass
from numbers import Integral
import time
from typing import Any, Literal

from mrqlab_sequence import SequenceIR

from .backends.protocol import StateBackend
from .kernel.caps import enforce_state_work_limit
from .kernel.conventions import SIGNAL_CONVENTION
from .kernel.runner import run_backend
from .kernel.scheduler import preflight_schedule, schedule
from .models import EngineOptions, Phantom, ScannerModel, SimResult


StateWidth = Callable[[Phantom, ScannerModel, EngineOptions], int]
BackendFactory = Callable[[Phantom, ScannerModel, EngineOptions], StateBackend]
MetadataFactory = Callable[[Phantom, ScannerModel, EngineOptions], dict[str, Any]]
SnapshotField = Literal["magnetization", "configurations"]


def _empty_metadata(
    phantom: Phantom, scanner: ScannerModel, options: EngineOptions
) -> dict[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class EnginePlugin:
    """Descriptor loaded from ``mrqlab.physics_engines`` entry points.

    A plugin describes state allocation and operator application only. The
    kernel-owned :class:`SimulationEngine` performs scheduling, work caps,
    ADC/NCO sampling, trajectory tracking, and result assembly.
    """

    name: str
    description: str
    state_width: StateWidth
    backend_factory: BackendFactory
    metadata_factory: MetadataFactory = _empty_metadata
    snapshot_field: SnapshotField | None = None
    available: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("engine plugin name must be a non-empty string")
        if not isinstance(self.description, str):
            raise TypeError("engine plugin description must be a string")
        if not all(
            callable(value)
            for value in (self.state_width, self.backend_factory, self.metadata_factory)
        ):
            raise TypeError("engine plugin factories and state_width must be callable")
        if self.snapshot_field not in (None, "magnetization", "configurations"):
            raise ValueError("engine plugin snapshot_field is invalid")
        if not isinstance(self.available, bool):
            raise TypeError("engine plugin available must be a strict boolean")


class SimulationEngine:
    """Kernel-controlled four-argument simulation façade."""

    def __init__(self, plugin: EnginePlugin):
        if not isinstance(plugin, EnginePlugin):
            raise TypeError("SimulationEngine requires an EnginePlugin backend descriptor")
        self.plugin = plugin
        self.name = plugin.name.lower()
        self.description = plugin.description
        self.available = plugin.available

    def _state_width(
        self, phantom: Phantom, scanner: ScannerModel, options: EngineOptions
    ) -> int:
        width = self.plugin.state_width(phantom, scanner, options)
        if isinstance(width, bool) or not isinstance(width, Integral):
            raise TypeError(f"engine {self.name!r} state_width must return a strict integer")
        if width <= 0:
            raise ValueError(f"engine {self.name!r} state_width must be positive")
        return int(width)

    def _snapshots_requested(self, options: EngineOptions) -> bool:
        if self.plugin.snapshot_field == "magnetization":
            return options.return_magnetization
        if self.plugin.snapshot_field == "configurations":
            return options.return_configurations
        return False

    def simulate(
        self,
        sequence: SequenceIR,
        phantom: Phantom,
        scanner: ScannerModel,
        options: EngineOptions,
    ) -> SimResult:
        if not self.available:
            raise NotImplementedError(f"physics engine {self.name!r} is unavailable")
        started = time.perf_counter()
        state_width = self._state_width(phantom, scanner, options)
        plan = preflight_schedule(
            sequence,
            options,
            max_operators=options.max_work // state_width,
        )
        work = enforce_state_work_limit(
            self.name, plan.operator_count, state_width, options
        )
        operators = schedule(sequence, options, plan)
        backend = self.plugin.backend_factory(phantom, scanner, options)
        trace = run_backend(backend, operators, self._snapshots_requested(options))
        extra_meta = self.plugin.metadata_factory(phantom, scanner, options)
        if not isinstance(extra_meta, dict):
            raise TypeError("engine plugin metadata_factory must return a dict")
        meta = {
            **extra_meta,
            "engine": self.name,
            "signal_convention": SIGNAL_CONVENTION,
            "samples": int(trace.signal.size),
            "n_ops": plan.operator_count,
            "estimated_work": work,
        }
        result = SimResult(
            signal=trace.signal,
            k_trajectory=trace.k_trajectory * scanner.gradient_scale,
            meta=meta,
            timing={"simulation_seconds": time.perf_counter() - started},
        )
        if self.plugin.snapshot_field == "magnetization":
            result.magnetization = trace.snapshots
        elif self.plugin.snapshot_field == "configurations":
            result.configurations = trace.snapshots
        return result
