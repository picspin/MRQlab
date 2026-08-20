from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field


class ProtocolSpec(BaseModel):
    id: str = "A"
    name: str = "Protocol"
    flip_angle_deg: float = Field(default=150.0, gt=0)
    te_eff_ms: float = Field(default=100.0, gt=0)
    b0_t: float = Field(default=3.0, gt=0)
    echo_train_length: int = Field(default=16, ge=1)
    echo_spacing_ms: float = Field(default=12.5, gt=0)
    target_t2_ms: float = Field(default=120.0, gt=0)
    reference_t2_ms: float = Field(default=80.0, gt=0)


class CompareRequest(BaseModel):
    protocol_a: ProtocolSpec = Field(default_factory=lambda: ProtocolSpec(id="A", name="Protocol A"))
    protocol_b: ProtocolSpec = Field(
        default_factory=lambda: ProtocolSpec(id="B", name="Protocol B", flip_angle_deg=120.0, te_eff_ms=80.0)
    )


class CompareProtocol(BaseModel):
    id: str
    name: str
    flip_angle_deg: float
    te_eff_ms: float
    b0_t: float
    echo_train: list[float]
    target_signal: float
    reference_signal: float
    contrast_diff: float
    cnr_proxy: float
    relative_sar: float


class CompareDelta(BaseModel):
    contrast_pct: float
    cnr_delta: float
    sar_delta: float


class CompareAnalysis(BaseModel):
    protocol_a: CompareProtocol
    protocol_b: CompareProtocol
    delta: CompareDelta


def evaluate_protocol(spec: ProtocolSpec) -> CompareProtocol:
    """Backend-owned TSE echo-train / contrast / CNR-proxy / relative SAR."""
    fa_rad = math.radians(spec.flip_angle_deg)
    refocus = math.sin(fa_rad / 2.0) ** 2
    echo_train: list[float] = []
    for i in range(1, spec.echo_train_length + 1):
        t = i * spec.echo_spacing_ms
        decay = math.exp(-t / spec.target_t2_ms) * (0.3 + 0.7 * refocus)
        echo_train.append(round(decay, 3))

    target = refocus * math.exp(-spec.te_eff_ms / spec.target_t2_ms)
    reference = refocus * math.exp(-spec.te_eff_ms / spec.reference_t2_ms)
    contrast = abs(target - reference)
    noise_floor = 0.05 / math.sqrt(spec.b0_t / 1.5)
    cnr = contrast / noise_floor
    relative_sar = spec.echo_train_length * (spec.flip_angle_deg / 180.0) ** 2 * (spec.b0_t / 1.5) ** 2

    return CompareProtocol(
        id=spec.id,
        name=spec.name,
        flip_angle_deg=spec.flip_angle_deg,
        te_eff_ms=spec.te_eff_ms,
        b0_t=spec.b0_t,
        echo_train=echo_train,
        target_signal=round(target, 3),
        reference_signal=round(reference, 3),
        contrast_diff=round(contrast, 3),
        cnr_proxy=round(cnr, 2),
        relative_sar=round(relative_sar, 1),
    )


def compute_compare(req: CompareRequest) -> CompareAnalysis:
    a = evaluate_protocol(req.protocol_a)
    b = evaluate_protocol(req.protocol_b)
    contrast_pct = ((b.contrast_diff - a.contrast_diff) / (a.contrast_diff or 1.0)) * 100.0
    return CompareAnalysis(
        protocol_a=a,
        protocol_b=b,
        delta=CompareDelta(
            contrast_pct=round(contrast_pct, 1),
            cnr_delta=round(b.cnr_proxy - a.cnr_proxy, 2),
            sar_delta=round(b.relative_sar - a.relative_sar, 1),
        ),
    )


def compute_compare_dict(req: CompareRequest) -> dict[str, Any]:
    return compute_compare(req).model_dump(mode="json")
