from dataclasses import asdict, dataclass, replace
import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field

from mrqlab_physics import (
    BlochMcConnellPools,
    EngineOptions,
    Isochromat,
    MagnetizationTransferPools,
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
    physics_status: dict[str, str] = Field(default_factory=dict)
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
                diffusion_adc_mm2_s=t.diffusion_adc_mm2_s,
            )
        else:
            if len(tissues) == 2 and tissues[0].exchange_rate_hz > 0:
                a, b = tissues
                k_ba = a.exchange_rate_hz * a.pool_fraction / b.pool_fraction
                pool_model = (
                    MagnetizationTransferPools(
                        a.t1, a.t2, a.proton_density, b.t1, b.proton_density,
                        a.exchange_rate_hz, k_ba,
                    )
                    if b.bound_pool else
                    BlochMcConnellPools(
                        a.t1, a.t2, a.proton_density, b.t1, b.t2, b.proton_density,
                        a.exchange_rate_hz, k_ba,
                    )
                )
                return Phantom(
                    t1=a.t1, t2=a.t2, proton_density=a.proton_density,
                    off_resonance_hz=graph.sample.off_resonance_hz,
                    magnetization_transfer=pool_model if b.bound_pool else None,
                    bloch_mcconnell=pool_model if not b.bound_pool else None,
                )
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
    adc_values = (
        [t.diffusion_adc_mm2_s for t in (graph.tissue if isinstance(graph.tissue, tuple) else (graph.tissue,))]
        if graph.tissue is not None else []
    )
    if any(value is not None and value > 0 for value in adc_values) and sequence.metadata.get("gradient_units", "teaching") != "mt_m":
        raise CapabilityMismatch("diffusion requires SequenceIR metadata gradient_units='mt_m'")
    extra, explanations = disturbance_requirements(graph.disturbances)
    tissue_values = graph.tissue if isinstance(graph.tissue, tuple) else ((graph.tissue,) if graph.tissue is not None else ())
    exchange_declared = bool(tissue_values and tissue_values[0].exchange_rate_hz > 0)
    if tissue_values and tissue_values[0].bound_pool:
        raise CapabilityMismatch("pool a must be the free pool")
    if len(tissue_values) >= 2 and tissue_values[1].bound_pool and not exchange_declared:
        raise CapabilityMismatch("a bound pool requires positive exchange_rate_hz on pool a")
    if exchange_declared:
        if len(tissue_values) != 2:
            raise CapabilityMismatch("positive exchange_rate_hz requires exactly two tissues")
        a, b = tissue_values
        if a.pool_fraction <= 0 or b.pool_fraction <= 0:
            raise CapabilityMismatch("two-pool fractions must be positive")
        if abs(a.pool_fraction + b.pool_fraction - 1.0) > 1e-9:
            raise CapabilityMismatch("two-pool fractions must sum to 1")
        if b.exchange_rate_hz > 0:
            raise CapabilityMismatch("exchange_rate_hz is declared only on pool a")
        extra = frozenset(extra | {"exchange", "multi_pool"})
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
    if (
        "exchange" in required
        and graph.engine.preferred is not None
        and graph.engine.preferred != "epg-x"
    ):
        raise CapabilityMismatch(
            f"forced representation {graph.engine.preferred!r} cannot satisfy exchange"
        )
    if (
        "slice_selective" in required
        and graph.engine.preferred is not None
        and graph.engine.preferred != "ssepg"
    ):
        raise CapabilityMismatch(
            f"forced representation {graph.engine.preferred!r} cannot satisfy slice_selective"
        )
    if (
        "phase_distribution" in required
        and graph.engine.preferred is not None
        and graph.engine.preferred != "pdg"
    ):
        raise CapabilityMismatch(
            f"forced representation {graph.engine.preferred!r} cannot satisfy phase_distribution"
        )
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

    physics_status = {}
    if graph.tissue is not None:
        tissues = graph.tissue if isinstance(graph.tissue, tuple) else (graph.tissue,)
        for t in tissues:
            if t.exchange_rate_hz > 0:
                if selected.validity.exchange == "unsupported":
                    raise CapabilityMismatch(f"Engine '{selected.name}' does not support exchange (validity.exchange = 'unsupported')")
                physics_status["exchange"] = f"declared_{selected.validity.exchange}_in_{selected.name}"
            if abs(t.flow_velocity_mps) > 0:
                if selected.validity.flow == "unsupported":
                    raise CapabilityMismatch(f"Engine '{selected.name}' does not support flow dynamics (validity.flow = 'unsupported')")
                physics_status["flow"] = f"declared_{selected.validity.flow}_in_{selected.name}"
            if t.diffusion_adc_mm2_s is not None and t.diffusion_adc_mm2_s > 0:
                if selected.validity.diffusion == "unsupported":
                    raise CapabilityMismatch(f"Engine '{selected.name}' does not support diffusion (validity.diffusion = 'unsupported')")
                physics_status["diffusion"] = f"declared_{selected.validity.diffusion}_in_{selected.name}"

    if graph.physiology is not None:
        if len(graph.physiology.flow_waveform) > 0:
            if selected.validity.flow == "unsupported":
                raise CapabilityMismatch(f"Engine '{selected.name}' does not support flow waveforms (validity.flow = 'unsupported')")
            physics_status["flow_waveform"] = f"declared_{selected.validity.flow}_in_{selected.name}"

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
        physics_status=physics_status,
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
    if plan.representation == "ssepg":
        slice_disturbance = next(
            (item for item in graph.disturbances.items if item.enabled and item.kind == "slice_profile"),
            None,
        )
        if slice_disturbance is None:
            raise CapabilityMismatch("ssepg requires an enabled slice_profile disturbance")
        sequence.metadata["ssepg"] = dict(slice_disturbance.parameters)
    if plan.representation == "pdg":
        b0_disturbance = next(
            (item for item in graph.disturbances.items if item.enabled and item.kind == "b0_map"),
            None,
        )
        if b0_disturbance is None:
            raise CapabilityMismatch("pdg requires an enabled b0_map disturbance")
        sequence.metadata["pdg"] = dict(b0_disturbance.parameters)
    options = EngineOptions(**plan.options)
    physics_ir = compile_physics_ir(sequence, plan.representation, options)
    scanner_model = graph.effective_scanner
    try:
        engine = get_engine(plan.representation if plan.representation in {"hybrid", "ssepg", "pdg", "epg-x"} else plan.engine)
        result = engine.simulate(
            sequence,
            _phantom_from_sample(graph),
            scanner_model,
            options,
        )
    except (RuntimeError, NotImplementedError, ValueError) as exc:
        if plan.representation not in {"hybrid", "ssepg", "pdg"}:
            raise
        raise CapabilityMismatch(f"{plan.representation} engine handoff unavailable: {exc}") from exc
    return KernelRun(graph.model_copy(deep=True), sequence, result, plan, physics_ir)
