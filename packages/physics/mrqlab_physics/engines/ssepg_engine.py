"""Slice-selective spatial Bloch engine for the Level-3 ssEPG product.

The z profile is propagated in the rotating frame with RF and Gz active in
the same time steps.  Conventional echo-train observations remain owned by
the bounded EPG propagation; no spatial states or PDG image are fabricated.
"""

import numpy as np

from ..base import EnginePlugin, SimulationEngine
from .epg_engine import EPGEngine


_GAMMA_RAD_T_S = 267.52218744e6


def _state_width(phantom, scanner, options) -> int:
    return 3 * (2 * options.epg_kmax + 1) + 3 * 64


def _unavailable_backend(phantom, scanner, options, sequence):
    raise RuntimeError("ssepg uses its dedicated spatial Bloch compiler path")


SSEPG_PLUGIN = EnginePlugin(
    name="ssepg",
    description="Slice-selective shaped RF on a one-dimensional spatial Bloch grid",
    state_width=_state_width,
    backend_factory=_unavailable_backend,
    representation="ssepg",
    supports=frozenset(
        {"hard_rf", "shaped_rf", "configuration_states", "spatial_encoding", "slice_selective"}
    ),
)


def _profile(sequence, phantom):
    params = sequence.metadata.get("ssepg")
    if not isinstance(params, dict):
        raise ValueError("ssepg requires slice_profile parameters")
    count = int(params.get("samples", params.get("z_samples", 64)))
    if count < 16:
        raise ValueError("ssepg z-grid requires at least 16 samples")
    thickness = float(params.get("slice_thickness_m", params.get("thickness_m", 0.005)))
    if "slice_thickness_mm" in params:
        thickness = float(params["slice_thickness_mm"]) * 1e-3
    duration = float(params.get("duration_s", 0.001))
    steps = int(params.get("rf_samples", max(64, count)))
    time_bandwidth = float(params.get("time_bandwidth", 4.0))
    if thickness <= 0 or duration <= 0 or steps < 8:
        raise ValueError("ssepg thickness, duration, and RF sampling must be positive")

    z = np.linspace(-2.0 * thickness, 2.0 * thickness, count)
    b1_value = params.get("b1_scale", 1.0)
    if isinstance(b1_value, (list, tuple)):
        b1 = np.asarray(b1_value, dtype=float)
        if b1.shape != z.shape:
            raise ValueError("b1_scale array must match the ssepg z-grid")
    else:
        b1 = np.full(count, float(b1_value))
    ramp = float(params.get("b1_linear_ramp", params.get("b1_ramp", 0.0)))
    b1 *= 1.0 + ramp * z / (2.0 * thickness)

    rf_channel = next((channel for channel in sequence.channels if channel.name == "rf_amp"), None)
    if rf_channel is None or not rf_channel.events:
        raise ValueError("ssepg requires an RF event")
    flip = np.deg2rad(float(rf_channel.events[0].value))
    u = (np.arange(steps, dtype=float) + 0.5) / steps - 0.5
    envelope = np.sinc(time_bandwidth * u)
    envelope *= flip / np.sum(envelope)
    dt = duration / steps
    gradient_t_m = time_bandwidth / (_GAMMA_RAD_T_S / (2.0 * np.pi) * thickness * duration)
    off_hz = phantom.off_resonance_hz + float(params.get("off_resonance_hz", 0.0))

    magnetization = np.zeros((count, 3), dtype=float)
    magnetization[:, 2] = phantom.proton_density
    for rf_angle in envelope:
        wx = rf_angle * b1
        wz = 2.0 * np.pi * off_hz * dt + _GAMMA_RAD_T_S * gradient_t_m * z * dt
        theta = np.hypot(wx, wz)
        axis_x = np.divide(wx, theta, out=np.zeros_like(theta), where=theta != 0)
        axis_z = np.divide(wz, theta, out=np.ones_like(theta), where=theta != 0)
        cosine, sine = np.cos(theta), np.sin(theta)
        cross = np.column_stack((-axis_z * magnetization[:, 1], axis_z * magnetization[:, 0] - axis_x * magnetization[:, 2], axis_x * magnetization[:, 1]))
        dot = axis_x * magnetization[:, 0] + axis_z * magnetization[:, 2]
        axis = np.column_stack((axis_x, np.zeros(count), axis_z))
        magnetization = magnetization * cosine[:, None] + cross * sine[:, None] + axis * (dot * (1.0 - cosine))[:, None]
        magnetization[:, :2] *= np.exp(-dt / phantom.t2)
        magnetization[:, 2] = phantom.proton_density + (magnetization[:, 2] - phantom.proton_density) * np.exp(-dt / phantom.t1)
    return {"z_m": z, "mz": magnetization[:, 2], "mxy": np.hypot(magnetization[:, 0], magnetization[:, 1])}


class SsepgEngine(SimulationEngine):
    name = "ssepg"
    description = SSEPG_PLUGIN.description

    def __init__(self):
        super().__init__(SSEPG_PLUGIN)

    def simulate(self, sequence, phantom, scanner, options):
        profile = _profile(sequence, phantom)
        result = EPGEngine().simulate(sequence, phantom, scanner, options)
        result.slice_profile = profile
        result.meta.update(
            engine="ssepg",
            representation="ssepg",
            assumptions=[
                "one-dimensional z-grid spatial Bloch propagation",
                "shaped RF and slice-select Gz time-stepped together",
                "EPG owns the non-spatial echo train after slice excitation",
            ],
        )
        return result
