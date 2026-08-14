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
