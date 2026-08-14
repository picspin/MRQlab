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

    def simulate(
        self, sequence, phantom: Phantom, scanner: ScannerModel, options: EngineOptions
    ) -> SimResult:
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
