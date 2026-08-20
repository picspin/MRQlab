from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, Field


OptimizeMode = Literal["max_contrast", "balanced_sar", "min_sar"]


class OptimizeGoal(BaseModel):
    mode: OptimizeMode = "balanced_sar"
    max_sar_budget: float = Field(default=35.0, gt=0)
    min_cnr_proxy: float = Field(default=2.5, ge=0)
    target_t2_ms: float = Field(default=120.0, gt=0)
    reference_t2_ms: float = Field(default=80.0, gt=0)
    echo_train_length: int = Field(default=16, ge=1)
    current_fa_deg: float = Field(default=150.0, gt=0)
    current_te_ms: float = Field(default=100.0, gt=0)


class ParetoPoint(BaseModel):
    flip_angle: float
    te_eff: float
    contrast: float
    cnr_proxy: float
    relative_sar: float
    score: float
    is_feasible: bool
    is_dominated: bool = False
    label: str | None = None


class SensitivityGradient(BaseModel):
    parameter: str
    d_cnr: float
    d_sar: float


class OptimizeAnalysis(BaseModel):
    pareto_frontier: list[ParetoPoint]
    candidates: list[ParetoPoint]
    optimal_candidate: ParetoPoint
    sensitivities: list[SensitivityGradient]
    grid_size: int


def evaluate_tse_point(
    fa_deg: float,
    te_ms: float,
    *,
    target_t2_ms: float,
    reference_t2_ms: float,
    echo_train_length: int,
) -> tuple[float, float, float]:
    """Closed-form TSE contrast / CNR proxy / relative SAR. Backend-owned."""
    fa_rad = math.radians(fa_deg)
    refocus = math.sin(fa_rad / 2.0) ** 2
    sig_target = refocus * math.exp(-te_ms / target_t2_ms)
    sig_ref = refocus * math.exp(-te_ms / reference_t2_ms)
    contrast = max(0.0, sig_target - sig_ref)
    cnr_proxy = contrast * 20.0
    relative_sar = echo_train_length * (fa_deg / 180.0) ** 2 * 3.2
    return contrast, cnr_proxy, relative_sar


def _score(mode: OptimizeMode, cnr: float, sar: float, budget: float) -> float:
    penalty = 100.0 if sar > budget else 0.0
    if mode == "max_contrast":
        return cnr * 10.0 - penalty
    if mode == "balanced_sar":
        return cnr * 5.0 - sar * 0.4 - penalty
    return -sar * 2.0 + cnr * 2.0 - penalty


def _non_dominated(points: list[ParetoPoint]) -> list[ParetoPoint]:
    """Maximize CNR, minimize SAR. A point is dominated if another is ≥CNR and ≤SAR, strictly better in one."""
    frontier: list[ParetoPoint] = []
    for p in points:
        dominated = False
        for q in points:
            if q is p:
                continue
            if q.cnr_proxy >= p.cnr_proxy and q.relative_sar <= p.relative_sar:
                if q.cnr_proxy > p.cnr_proxy or q.relative_sar < p.relative_sar:
                    dominated = True
                    break
        p.is_dominated = dominated
        if not dominated:
            frontier.append(p)
    frontier.sort(key=lambda x: x.relative_sar)
    return frontier


def compute_pareto(goal: OptimizeGoal) -> OptimizeAnalysis:
    fa_values = [100, 110, 120, 130, 140, 150, 160, 170, 180]
    te_values = [60, 70, 80, 90, 100, 110, 120]
    points: list[ParetoPoint] = []

    for fa in fa_values:
        for te in te_values:
            contrast, cnr, sar = evaluate_tse_point(
                fa,
                te,
                target_t2_ms=goal.target_t2_ms,
                reference_t2_ms=goal.reference_t2_ms,
                echo_train_length=goal.echo_train_length,
            )
            feasible = sar <= goal.max_sar_budget and cnr >= goal.min_cnr_proxy
            points.append(
                ParetoPoint(
                    flip_angle=fa,
                    te_eff=te,
                    contrast=round(contrast, 3),
                    cnr_proxy=round(cnr, 2),
                    relative_sar=round(sar, 1),
                    score=round(_score(goal.mode, cnr, sar, goal.max_sar_budget), 2),
                    is_feasible=feasible,
                )
            )

    feasible = [p for p in points if p.is_feasible]
    pool = feasible or points
    optimal = max(pool, key=lambda p: p.score)
    optimal.label = "optimal"
    # Frontier is the non-dominated set of the full grid (CNR↑, SAR↓).
    # Feasibility is a separate overlay so the trade-off curve stays visible
    # even when the SAR/CNR box is tight.
    frontier = _non_dominated(points)

    d_fa = 5.0
    d_te = 10.0
    _, cnr0, sar0 = evaluate_tse_point(
        goal.current_fa_deg,
        goal.current_te_ms,
        target_t2_ms=goal.target_t2_ms,
        reference_t2_ms=goal.reference_t2_ms,
        echo_train_length=goal.echo_train_length,
    )
    _, cnr_fa, sar_fa = evaluate_tse_point(
        goal.current_fa_deg + d_fa,
        goal.current_te_ms,
        target_t2_ms=goal.target_t2_ms,
        reference_t2_ms=goal.reference_t2_ms,
        echo_train_length=goal.echo_train_length,
    )
    _, cnr_te, sar_te = evaluate_tse_point(
        goal.current_fa_deg,
        goal.current_te_ms + d_te,
        target_t2_ms=goal.target_t2_ms,
        reference_t2_ms=goal.reference_t2_ms,
        echo_train_length=goal.echo_train_length,
    )

    return OptimizeAnalysis(
        pareto_frontier=frontier,
        candidates=points,
        optimal_candidate=optimal,
        sensitivities=[
            SensitivityGradient(
                parameter="Flip Angle",
                d_cnr=round((cnr_fa - cnr0) / d_fa, 4),
                d_sar=round((sar_fa - sar0) / d_fa, 4),
            ),
            SensitivityGradient(
                parameter="Effective TE",
                d_cnr=round((cnr_te - cnr0) / d_te, 4),
                d_sar=round((sar_te - sar0) / d_te, 4),
            ),
        ],
        grid_size=len(points),
    )


def compute_pareto_dict(goal: OptimizeGoal) -> dict[str, Any]:
    return compute_pareto(goal).model_dump(mode="json")
