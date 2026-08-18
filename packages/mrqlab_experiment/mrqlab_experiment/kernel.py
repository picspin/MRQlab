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
    cost_estimate: float = 0.0
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
    if graph.tissue is not None:
        tissues = graph.tissue if isinstance(graph.tissue, tuple) else (graph.tissue,)
        if len(tissues) == 1:
            t = tissues[0]
            return Phantom(
                t1=t.t1,
                t2=t.t2,
                proton_density=t.proton_density,
                off_resonance_hz=graph.sample.off_resonance_hz,
            )
        else:
            isochromats = tuple(
                Isochromat(
                    t1=t.t1,
                    t2=t.t2,
                    proton_density=t.proton_density,
                    off_resonance_hz=graph.sample.off_resonance_hz,
                )
                for t in tissues
            )
            return Phantom(
                t1=tissues[0].t1,
                t2=tissues[0].t2,
                proton_density=sum(t.proton_density for t in tissues) / len(tissues),
                isochromats=isochromats,
            )
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

    # Check tissue and physiology requirements
    if graph.tissue is not None:
        tissues = graph.tissue if isinstance(graph.tissue, tuple) else (graph.tissue,)
        for t in tissues:
            if t.exchange_rate_hz > 0 and selected.validity.exchange == "unsupported":
                raise CapabilityMismatch(f"Engine '{selected.name}' does not support exchange (validity.exchange = 'unsupported')")
            if abs(t.flow_velocity_mps) > 0 and selected.validity.flow == "unsupported":
                raise CapabilityMismatch(f"Engine '{selected.name}' does not support flow dynamics (validity.flow = 'unsupported')")
            if t.diffusion_adc_mm2_s is not None and t.diffusion_adc_mm2_s > 0 and selected.validity.diffusion == "unsupported":
                raise CapabilityMismatch(f"Engine '{selected.name}' does not support diffusion (validity.diffusion = 'unsupported')")

    if graph.physiology is not None:
        if len(graph.physiology.flow_waveform) > 0 and selected.validity.flow == "unsupported":
            raise CapabilityMismatch(f"Engine '{selected.name}' does not support flow waveforms (validity.flow = 'unsupported')")

    total_events = sum(len(ch.events) for ch in sequence.channels)
    cost_estimate = float(total_events * max(1, len(graph.readout.products)))

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
        cost_estimate=cost_estimate,
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
