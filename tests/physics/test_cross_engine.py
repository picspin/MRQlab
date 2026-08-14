import numpy as np
import pytest

from mrqlab_sequence import Channel, Event, SequenceIR
from mrqlab_physics import EngineOptions, Phantom, ScannerModel, SpectralPool
from mrqlab_physics.engines import BlochEngine, EPGEngine, SpectralEngine
from mrqlab_physics.kernel.conventions import SIGNAL_CONVENTION


def _channel(name, values):
    return Channel(name=name, events=[Event(time=t, value=v) for t, v in values])


def _fid(sample_time=0.02):
    return SequenceIR(
        name="overlap-fid",
        duration=sample_time + 0.001,
        channels=[
            _channel("rf_amp", [(0.0, 90.0)]),
            _channel("rf_phase", [(0.0, 0.0)]),
            _channel("adc_gate", [(sample_time, 1.0), (sample_time + 0.001, 0.0)]),
        ],
        metadata={"epg_dk_events": []},
    )


def test_bloch_epg_and_one_pool_spectral_agree_on_fid():
    sequence = _fid()
    options = EngineOptions(dwell_time=0.001, epg_kmax=2)
    phantom = Phantom(t1=1.0, t2=0.08, proton_density=0.7, off_resonance_hz=3.0)
    spectral = Phantom(
        t1=phantom.t1,
        t2=phantom.t2,
        proton_density=phantom.proton_density,
        off_resonance_hz=phantom.off_resonance_hz,
        pools=(SpectralPool("water", 1.0, 0.0, phantom.t1, phantom.t2),),
    )
    results = [
        BlochEngine().simulate(sequence, phantom, ScannerModel(), options),
        EPGEngine().simulate(sequence, phantom, ScannerModel(), options),
        SpectralEngine().simulate(sequence, spectral, ScannerModel(), options),
    ]
    np.testing.assert_allclose(
        [result.signal[0] for result in results], results[0].signal[0], atol=1e-10
    )
    assert {result.meta["signal_convention"] for result in results} == {SIGNAL_CONVENTION}


def test_cross_engine_t2_decay_matches_analytic_value():
    sequence = _fid(sample_time=0.08)
    phantom = Phantom(t1=100, t2=0.08)
    options = EngineOptions(epg_kmax=1)
    bloch = BlochEngine().simulate(sequence, phantom, ScannerModel(), options)
    epg = EPGEngine().simulate(sequence, phantom, ScannerModel(), options)
    assert abs(bloch.signal[0]) == pytest.approx(np.exp(-1), rel=1e-6)
    assert abs(epg.signal[0]) == pytest.approx(np.exp(-1), rel=1e-6)
