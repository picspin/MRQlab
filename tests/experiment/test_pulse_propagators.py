import math
import numpy as np
import pytest

from mrqlab_experiment.pulse import (
    PulseDefinition,
    PulseCompiler,
    PulsePropagator,
    HardPulsePropagator,
    SmallTipPropagator,
    SpatialBlochPropagator,
    compile_pulse,
)


def test_hard_pulse_propagator_rotation():
    # 90 deg along X in standard right-handed rotating frame rotates [0, 0, 1] to [0, -1, 0]
    pulse = PulseDefinition(
        kind="hard",
        flip_angle_deg=90.0,
        phase_deg=0.0,
        duration_s=0.001,
    )
    prop = compile_pulse(pulse)
    assert isinstance(prop, HardPulsePropagator)
    m0 = np.array([0.0, 0.0, 1.0])
    m1 = prop.propagate(m0)
    assert np.allclose(m1, [0.0, -1.0, 0.0], atol=1e-5)


def test_small_tip_angle_profile_approximation():
    # Small tip angle (e.g. 10 deg sinc/gaussian pulse)
    pulse = PulseDefinition(
        kind="shaped_sinc",
        flip_angle_deg=10.0,
        phase_deg=0.0,
        duration_s=0.002,
        time_bandwidth=4.0,
    )
    prop = compile_pulse(pulse, method="small_tip")
    assert isinstance(prop, SmallTipPropagator)
    # Check frequency response / excitation profile computation
    freqs = np.linspace(-1000, 1000, 21)
    profile = prop.frequency_response(freqs)
    assert len(profile) == len(freqs)
    # Peak at on-resonance (0 Hz)
    center_idx = len(freqs) // 2
    assert np.abs(profile[center_idx]) > np.abs(profile[0])


def test_spatial_bloch_propagator_slice_profile():
    pulse = PulseDefinition(
        kind="shaped_sinc",
        flip_angle_deg=90.0,
        phase_deg=0.0,
        duration_s=0.002,
        time_bandwidth=4.0,
        slice_thickness_m=0.005,
    )
    prop = compile_pulse(pulse, method="spatial_bloch")
    assert isinstance(prop, SpatialBlochPropagator)
    z_positions = np.linspace(-0.01, 0.01, 21)
    profiles = prop.slice_profile(z_positions, t1=1.0, t2=0.1, gradient_g_m=0.02)
    assert profiles.shape == (21, 3)
    # On-slice center (z=0) has high transverse magnetization
    center_idx = len(z_positions) // 2
    assert np.sqrt(profiles[center_idx, 0]**2 + profiles[center_idx, 1]**2) > 0.8
    # Out of slice (z far) stays longitudinal
    assert profiles[0, 2] > 0.8
