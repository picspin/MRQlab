import pytest
from mrqlab_experiment.gradient import (
    DiffusionSpec,
    GradientHardwareConstraints,
    GradientPulseSpec,
    calculate_diffusion_b_value,
    generate_diffusion_waveform,
    validate_gradient,
)


def test_gradient_hardware_validation():
    hw = GradientHardwareConstraints(max_gradient_mt_m=45.0, max_slew_rate_t_m_s=150.0)
    
    # 1. Valid trapezoid gradient
    grad_valid = GradientPulseSpec(amplitude_mt_m=30.0, duration_ms=2.0, ramp_time_ms=0.5)
    res_valid = validate_gradient(grad_valid, hw)
    assert res_valid.is_valid is True
    assert len(res_valid.violations) == 0
    assert res_valid.actual_slew_rate == 60.0  # 30 mT/m / 0.5 ms = 60 T/m/s

    # 2. Exceeding Gmax
    grad_high_amp = GradientPulseSpec(amplitude_mt_m=50.0, duration_ms=2.0, ramp_time_ms=1.0)
    res_high_amp = validate_gradient(grad_high_amp, hw)
    assert res_high_amp.is_valid is False
    assert any("exceeds Gmax" in v for v in res_high_amp.violations)

    # 3. Exceeding SlewRateMax
    grad_fast_ramp = GradientPulseSpec(amplitude_mt_m=40.0, duration_ms=2.0, ramp_time_ms=0.2)
    res_fast_ramp = validate_gradient(grad_fast_ramp, hw)
    assert res_fast_ramp.is_valid is False
    assert any("exceeds SlewRateMax" in v for v in res_fast_ramp.violations)
    assert res_fast_ramp.actual_slew_rate == 200.0


def test_diffusion_b_value_and_waveform():
    # Clinical DWI typically: G=40 mT/m, delta=18 ms, Delta=35 ms -> b ~ 800 - 1000 s/mm²
    diff = DiffusionSpec(g_max_mt_m=40.0, delta_small_ms=18.0, delta_big_ms=35.0)
    b_val = calculate_diffusion_b_value(diff)
    
    assert 700.0 < b_val < 1100.0

    # Waveform generation
    waveform = generate_diffusion_waveform(diff, num_points=50)
    assert "time_ms" in waveform
    assert "gradient_mt_m" in waveform
    assert len(waveform["time_ms"]) == 50
    assert waveform["b_value_s_mm2"] == b_val
