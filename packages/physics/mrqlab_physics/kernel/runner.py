from dataclasses import dataclass

import numpy as np

from ..backends.protocol import StateBackend
from ..ops.sample import demodulate
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
        if isinstance(op, AdcSample):
            signal.append(
                demodulate(
                    backend.observe(),
                    op.t,
                    op.nco_frequency_hz,
                    op.nco_phase_rad,
                )
            )
            trajectory.append(k.copy())
        else:
            backend.apply(op)
        if isinstance(op, GradInterval):
            k = k + np.asarray(op.gradient) * op.dt
        if return_snapshots:
            snapshots.append(backend.snapshot())
    snapshot_array = np.stack(snapshots) if snapshots else None
    trajectory_array = np.asarray(trajectory, dtype=float).reshape((-1, 3))
    return RuntimeTrace(np.asarray(signal, dtype=np.complex128), trajectory_array, snapshot_array)
