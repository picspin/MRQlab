import time

import numpy as np

from ..backends.bloch import BlochBackend
from ..backends.epg import EPGBackend
from ..base import EnginePlugin, SimulationEngine
from ..kernel.caps import enforce_state_work_limit
from ..kernel.conventions import SIGNAL_CONVENTION
from ..kernel.scheduler import preflight_schedule, schedule
from ..models import SimResult
from ..ops.sample import demodulate
from ..ops.types import AdcSample, GradInterval, RfOp


def _state_width(phantom, scanner, options) -> int:
    return 3 * (2 * options.epg_kmax + 1) + 3 * len(phantom.resolved_isochromats())


def _backend(phantom, scanner, options):
    return EPGBackend(phantom, options.epg_kmax)


HYBRID_PLUGIN = EnginePlugin(
    name="hybrid",
    description="Teaching hybrid of Bloch RF and EPG evolution spans",
    state_width=_state_width,
    backend_factory=_backend,
    snapshot_field="configurations",
    representation="hybrid",
    supports=frozenset(
        {"hard_rf", "shaped_rf", "configuration_states", "spatial_encoding"}
    ),
)


class HybridEngine(SimulationEngine):
    name = "hybrid"
    description = "Teaching hybrid of Bloch RF and EPG evolution spans"

    def __init__(self):
        super().__init__(HYBRID_PLUGIN)

    def simulate(self, sequence, phantom, scanner, options) -> SimResult:
        """Run RF with Bloch and continue non-RF intervals in EPG state.

        The teaching handoff maps the observable EPG zero order to one Cartesian
        isochromat for each RF interval, then writes the rotated zero order back.
        Higher EPG orders are retained across that interval.
        """
        if len(phantom.resolved_isochromats()) != 1 or phantom.pools:
            raise RuntimeError("hybrid handoff supports one single-pool isochromat")

        started = time.perf_counter()
        width = self._state_width(phantom, scanner, options)
        plan = preflight_schedule(sequence, options, max_operators=options.max_work // width)
        work = enforce_state_work_limit(self.name, plan.operator_count, width, options)
        operators = schedule(sequence, options, plan)
        epg = EPGBackend(phantom, options.epg_kmax)
        signal: list[complex] = []
        trajectory: list[np.ndarray] = []
        snapshots: list[np.ndarray] = []
        k = np.zeros(3, dtype=float)

        for op in operators:
            if isinstance(op, RfOp):
                bloch = BlochBackend(phantom.resolved_isochromats(), scanner)
                f0 = epg.omega[0, epg.zero]
                z0 = epg.omega[2, epg.zero]
                if abs(z0.imag) > 1e-10:
                    raise RuntimeError("EPG zero-order longitudinal state is not Cartesian")
                bloch.state[0] = (f0.real, f0.imag, z0.real)
                bloch.apply(op)
                mx, my, mz = bloch.state[0]
                epg.omega[0, epg.zero] = mx + 1j * my
                epg.omega[1, epg.zero] = mx - 1j * my
                epg.omega[2, epg.zero] = mz
            elif isinstance(op, AdcSample):
                signal.append(demodulate(epg.observe(), op.t, op.nco_frequency_hz, op.nco_phase_rad))
                trajectory.append(k.copy())
            else:
                epg.apply(op)
            if isinstance(op, GradInterval):
                k = k + np.asarray(op.gradient) * op.dt
            if options.return_configurations:
                snapshots.append(epg.snapshot())

        result = SimResult(
            signal=np.asarray(signal, dtype=np.complex128),
            k_trajectory=np.asarray(trajectory, dtype=float).reshape((-1, 3)) * scanner.gradient_scale,
            configurations=np.stack(snapshots) if snapshots else None,
            meta={
                "engine": "hybrid",
                "representation": "hybrid",
                "signal_convention": SIGNAL_CONVENTION,
                "samples": len(signal),
                "n_ops": plan.operator_count,
                "estimated_work": work,
                "assumptions": [
                    "Bloch owns instantaneous shaped-RF intervals",
                    "EPG owns free evolution, gradients, shifts, and readout",
                    "zero-order Cartesian handoff; higher EPG orders retained",
                    "single-pool single-isochromat teaching stitch",
                ],
            },
            timing={"simulation_seconds": time.perf_counter() - started},
        )
        return result
