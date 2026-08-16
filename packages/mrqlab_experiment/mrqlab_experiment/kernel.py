from dataclasses import asdict, dataclass, replace
from typing import Any

from pydantic import BaseModel

from mrqlab_physics import (
    EngineOptions,
    Isochromat,
    Phantom,
    ScannerModel,
    SimResult,
    SpectralPool,
    get_engine,
)
from mrqlab_sequence import SequenceIR

from .capabilities import CapabilityMismatch, REPRESENTATIONS, select_representation
from .compiler import compile_sequence
from .disturbances import disturbance_requirements
from .models import ExperimentGraph


class ValidationIssue(BaseModel):
    code: str
    message: str


class ValidationReport(BaseModel):
    valid: bool
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()


class ExecutionPlan(BaseModel):
    experiment_id: str
    representation: str
    engine: str
    required_capabilities: tuple[str, ...]
    preferred: str | None
    options: dict[str, Any]
    reasons: tuple[str, ...]


@dataclass(slots=True)
class KernelRun:
    experiment: ExperimentGraph
    sequence: SequenceIR
    sim_result: SimResult
    plan: ExecutionPlan


def _phantom_from_sample(graph: ExperimentGraph) -> Phantom:
    sample = graph.sample.model_dump()
    isochromats = tuple(Isochromat(**item) for item in sample.pop("isochromats", ()))
    pools = tuple(SpectralPool(**item) for item in sample.pop("pools", ()))
    return Phantom(**sample, isochromats=isochromats, pools=pools)


def plan_experiment(graph: ExperimentGraph) -> ExecutionPlan:
    sequence = compile_sequence(graph)
    extra, explanations = disturbance_requirements(graph.disturbances)
    required = frozenset(graph.engine.required_capabilities | extra)
    if graph.engine.preferred is not None:
        preferred = graph.engine.preferred
        source = "preferred"
    elif sequence.metadata.get("preferred_engine") is not None:
        preferred = str(sequence.metadata["preferred_engine"])
        source = "metadata"
    else:
        preferred = None
        source = "capability"
    if preferred is not None and preferred not in REPRESENTATIONS:
        get_engine(preferred)
    selected = select_representation(required, preferred)
    requested = EngineOptions(**graph.engine.options)
    options = replace(requested, max_work=min(requested.max_work, graph.constraints.max_work))
    return ExecutionPlan(
        experiment_id=graph.id,
        representation=selected.name,
        engine=selected.name,
        required_capabilities=tuple(sorted(required)),
        preferred=preferred,
        options=asdict(options),
        reasons=(*explanations, source),
    )


def validate_experiment(graph: ExperimentGraph) -> ValidationReport:
    try:
        plan_experiment(graph)
    except CapabilityMismatch as exc:
        _extra, explanations = disturbance_requirements(graph.disturbances)
        if explanations:
            return ValidationReport(
                valid=False,
                errors=(
                    ValidationIssue(
                        code="unavailable_representation",
                        message="; ".join(explanations),
                    ),
                ),
            )
        return ValidationReport(
            valid=False,
            errors=(ValidationIssue(code="capability_mismatch", message=str(exc)),),
        )
    except ValueError as exc:
        code = "unsupported_node" if "reserved node kind" in str(exc) else "invalid_graph"
        return ValidationReport(valid=False, errors=(ValidationIssue(code=code, message=str(exc)),))
    return ValidationReport(valid=True)


def run_experiment(graph: ExperimentGraph) -> KernelRun:
    report = validate_experiment(graph)
    if not report.valid:
        raise ValueError(report.errors[0].message)
    plan = plan_experiment(graph)
    sequence = compile_sequence(graph)
    result = get_engine(plan.engine).simulate(
        sequence,
        _phantom_from_sample(graph),
        ScannerModel(**graph.scanner.model_dump()),
        EngineOptions(**plan.options),
    )
    return KernelRun(graph, sequence, result, plan)
