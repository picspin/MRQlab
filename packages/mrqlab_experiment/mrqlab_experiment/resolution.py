from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .capabilities import EngineValidity
from .clinical import ParameterState
from .models import ExperimentGraph, TemplateRef


class FrozenDict(dict):
    def _immutable(self, *args, **kwargs):
        raise TypeError("resolved mappings are immutable")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _immutable


def _deep_freeze(value):
    if isinstance(value, dict):
        return FrozenDict({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    return value


class ResolvedExecutionPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    schema_version: Literal["2.0"] = "2.0"
    experiment_id: str
    clinical_recipe_id: str | None = None
    experiment_snapshot: FrozenDict
    fingerprint: str = ""
    representation: str
    engine: str
    validity: EngineValidity = Field(default_factory=EngineValidity)
    required_capabilities: tuple[str, ...]
    preferred: str | None
    requested_observations: tuple[str, ...] = ()
    parameters: tuple[ParameterState, ...] = ()
    scanner_profile: str | None = None
    tissue_prior_set: str | None = None
    approximations: tuple[str, ...] = ()
    differentiable: bool = False
    cost_estimate: float = 0.0
    physics_status: FrozenDict = Field(default_factory=FrozenDict)
    stale_dependencies: FrozenDict = Field(default_factory=FrozenDict)
    options: FrozenDict = Field(default_factory=FrozenDict)
    reasons: tuple[str, ...] = ()

    @field_validator(
        "experiment_snapshot", "physics_status", "stale_dependencies", "options", mode="before"
    )
    @classmethod
    def freeze_mappings(cls, value):
        return _deep_freeze(value)


_UNITS = {
    "te": "s",
    "tr": "s",
    "echoes": "count",
    "echo_count": "count",
    "flip_angle": "deg",
    "refocusing_flip_angle": "deg",
    "b0_t": "T",
    "max_gradient_mt_m": "mT/m",
    "max_slew_rate_t_m_s": "T/m/s",
    "adc_bandwidth_hz": "Hz",
    "matrix": "pixel",
    "max_work": "work_unit",
}


def resolve_parameter_states(graph: ExperimentGraph, sequence) -> tuple[ParameterState, ...]:
    authored = graph.sequence.params if isinstance(graph.sequence, TemplateRef) else {}
    derived = {
        key: value
        for key, value in sequence.metadata.items()
        if key in _UNITS and isinstance(value, (int, float, str, bool))
    }
    values = {**derived, **authored}
    states = [
        ParameterState(
            name=name,
            value=value,
            unit=_UNITS[name],
            state="authored" if name in authored else "derived",
            source="ExperimentGraph.sequence.params" if name in authored else "sequence compiler",
        )
        for name, value in sorted(values.items())
        if name in _UNITS
    ]
    scanner = graph.effective_scanner
    states.extend(
        (
            ParameterState(
                name="b0_t",
                value=scanner.b0_t,
                unit="T",
                state="scanner_default",
                source="ExperimentGraph.effective_scanner",
            ),
            ParameterState(
                name="max_gradient_mt_m",
                value=scanner.max_gradient_mt_m,
                unit="mT/m",
                state="scanner_default",
                source="ExperimentGraph.effective_scanner",
            ),
            ParameterState(
                name="max_slew_rate_t_m_s",
                value=scanner.max_slew_rate_t_m_s,
                unit="T/m/s",
                state="scanner_default",
                source="ExperimentGraph.effective_scanner",
            ),
            ParameterState(
                name="adc_bandwidth_hz",
                value=scanner.adc_bandwidth_hz,
                unit="Hz",
                state="scanner_default",
                source="ExperimentGraph.effective_scanner",
            ),
            ParameterState(
                name="matrix",
                value=graph.constraints.matrix,
                unit="pixel",
                state="authored",
                source="ExperimentGraph.constraints",
            ),
            ParameterState(
                name="max_work",
                value=graph.constraints.max_work,
                unit="work_unit",
                state="authored",
                source="ExperimentGraph.constraints",
            ),
        )
    )
    return tuple(sorted(states, key=lambda item: item.name))


def fingerprint_resolved_plan(plan: ResolvedExecutionPlan) -> str:
    payload = plan.model_dump(mode="json", exclude={"fingerprint"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
