from typing import Any, Literal

from pydantic import BaseModel, Field

DisturbanceKind = Literal[
    "thermal_noise",
    "b0_map",
    "b1_map",
    "gradient_delay",
    "eddy_current",
    "gradient_nonlinearity",
    "motion",
    "flow",
    "diffusion",
    "exchange",
    "susceptibility",
    "coil_sensitivity",
    "adc_imperfection",
    "slice_profile",
]


class Disturbance(BaseModel):
    id: str
    kind: DisturbanceKind
    domain: Literal["signal", "field", "scanner", "motion", "tissue", "sequence"]
    enabled: bool = True
    parameters: dict[str, Any] = Field(default_factory=dict)


class DisturbanceStack(BaseModel):
    items: tuple[Disturbance, ...] = ()


_REQUIREMENTS = {
    "slice_profile": (
        frozenset({"shaped_rf", "configuration_states", "slice_selective"}),
        "EPG → ssEPG",
    ),
    "exchange": (frozenset({"exchange", "multi_pool"}), "EPG → EPG-X / hybrid"),
    "b0_map": (frozenset({"spatial_encoding", "off_resonance", "phase_distribution"}), "EPG → PDG for spatial B0"),
}


def disturbance_requirements(stack: DisturbanceStack) -> tuple[frozenset[str], tuple[str, ...]]:
    required: set[str] = set()
    explanations: list[str] = []
    for item in stack.items:
        if item.enabled and item.kind in _REQUIREMENTS:
            capabilities, explanation = _REQUIREMENTS[item.kind]
            required.update(capabilities)
            explanations.append(explanation)
    return frozenset(required), tuple(explanations)


def stack_from_reality(value: int) -> DisturbanceStack:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        raise ValueError("reality must be an integer from 0 to 100")
    items = []
    if value >= 25:
        items.append(
            Disturbance(
                id="noise",
                kind="thermal_noise",
                domain="signal",
                parameters={"snr_db": 40.0},
            )
        )
    if value >= 50:
        items.append(
            Disturbance(id="b0", kind="b0_map", domain="field", parameters={"peak_hz": 20.0})
        )
    if value >= 75:
        items.append(
            Disturbance(
                id="motion",
                kind="motion",
                domain="motion",
                parameters={"translation_mm": 1.0},
            )
        )
    return DisturbanceStack(items=tuple(items))
