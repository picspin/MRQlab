from dataclasses import asdict, dataclass, replace
import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field

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

from .capabilities import CapabilityMismatch, EngineValidity, REPRESENTATIONS, select_representation
from .compiler import compile_sequence
from .disturbances import disturbance_requirements
from .models import ExperimentGraph
from .physics_ir import PhysicsIR, compile_physics_ir


class ValidationIssue(BaseModel):
    code: str
    message: str


class ValidationReport(BaseModel):
    valid: bool
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()


class ExecutionPlan(BaseModel):
    experiment_id: str
    fingerprint: str = ""
    representation: str
    engine: str
    validity: EngineValidity = Field(default_factory=EngineValidity)
    required_capabilities: tuple[str, ...]
    preferred: str | None
    requested_observations: tuple[str, ...] = ()
    approximations: tuple[str, ...] = ()
    differentiable: bool = False
    stale_dependencies: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    options: dict[str, Any]
    reasons: tuple[str, ...]



@dataclass(slots=True)
class KernelRun:
    experiment: ExperimentGraph
    sequence: SequenceIR
    sim_result: SimResult
    plan: ExecutionPlan
    physics_ir: PhysicsIR | None = None


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
    
    raw = graph.model_dump(mode="json")
    fingerprint = hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    approximations = ()
    if selected.name == "epg":
        approximations = ("hard_rf_isochromat_average", "discrete_echo_train")
    elif selected.name == "bloch":
        approximations = ("isochromat_sampling_grid",)

    stale_deps = {
        "sample": ("signal", "image", "magnetization", "configurations", "echo_train", "objective_score"),
        "scanner": ("signal", "image", "k_trajectory"),
        "sequence": ("signal", "image", "k_trajectory", "magnetization", "configurations", "echo_train", "sar", "objective_score"),
    }

    return ExecutionPlan(
        experiment_id=graph.id,
        fingerprint=fingerprint,
        representation=selected.name,
        engine=selected.name,
        validity=selected.validity,
        required_capabilities=tuple(sorted(required)),
        preferred=preferred,
        requested_observations=graph.readout.products,
        approximations=approximations,
        differentiable=selected.validity.differentiable,
        stale_dependencies=stale_deps,
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
    options = EngineOptions(**plan.options)
    physics_ir = compile_physics_ir(sequence, plan.representation, options)
    result = get_engine(plan.engine).simulate(
        sequence,
        _phantom_from_sample(graph),
        ScannerModel(**graph.scanner.model_dump()),
        options,
    )
    return KernelRun(graph.model_copy(deep=True), sequence, result, plan, physics_ir)
