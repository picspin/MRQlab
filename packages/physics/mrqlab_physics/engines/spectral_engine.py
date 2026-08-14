import time

from ..backends.spectral import SpectralBackend
from ..base import SimulationEngine
from ..kernel.caps import enforce_work_limit
from ..kernel.conventions import SIGNAL_CONVENTION
from ..kernel.runner import run_backend
from ..kernel.scheduler import schedule
from ..models import EngineOptions, Phantom, ScannerModel, SimResult


class SpectralEngine(SimulationEngine):
    name = "spectral"
    description = "Independent fat/water chemical-shift pools"
    available = True

    def simulate(
        self, sequence, phantom: Phantom, scanner: ScannerModel, options: EngineOptions
    ) -> SimResult:
        started = time.perf_counter()
        operators = schedule(sequence, options)
        base_spins = phantom.resolved_isochromats()
        work = enforce_work_limit(
            self.name, len(operators), len(base_spins), options, len(phantom.pools)
        )
        trace = run_backend(
            SpectralBackend(phantom, scanner), operators, options.return_magnetization
        )
        return SimResult(
            signal=trace.signal,
            k_trajectory=trace.k_trajectory * scanner.gradient_scale,
            magnetization=trace.snapshots,
            meta={
                "engine": self.name,
                "signal_convention": SIGNAL_CONVENTION,
                "available": True,
                "model": "independent chemical-shift pools",
                "pools": [pool.name for pool in phantom.pools],
                "n_isochromats": len(base_spins) * len(phantom.pools),
                "n_ops": len(operators),
                "estimated_work": work,
                "assumptions": [
                    "no exchange",
                    "instantaneous RF",
                    "Lorentzian relaxation only",
                ],
            },
            timing={"simulation_seconds": time.perf_counter() - started},
        )
