"""Phase-distribution graph propagation on a one-dimensional spatial grid."""

import time

import numpy as np

from ..backends.epg import EPGBackend
from ..base import EnginePlugin, SimulationEngine
from ..kernel.caps import enforce_state_work_limit
from ..kernel.conventions import SIGNAL_CONVENTION
from ..kernel.runner import run_backend
from ..kernel.scheduler import preflight_schedule, schedule
from ..models import Phantom, SimResult
from ..ops.types import GradInterval


_GAMMA_HZ_T = 42.57747892e6


class _SpatialEPGBackend:
    def __init__(self, phantom, kmax, x_m, off_hz):
        self.x_m = x_m
        self.backends = [
            EPGBackend(
                Phantom(phantom.t1, phantom.t2, phantom.proton_density, float(value)),
                kmax,
            )
            for value in off_hz
        ]

    def apply(self, op):
        for backend in self.backends:
            backend.apply(op)
        if isinstance(op, GradInterval) and op.gradient[0] != 0:
            phase = np.exp(2j * np.pi * _GAMMA_HZ_T * op.gradient[0] * self.x_m * op.dt)
            for backend, value in zip(self.backends, phase, strict=True):
                backend.omega[0] *= value
                backend.omega[1] *= np.conj(value)

    def observe(self):
        return complex(np.mean([backend.observe() for backend in self.backends]))

    def snapshot(self):
        return np.stack([backend.snapshot() for backend in self.backends])


def _state_width(phantom, scanner, options):
    return 32 * 3 * (2 * min(options.epg_kmax, 8) + 1)


def _unavailable_backend(phantom, scanner, options):
    raise RuntimeError("pdg uses its dedicated spatial configuration-state compiler path")


PDG_PLUGIN = EnginePlugin(
    name="pdg",
    description="Spatial phase-distribution graph with bin-wise EPG states",
    state_width=_state_width,
    backend_factory=_unavailable_backend,
    representation="pdg",
    supports=frozenset({"hard_rf", "configuration_states", "spatial_encoding", "off_resonance", "phase_distribution"}),
)


class PdgEngine(SimulationEngine):
    name = "pdg"
    description = PDG_PLUGIN.description

    def __init__(self):
        super().__init__(PDG_PLUGIN)

    def simulate(self, sequence, phantom, scanner, options):
        params = sequence.metadata.get("pdg")
        if not isinstance(params, dict):
            raise ValueError("pdg requires b0_map parameters")
        count = int(params.get("samples", params.get("bins", 32)))
        fov = float(params.get("fov_m", sequence.metadata.get("fov_m", 0.22)))
        if count < 16 or not np.isfinite(fov) or fov <= 0:
            raise ValueError("pdg requires at least 16 bins and a positive finite FOV")
        x_m = np.linspace(-fov / 2.0, fov / 2.0, count)
        explicit = params.get("off_resonance_hz")
        if explicit is None:
            peak_hz = float(params.get("peak_hz", 0.0))
            if not np.isfinite(peak_hz):
                raise ValueError("pdg peak_hz must be finite")
            off_hz = peak_hz * x_m / (fov / 2.0)
        else:
            off_hz = np.asarray(explicit, dtype=float)
            if off_hz.shape != x_m.shape or not np.all(np.isfinite(off_hz)):
                raise ValueError("off_resonance_hz must be a finite array matching the pdg grid")

        started = time.perf_counter()
        plan = preflight_schedule(sequence, options, max_operators=options.max_work)
        kmax = min(options.epg_kmax, 8)
        width = count * 3 * (2 * kmax + 1)
        work = enforce_state_work_limit(self.name, plan.operator_count, width, options)
        backend = _SpatialEPGBackend(phantom, kmax, x_m, off_hz)
        trace = run_backend(backend, schedule(sequence, options, plan), False)
        configurations = backend.snapshot()
        return SimResult(
            signal=trace.signal,
            k_trajectory=trace.k_trajectory * scanner.gradient_scale,
            phase_distribution={
                "x_m": x_m,
                "off_hz": off_hz,
                "configurations": configurations,
                "image": np.abs(configurations[:, 0, kmax]),
            },
            meta={
                "engine": "pdg",
                "representation": "pdg",
                "signal_convention": SIGNAL_CONVENTION,
                "samples": int(trace.signal.size),
                "n_ops": plan.operator_count,
                "estimated_work": work,
                "assumptions": ["one-dimensional frequency-encode grid", "bin-wise EPG configuration states"],
            },
            timing={"simulation_seconds": time.perf_counter() - started},
        )
