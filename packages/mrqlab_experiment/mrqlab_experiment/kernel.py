from dataclasses import dataclass, replace

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

from .capabilities import CapabilityMismatch, select_representation
from .compiler import compile_sequence
from .models import ExperimentGraph


class ValidationIssue(BaseModel):
    code: str
    message: str


class ValidationReport(BaseModel):
    valid: bool
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()


@dataclass(slots=True)
class KernelRun:
    experiment: ExperimentGraph
    sequence: SequenceIR
    sim_result: SimResult


def _phantom_from_sample(graph: ExperimentGraph) -> Phantom:
    sample = graph.sample.model_dump()
    isochromats = tuple(Isochromat(**item) for item in sample.pop("isochromats", ()))
    pools = tuple(SpectralPool(**item) for item in sample.pop("pools", ()))
    return Phantom(**sample, isochromats=isochromats, pools=pools)


def validate_experiment(graph: ExperimentGraph) -> ValidationReport:
    try:
        compile_sequence(graph)
    except ValueError as exc:
        code = "unsupported_node" if "reserved node kind" in str(exc) else "invalid_graph"
        return ValidationReport(valid=False, errors=(ValidationIssue(code=code, message=str(exc)),))
    try:
        select_representation(graph.engine.required_capabilities, graph.engine.preferred)
    except CapabilityMismatch as exc:
        return ValidationReport(
            valid=False,
            errors=(ValidationIssue(code="capability_mismatch", message=str(exc)),),
        )
    return ValidationReport(valid=True)


def run_experiment(graph: ExperimentGraph) -> KernelRun:
    report = validate_experiment(graph)
    if not report.valid:
        raise ValueError(report.errors[0].message)
    sequence = compile_sequence(graph)
    requested = EngineOptions(**graph.engine.options)
    options = replace(requested, max_work=min(requested.max_work, graph.constraints.max_work))
    engine_name = graph.engine.preferred or str(sequence.metadata.get("preferred_engine", "bloch"))
    result = get_engine(engine_name).simulate(
        sequence,
        _phantom_from_sample(graph),
        ScannerModel(**graph.scanner.model_dump()),
        options,
    )
    return KernelRun(graph, sequence, result)
