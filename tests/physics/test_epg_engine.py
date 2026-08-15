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


def test_three_echo_cpmg_train_matches_independent_t2_envelope():
    echo_times = np.array([0.02, 0.04, 0.06])
    sequence = SequenceIR(
        name="three-echo-cpmg",
        duration=0.061,
        channels=[
            _channel("rf_amp", [(0.0, 90.0), (0.01, 180.0), (0.03, 180.0), (0.05, 180.0)]),
            _channel("rf_phase", [(0.0, 0.0), (0.01, 90.0), (0.03, 90.0), (0.05, 90.0)]),
            _channel(
                "adc_gate",
                [(0.02, 1.0), (0.021, 0.0), (0.04, 1.0), (0.041, 0.0), (0.06, 1.0), (0.061, 0.0)],
            ),
        ],
        metadata={
            "epg_dk_events": [
                {"time": time, "dk": [1, 0, 0]}
                for time in (0.005, 0.015, 0.025, 0.035, 0.045, 0.055)
            ]
        },
    )

    result = EPGEngine().simulate(
        sequence,
        Phantom(t1=1000.0, t2=0.04),
        ScannerModel(),
        EngineOptions(dwell_time=0.001, epg_kmax=8),
    )

    np.testing.assert_allclose(np.abs(result.signal), np.exp(-echo_times / 0.04), atol=1e-10)
