import time

from ..backends.bloch import BlochBackend
from ..base import SimulationEngine
from ..kernel.caps import enforce_work_limit
from ..kernel.conventions import SIGNAL_CONVENTION
from ..kernel.runner import run_backend
from ..kernel.scheduler import schedule
from ..models import EngineOptions, Phantom, ScannerModel, SimResult


class BlochEngine(SimulationEngine):
    name = "bloch"
    description = "Vectorized multi-isochromat Bloch simulation"

    def simulate(
        self, sequence, phantom: Phantom, scanner: ScannerModel, options: EngineOptions
    ) -> SimResult:
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
                "signal_convention": SIGNAL_CONVENTION,
                "samples": int(trace.signal.size),
                "n_isochromats": len(spins),
                "n_ops": len(operators),
                "estimated_work": work,
                "assumptions": ["instantaneous RF", "dimensionless teaching gradients"],
            },
            timing={"simulation_seconds": time.perf_counter() - started},
        )
