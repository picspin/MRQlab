import numpy as np
import pytest

from mrqlab_sequence import build_sequence
from mrqlab_sequence.models import Channel, Event, SequenceIR
from mrqlab_physics import EngineOptions, Phantom, ScannerModel
from mrqlab_physics.engines import BlochEngine
import mrqlab_physics.base as base_module
import mrqlab_physics.engines.bloch_engine as bloch_engine_module
import mrqlab_physics.kernel.scheduler as scheduler_module
from mrqlab_physics.kernel.runner import run_backend
from mrqlab_physics.kernel.scheduler import schedule
from mrqlab_physics.ops.types import AdcSample, GradInterval, Relax, RfOp, Shift


class RecordingBackend:
    def __init__(self):
        self.applied = []
        self.observed = []

    def apply(self, op):
        self.applied.append(op)

    def observe(self):
        self.observed.append(len(self.applied))
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


def test_scheduler_rejects_fractional_metadata_shift_components():
    sequence = SequenceIR(name="fractional-shift", duration=0.01, channels=[])
    sequence.metadata["epg_dk_events"] = [{"time": 0.005, "dk": [1.5, 0, 0]}]

    with pytest.raises(ValueError, match="three integer dk values"):
        schedule(sequence, EngineOptions())


def test_scheduler_places_gradient_fallback_after_rf_at_shared_timestamp():
    sequence = SequenceIR(
        name="gradient-ordering",
        duration=0.002,
        channels=[
            Channel(name="rf_amp", events=[Event(time=0.001, value=90)]),
            Channel(name="rf_phase", events=[Event(time=0.001, value=0)]),
            Channel(name="gx", events=[Event(time=0, value=1), Event(time=0.001, value=0)]),
        ],
    )

    operators = schedule(sequence, EngineOptions(epg_dk_scale=0.001))

    shared_time = [op for op in operators if op.t == 0.001]
    assert [type(op) for op in shared_time] == [RfOp, Shift, Relax, GradInterval]
    assert shared_time[1] == Shift(0.001, (1, 0, 0), "gradient_area")


def test_scheduler_converts_rf_and_nco_phases_and_samples_before_new_interval():
    sequence = SequenceIR(
        name="phase-and-adc-ordering",
        duration=0.002,
        channels=[
            Channel(name="rf_amp", events=[Event(time=0.001, value=90)]),
            Channel(name="rf_phase", events=[Event(time=0.001, value=90)]),
            Channel(name="gx", events=[Event(time=0, value=1), Event(time=0.001, value=0)]),
            Channel(name="adc_gate", events=[Event(time=0.001, value=1), Event(time=0.002, value=0)]),
            Channel(name="nco_freq", events=[Event(time=0, value=123)]),
            Channel(name="nco_phase", events=[Event(time=0, value=180)]),
        ],
    )

    operators = schedule(sequence, EngineOptions(dwell_time=0.001, epg_dk_scale=0.001))
    shared_time = [op for op in operators if op.t == 0.001]
    rf, shift, adc, relax, gradient = shared_time
    backend = RecordingBackend()
    run_backend(backend, operators, return_snapshots=False)

    assert [type(op) for op in shared_time] == [RfOp, Shift, AdcSample, Relax, GradInterval]
    assert rf.phase_rad == pytest.approx(np.pi / 2)
    assert adc.nco_frequency_hz == 123
    assert adc.nco_phase_rad == pytest.approx(np.pi)
    assert adc not in backend.applied
    assert backend.observed == [backend.applied.index(shift) + 1]
    assert backend.applied[backend.observed[0]] == relax
    assert gradient.t == adc.t


def test_scheduler_metadata_shifts_suppress_gradient_area_fallback():
    sequence = SequenceIR(
        name="metadata-precedence",
        duration=0.002,
        channels=[Channel(name="gx", events=[Event(time=0, value=1), Event(time=0.001, value=0)])],
        metadata={"epg_dk_events": [{"time": 0.001, "dk": [3, 0, 0]}]},
    )

    shifts = [op for op in schedule(sequence, EngineOptions(epg_dk_scale=0.001)) if isinstance(op, Shift)]

    assert shifts == [Shift(0.001, (3, 0, 0), "metadata")]


def test_arithmetic_preflight_rejects_work_before_scheduler_materialization(monkeypatch):
    sequence = SequenceIR(
        name="preflight",
        duration=0.101,
        channels=[
            Channel(
                name="adc_gate",
                events=[Event(time=0.001, value=1), Event(time=0.101, value=0)],
            )
        ],
    )

    def fail_if_materialized(*args, **kwargs):
        raise AssertionError("scheduler materialized before arithmetic work preflight")

    monkeypatch.setattr(scheduler_module, "schedule", fail_if_materialized)
    monkeypatch.setattr(base_module, "schedule", fail_if_materialized)
    monkeypatch.setattr(bloch_engine_module, "schedule", fail_if_materialized, raising=False)

    with pytest.raises(ValueError, match="estimated work"):
        BlochEngine().simulate(
            sequence,
            Phantom(),
            ScannerModel(),
            EngineOptions(dwell_time=0.001, max_work=1),
        )


def test_scheduler_enforces_explicit_event_limit(monkeypatch):
    sequence = SequenceIR(
        name="event-limit",
        duration=0.01,
        channels=[
            Channel(
                name="gx",
                events=[Event(time=0.0, value=0.0), Event(time=0.01, value=0.0)],
            )
        ],
    )
    monkeypatch.setattr(scheduler_module, "MAX_SEQUENCE_EVENTS", 1, raising=False)

    with pytest.raises(ValueError, match="event limit"):
        schedule(sequence, EngineOptions())


def test_scheduler_enforces_explicit_adc_sample_limit(monkeypatch):
    sequence = SequenceIR(
        name="sample-limit",
        duration=0.003,
        channels=[
            Channel(
                name="adc_gate",
                events=[Event(time=0.0, value=1.0), Event(time=0.003, value=0.0)],
            )
        ],
    )
    monkeypatch.setattr(scheduler_module, "MAX_ADC_SAMPLES", 2, raising=False)

    with pytest.raises(ValueError, match="ADC sample limit"):
        schedule(sequence, EngineOptions(dwell_time=0.001))


@pytest.mark.parametrize(
    "raw",
    [
        {},
        {"time": 0.005},
        {"dk": [1, 0, 0]},
        None,
        {"time": 0.005, "dk": "bad"},
    ],
)
def test_scheduler_rejects_malformed_metadata_shifts_as_validation_errors(raw):
    sequence = SequenceIR(
        name="malformed-shift",
        duration=0.01,
        channels=[],
        metadata={"epg_dk_events": [raw]},
    )

    with pytest.raises(ValueError, match="epg_dk_event"):
        schedule(sequence, EngineOptions())
