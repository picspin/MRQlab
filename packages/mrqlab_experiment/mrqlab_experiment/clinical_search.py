"""Simulation-backed searches for existing SE/GRE/TSE research models.

Scores minimize the authored clinical objective vector. RF energy and duration
are teaching proxies per simulated repetition, not SAR certification or a full
scan-time prediction. Teaching gradients cannot be checked against mT/m limits.
"""
from __future__ import annotations

import math
from time import perf_counter
from typing import Iterable

from pydantic import BaseModel, ConfigDict

from .clinical import ParameterState
from .kernel import run_experiment
from .models import ExperimentGraph, TemplateRef
from .observations import build_result_graph


class SearchPoint(BaseModel):
    model_config = ConfigDict(frozen=True)
    parameters: dict[str, float]
    objective_loss: float
    repetition_duration_s: float
    rf_energy_relative: float
    elapsed_s: float
    plan_fingerprint: str
    engine: str
    experiment_hash: str
    resolved_parameters: tuple[ParameterState, ...]
    feasible: bool
    gradient_check: str = "unavailable: teaching gradient amplitudes have no physical units"
    safety_scope: str = "teaching RF energy and timing proxies; not hardware safety certification"


class ClinicalSearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    baseline: SearchPoint
    candidates: tuple[SearchPoint, ...]
    best: SearchPoint | None
    elapsed_s: float
    objective: dict
    baseline_parameters: dict[str, float | int]
    parameter_units: dict[str, str]
    selection: str = "minimum clinical vector loss among feasible simulated candidates"


def search_clinical_parameters(
    graph: ExperimentGraph,
    candidates: Iterable[dict[str, float]],
    *,
    max_rf_energy_relative: float,
    max_repetition_duration_s: float,
) -> ClinicalSearchResult:
    """Run baseline and each candidate; retain scores, timing and provenance.

    Inputs use seconds and degrees, just as TemplateRef does. No fallback to the
    closed-form optimizer is allowed. No feasible candidate yields best=None.
    The caller's graph is never mutated; the selected point can be replayed.
    """
    if not isinstance(graph.sequence, TemplateRef) or graph.sequence.template.upper() not in {"SE", "GRE", "TSE"}:
        raise ValueError("search requires an existing SE/GRE/TSE template")
    if graph.objective is None or graph.objective.kind != "clinical_vector" or graph.objective.clinical_vector is None or not graph.objective.clinical_vector.terms:
        raise ValueError("search requires a nonempty clinical objective vector")
    tissues = graph.tissue if isinstance(graph.tissue, tuple) else ((graph.tissue,) if graph.tissue else ())
    ids = [t.id for t in tissues]
    if len(ids) != len(set(ids)):
        raise ValueError("search requires unique tissue ids")
    if any(t.exchange_rate_hz or t.bound_pool or t.diffusion_adc_mm2_s or t.flow_velocity_mps for t in tissues):
        raise ValueError("independent tissue scoring does not support exchange, diffusion or flow")
    if any(term.target_tissue_id not in ids or term.reference_tissue_id not in ids for term in graph.objective.clinical_vector.terms):
        raise ValueError("objective references unknown tissue")
    for limit in (max_rf_energy_relative, max_repetition_duration_s):
        if not math.isfinite(limit) or limit <= 0:
            raise ValueError("search limits must be finite and positive")
    allowed = {"te": "s", "tr": "s", "flip_angle": "deg", "refocusing_flip_angle": "deg"}
    started = perf_counter()

    def evaluate(parameters):
        if set(parameters) - allowed.keys():
            raise ValueError("unsupported search parameter")
        if any(isinstance(v, bool) or not math.isfinite(v) for v in parameters.values()):
            raise ValueError("search parameters must be finite numbers")
        candidate = graph.model_copy(deep=True)
        candidate.sequence.params.update(parameters)
        candidate.readout = candidate.readout.model_copy(update={"products": ("signal", "tissue_contrast", "objective_score")})
        tick = perf_counter()
        run = run_experiment(candidate)
        observations = {o.id: o for o in build_result_graph(run).observations}
        loss = float(observations["objective_score"].data)
        energy = sum((float(e.value) / 180.0) ** 2 for ch in run.sequence.channels if ch.name == "rf_amp" for e in ch.events)
        if not math.isfinite(loss):
            raise ValueError("non-finite clinical objective")
        return SearchPoint(
            parameters=dict(parameters), objective_loss=loss,
            repetition_duration_s=run.sequence.duration, rf_energy_relative=energy,
            elapsed_s=perf_counter() - tick, plan_fingerprint=run.plan.fingerprint,
            engine=run.plan.engine,
            experiment_hash=observations["objective_score"].provenance.experiment_hash,
            resolved_parameters=run.plan.parameters,
            feasible=energy <= max_rf_energy_relative and run.sequence.duration <= max_repetition_duration_s,
        )

    baseline = evaluate({})
    points = tuple(evaluate(dict(p)) for p in candidates)
    if not points:
        raise ValueError("search requires at least one candidate")
    feasible = [p for p in (baseline, *points) if p.feasible]
    return ClinicalSearchResult(
        baseline=baseline, candidates=points,
        best=min(feasible, key=lambda p: p.objective_loss) if feasible else None,
        elapsed_s=perf_counter() - started,
        objective=graph.objective.clinical_vector.model_dump(mode="json"),
        baseline_parameters=dict(graph.sequence.params),
        parameter_units={k: allowed[k] for p in points for k in p.parameters},
    )
