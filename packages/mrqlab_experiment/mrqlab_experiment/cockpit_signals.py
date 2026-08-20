from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, Field


SeqType = Literal["TSE", "GRE", "SE"]


class CockpitTissue(BaseModel):
    id: str
    name: str = ""
    t1: float = Field(gt=0)  # ms
    t2: float = Field(gt=0)  # ms
    t2s: float | None = None
    pd: float = Field(default=1.0, ge=0)


class CockpitSignalRequest(BaseModel):
    seq_type: SeqType = "TSE"
    fa_deg: float = Field(default=150.0, gt=0)
    te_ms: float = Field(default=100.0, gt=0)
    tr_ms: float = Field(default=3000.0, gt=0)
    echo_train_length: int = Field(default=16, ge=1)
    tissues: list[CockpitTissue]


class TissueIntensity(BaseModel):
    id: str
    name: str
    intensity: float


class CockpitSignalAnalysis(BaseModel):
    seq_type: SeqType
    fa_deg: float
    te_ms: float
    tr_ms: float
    is_gre: bool
    refocus_eff: float
    relative_sar: float
    delta_signal: float
    cnr_proxy: float
    tissues: list[TissueIntensity]
    signals: dict[str, float]


def _ernst_signal(pd: float, t1: float, t2star: float, fa_rad: float, te_ms: float, tr_ms: float) -> float:
    e1 = math.exp(-tr_ms / t1)
    e2s = math.exp(-te_ms / t2star)
    denom = 1.0 - e1 * math.cos(fa_rad)
    if abs(denom) < 1e-12:
        denom = 1e-12
    return pd * ((1.0 - e1) * math.sin(fa_rad) / denom) * e2s


def _tse_signal(pd: float, t1: float, t2: float, refocus: float, te_ms: float, tr_ms: float) -> float:
    return pd * (1.0 - math.exp(-tr_ms / t1)) * math.exp(-te_ms / t2) * refocus


def compute_cockpit_signals(req: CockpitSignalRequest) -> CockpitSignalAnalysis:
    """Backend-owned GRE Ernst / TSE spin-echo signals + relative SAR. Frontend only renders."""
    is_gre = req.seq_type == "GRE"
    fa_rad = math.radians(req.fa_deg)
    refocus = math.sin(fa_rad) if is_gre else math.sin(fa_rad / 2.0) ** 2
    relative_sar = (
        1.0 * (req.fa_deg / 90.0) ** 2 * 0.4
        if is_gre
        else req.echo_train_length * (req.fa_deg / 180.0) ** 2 * 3.2
    )

    tissues: list[TissueIntensity] = []
    signals: dict[str, float] = {}
    for t in req.tissues:
        if is_gre:
            raw = _ernst_signal(t.pd, t.t1, t.t2s or t.t2, fa_rad, req.te_ms, req.tr_ms)
        else:
            raw = _tse_signal(t.pd, t.t1, t.t2, refocus, req.te_ms, req.tr_ms)
        intensity = max(0.02, min(1.0, raw))
        tissues.append(TissueIntensity(id=t.id, name=t.name, intensity=round(intensity, 6)))
        signals[t.id] = round(intensity, 6)

    delta = abs(tissues[0].intensity - (tissues[1].intensity if len(tissues) > 1 else 0.2)) if tissues else 0.0
    return CockpitSignalAnalysis(
        seq_type=req.seq_type,
        fa_deg=req.fa_deg,
        te_ms=req.te_ms,
        tr_ms=req.tr_ms,
        is_gre=is_gre,
        refocus_eff=round(refocus, 6),
        relative_sar=round(relative_sar, 4),
        delta_signal=round(delta, 6),
        cnr_proxy=round(delta * 20.0, 4),
        tissues=tissues,
        signals=signals,
    )


def compute_cockpit_signals_dict(req: CockpitSignalRequest) -> dict[str, Any]:
    return compute_cockpit_signals(req).model_dump(mode="json")
