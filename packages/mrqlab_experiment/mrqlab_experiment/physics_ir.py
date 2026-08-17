from typing import Any, Literal, Protocol

from pydantic import BaseModel

from mrqlab_physics import EngineOptions
from mrqlab_physics.kernel.scheduler import preflight_schedule, schedule
from mrqlab_physics.ops.types import AdcSample, GradInterval, Relax, RfOp, Shift
from mrqlab_sequence import SequenceIR


class PhysicsOperator(Protocol):
    t: float

    def apply(self, state: Any, event: Any, context: Any) -> Any: ...


OperatorKind = Literal["RF_ROTATION", "FREE_EVOLUTION", "EPG_SHIFT", "GRADIENT", "READOUT"]
SpanKind = Literal["Bloch", "EPG", "PDG", "ssEPG"]


class PhysicsOperatorRecord(BaseModel):
    kind: OperatorKind
    t: float
    parameters: dict[str, Any]


class CompilerSpan(BaseModel):
    kind: SpanKind
    start: int
    stop: int


class PhysicsIR(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    representation: str
    operators: tuple[PhysicsOperatorRecord, ...]
    compiler_spans: tuple[CompilerSpan, ...]


def _record(op) -> PhysicsOperatorRecord:
    if isinstance(op, RfOp):
        return PhysicsOperatorRecord(
            kind="RF_ROTATION",
            t=op.t,
            parameters={"alpha_rad": op.alpha_rad, "phase_rad": op.phase_rad},
        )
    if isinstance(op, Relax):
        return PhysicsOperatorRecord(kind="FREE_EVOLUTION", t=op.t, parameters={"dt": op.dt})
    if isinstance(op, Shift):
        return PhysicsOperatorRecord(
            kind="EPG_SHIFT",
            t=op.t,
            parameters={"dk": op.dk, "source": op.source},
        )
    if isinstance(op, GradInterval):
        return PhysicsOperatorRecord(
            kind="GRADIENT",
            t=op.t,
            parameters={"dt": op.dt, "gradient": op.gradient},
        )
    if isinstance(op, AdcSample):
        return PhysicsOperatorRecord(
            kind="READOUT",
            t=op.t,
            parameters={
                "nco_frequency_hz": op.nco_frequency_hz,
                "nco_phase_rad": op.nco_phase_rad,
            },
        )
    raise TypeError(f"unknown scheduled operator {type(op).__name__}")


_SPAN_BY_REPRESENTATION: dict[str, SpanKind] = {
    "bloch": "Bloch",
    "spectral": "Bloch",
    "epg": "EPG",
    "pdg": "PDG",
    "ssepg": "ssEPG",
}


def compile_physics_ir(sequence: SequenceIR, representation: str, options: EngineOptions) -> PhysicsIR:
    plan = preflight_schedule(sequence, options, max_operators=options.max_work)
    records = tuple(_record(op) for op in schedule(sequence, options, plan))
    span_name = _SPAN_BY_REPRESENTATION.get(representation)
    if span_name is None:
        raise ValueError(f"no compiler span for representation {representation!r}")
    return PhysicsIR(
        representation=representation,
        operators=records,
        compiler_spans=(CompilerSpan(kind=span_name, start=0, stop=len(records)),),
    )
