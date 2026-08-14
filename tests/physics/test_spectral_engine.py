import pytest

from mrqlab_sequence import Channel, Event, SequenceIR
from mrqlab_physics import EngineOptions, Phantom, ScannerModel, SpectralPool
from mrqlab_physics.engines import SpectralEngine


GAMMA_HZ_PER_T = 42_577_478.518


def _channel(name, values):
    return Channel(name=name, events=[Event(time=t, value=v) for t, v in values])


def test_equal_fat_water_pools_cancel_at_half_beat():
    scanner = ScannerModel(b0_t=1.5)
    delta_hz = 3.5e-6 * GAMMA_HZ_PER_T * scanner.b0_t
    sample_time = 0.5 / delta_hz
    sequence = SequenceIR(name="fat-water", duration=sample_time + 1e-5, channels=[
        _channel("rf_amp", [(0.0, 90.0)]),
        _channel("rf_phase", [(0.0, 0.0)]),
        _channel("adc_gate", [(sample_time, 1.0), (sample_time + 1e-5, 0.0)]),
    ])
    phantom = Phantom(pools=(
        SpectralPool("water", 0.5, 0.0, 100.0, 100.0),
        SpectralPool("fat", 0.5, -3.5, 100.0, 100.0),
    ))

    result = SpectralEngine().simulate(sequence, phantom, scanner, EngineOptions(dwell_time=1e-5))

    assert abs(result.signal[0]) < 1e-4
    assert result.meta["pools"] == ["water", "fat"]
    assert result.meta["model"] == "independent chemical-shift pools"


def test_spectral_requires_at_least_one_pool():
    with pytest.raises(ValueError, match="at least one spectral pool"):
        SpectralEngine().simulate(
            SequenceIR(name="empty", duration=0.01, channels=[]),
            Phantom(), ScannerModel(), EngineOptions(),
        )
