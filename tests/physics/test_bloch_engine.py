import numpy as np
import pytest
from mrqlab_sequence import Channel, Event, SequenceIR, build_sequence
from mrqlab_physics import EngineOptions, Isochromat, Phantom, ScannerModel
from mrqlab_physics.engines import BlochEngine


def _channel(name, values):
    return Channel(name=name, events=[Event(time=t, value=v) for t, v in values])


def test_rf_phase_90_rotates_z_toward_positive_x():
    sequence = SequenceIR(name="phase", duration=0.01, channels=[
        _channel("rf_amp", [(0.0, 90.0)]),
        _channel("rf_phase", [(0.0, 90.0)]),
        _channel("adc_gate", [(0.0, 1.0), (0.001, 0.0)]),
    ])
    result = BlochEngine().simulate(sequence, Phantom(), ScannerModel(), EngineOptions())
    assert result.signal[0].real == pytest.approx(1.0, abs=1e-12)
    assert result.signal[0].imag == pytest.approx(0.0, abs=1e-12)


def test_symmetric_isochromats_dephase_at_quarter_period():
    sequence = SequenceIR(name="fan", duration=0.251, channels=[
        _channel("rf_amp", [(0.0, 90.0)]),
        _channel("rf_phase", [(0.0, 0.0)]),
        _channel("adc_gate", [(0.25, 1.0), (0.251, 0.0)]),
    ])
    phantom = Phantom(isochromats=(
        Isochromat(t1=100, t2=100, off_resonance_hz=-1, weight=0.5),
        Isochromat(t1=100, t2=100, off_resonance_hz=1, weight=0.5),
    ))
    result = BlochEngine().simulate(sequence, phantom, ScannerModel(), EngineOptions())
    assert abs(result.signal[0]) < 0.01
    assert result.meta["n_isochromats"] == 2
    assert result.meta["estimated_work"] > 0


def test_se_and_gre_remain_primary_bloch_templates():
    for name in ("SE", "GRE"):
        result = BlochEngine().simulate(
            build_sequence(name, {"te": 0.02, "tr": 0.1}),
            Phantom(), ScannerModel(), EngineOptions(),
        )
        assert result.signal.size == 2


def test_gradient_scale_controls_spatial_phase_and_k_trajectory():
    sequence = SequenceIR(name="gradient-golden", duration=0.251, channels=[
        _channel("rf_amp", [(0.0, 90.0)]),
        _channel("rf_phase", [(0.0, 90.0)]),
        _channel("gx", [(0.0, 2.0), (0.25, 0.0)]),
        _channel("adc_gate", [(0.25, 1.0), (0.251, 0.0)]),
    ])
    phantom = Phantom(isochromats=(
        Isochromat(t1=1e9, t2=1e9, position_m=(0.5, 0.0, 0.0)),
    ))

    result = BlochEngine().simulate(
        sequence,
        phantom,
        ScannerModel(gradient_scale=3.0),
        EngineOptions(dwell_time=0.001),
    )

    assert result.signal[0] == pytest.approx(-1j, abs=1e-9)
    np.testing.assert_allclose(result.k_trajectory, [[1.5, 0.0, 0.0]], atol=1e-12)
