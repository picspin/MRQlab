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
