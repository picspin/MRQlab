from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, Field


PulseKind = Literal["hard", "shaped_sinc", "gaussian", "custom"]


def _sinc(x: float) -> float:
    if abs(x) < 1e-12:
        return 1.0
    return math.sin(math.pi * x) / (math.pi * x)


class PulseInspectRequest(BaseModel):
    flip_angle_deg: float = Field(default=150.0)
    phase_deg: float = Field(default=90.0)
    duration_ms: float = Field(default=2.5, gt=0)
    slice_thickness_mm: float = Field(default=5.0, gt=0)
    time_bandwidth: float = Field(default=4.0, gt=0)
    kind: PulseKind = "shaped_sinc"
    n_time: int = Field(default=61, ge=9, le=129)
    n_freq: int = Field(default=51, ge=9, le=129)
    n_z: int = Field(default=51, ge=9, le=129)


class PulseInspectAnalysis(BaseModel):
    id: str
    name: str
    kind: PulseKind
    flip_angle_deg: float
    phase_deg: float
    duration_ms: float
    time_bandwidth: float
    slice_thickness_mm: float
    waveform_time: list[float]
    waveform_b1: list[float]
    freq_axis_khz: list[float]
    freq_response_mag: list[float]
    spatial_axis_mm: list[float]
    slice_profile_mz: list[float]
    slice_profile_mxy: list[float]
    epg_transition_matrix: list[list[float]]
    peak_b1: float
    bw_khz: float


def inspect_pulse(req: PulseInspectRequest) -> PulseInspectAnalysis:
    n_time = req.n_time
    duration = req.duration_ms
    tbw = req.time_bandwidth
    fa = req.flip_angle_deg
    thickness = req.slice_thickness_mm

    waveform_time: list[float] = []
    waveform_b1: list[float] = []
    for i in range(n_time):
        t = (i / (n_time - 1) - 0.5) * duration
        waveform_time.append(t)
        x = (t / (duration / 2.0)) * (tbw / 2.0)
        win = 0.5 * (1.0 + math.cos((2.0 * math.pi * i) / (n_time - 1) - math.pi))
        waveform_b1.append(_sinc(x) * win * (fa / 180.0))

    n_freq = req.n_freq
    bw_khz = tbw / duration
    freq_axis: list[float] = []
    freq_mag: list[float] = []
    sin_fa = math.sin(math.radians(fa))
    for i in range(n_freq):
        f = (i / (n_freq - 1) - 0.5) * (bw_khz * 3.0)
        freq_axis.append(f)
        arg = f / (bw_khz / 2.0) if bw_khz > 0 else 0.0
        freq_mag.append(abs(_sinc(arg) * sin_fa))

    n_z = req.n_z
    spatial: list[float] = []
    mz: list[float] = []
    mxy: list[float] = []
    for i in range(n_z):
        z = (i / (n_z - 1) - 0.5) * (thickness * 3.0)
        spatial.append(z)
        ratio = z / (thickness / 2.0)
        theta = math.asin(max(-1.0, min(1.0, _sinc(ratio) * sin_fa)))
        mz.append(math.cos(theta))
        mxy.append(abs(math.sin(theta)))

    alpha = math.radians(fa)
    cos_a2 = math.cos(alpha / 2.0) ** 2
    sin_a2 = math.sin(alpha / 2.0) ** 2
    sin_a = math.sin(alpha)
    epg = [
        [cos_a2, sin_a2, sin_a],
        [sin_a2, cos_a2, sin_a],
        [-0.5 * sin_a, 0.5 * sin_a, math.cos(alpha)],
    ]

    return PulseInspectAnalysis(
        id="refocusing_pulse_1",
        name="Refocusing Sinc Pulse (RF #2..16)",
        kind=req.kind,
        flip_angle_deg=fa,
        phase_deg=req.phase_deg,
        duration_ms=duration,
        time_bandwidth=tbw,
        slice_thickness_mm=thickness,
        waveform_time=waveform_time,
        waveform_b1=waveform_b1,
        freq_axis_khz=freq_axis,
        freq_response_mag=freq_mag,
        spatial_axis_mm=spatial,
        slice_profile_mz=mz,
        slice_profile_mxy=mxy,
        epg_transition_matrix=epg,
        peak_b1=max(abs(v) for v in waveform_b1),
        bw_khz=bw_khz,
    )


def inspect_pulse_dict(req: PulseInspectRequest) -> dict[str, Any]:
    return inspect_pulse(req).model_dump()
