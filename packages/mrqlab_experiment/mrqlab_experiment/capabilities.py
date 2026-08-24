from dataclasses import dataclass
from typing import Literal

Capability = str


@dataclass(frozen=True, slots=True)
class EngineValidity:
    spatial_encoding: Literal["none", "limited", "full"] = "none"
    shaped_rf: Literal["unsupported", "approximate", "exact"] = "unsupported"
    flow: Literal["unsupported", "approximate", "exact"] = "unsupported"
    exchange: Literal["unsupported", "multi_pool"] = "unsupported"
    diffusion: Literal["unsupported", "isotropic", "anisotropic"] = "unsupported"
    differentiable: bool = False
    steady_state: Literal["unsupported", "supported"] = "unsupported"


@dataclass(frozen=True, slots=True)
class StateRepresentation:
    name: str
    supports: frozenset[Capability]
    available: bool
    explanation: str
    validity: EngineValidity = EngineValidity()


class CapabilityMismatch(ValueError):
    pass


REPRESENTATIONS = {
    "bloch": StateRepresentation(
        "bloch",
        frozenset({"hard_rf", "off_resonance", "spatial_encoding", "magnetization_states"}),
        True,
        "Cartesian magnetization for spatial and off-resonance evolution",
        validity=EngineValidity(
            spatial_encoding="full",
            shaped_rf="exact",
            flow="unsupported",
            exchange="unsupported",
            diffusion="unsupported",
            differentiable=False,
            steady_state="supported",
        ),
    ),
    "epg": StateRepresentation(
        "epg",
        frozenset({"hard_rf", "configuration_states", "steady_state"}),
        True,
        "Classic single-pool configuration states for echo trains",
        validity=EngineValidity(
            spatial_encoding="limited",
            shaped_rf="unsupported",
            flow="approximate",
            exchange="unsupported",
            diffusion="unsupported",
            differentiable=False,
            steady_state="supported",
        ),
    ),
    "spectral": StateRepresentation(
        "spectral",
        frozenset({"hard_rf", "off_resonance", "multi_pool", "magnetization_states"}),
        True,
        "Independent chemical-shift pools without exchange",
        validity=EngineValidity(
            spatial_encoding="limited",
            shaped_rf="approximate",
            flow="unsupported",
            exchange="unsupported",
            diffusion="unsupported",
            differentiable=False,
            steady_state="supported",
        ),
    ),
    "hybrid": StateRepresentation(
        "hybrid",
        frozenset({"hard_rf", "shaped_rf", "configuration_states", "spatial_encoding"}),
        True,
        "Hybrid composes Bloch RF spans with EPG evolution spans; it is not a new Experiment IR",
        validity=EngineValidity(
            spatial_encoding="limited",
            shaped_rf="exact",
            flow="unsupported",
            exchange="unsupported",
            diffusion="unsupported",
            differentiable=False,
            steady_state="supported",
        ),
    ),
    "ssepg": StateRepresentation(
        "ssepg",
        frozenset(
            {"hard_rf", "shaped_rf", "configuration_states", "spatial_encoding", "slice_selective"}
        ),
        True,
        "ssEPG is a dedicated compiler path for slice-selective shaped RF on a z-grid; it is not hybrid or PDG",
        validity=EngineValidity(
            spatial_encoding="limited",
            shaped_rf="exact",
            flow="unsupported",
            exchange="unsupported",
            diffusion="unsupported",
            differentiable=False,
            steady_state="supported",
        ),
    ),
    "pdg": StateRepresentation(
        "pdg",
        frozenset({"hard_rf", "configuration_states", "spatial_encoding", "off_resonance", "phase_distribution"}),
        True,
        "PDG is a dedicated pathway↔image compiler bridging EPG configuration states with spatial image formation via a phase-distribution grid",
        validity=EngineValidity(
            spatial_encoding="full",
            shaped_rf="approximate",
            flow="unsupported",
            exchange="unsupported",
            diffusion="unsupported",
            differentiable=False,
            steady_state="supported",
        ),
    ),
    "epg-x": StateRepresentation(
        "epg-x",
        frozenset({"hard_rf", "configuration_states", "exchange", "multi_pool"}),
        False,
        "EPG-X combines EPG state with exchange operators",
        validity=EngineValidity(
            spatial_encoding="limited",
            shaped_rf="unsupported",
            flow="unsupported",
            exchange="multi_pool",
            diffusion="unsupported",
            differentiable=False,
            steady_state="supported",
        ),
    ),
}


def select_representation(required: frozenset[str], preferred: str | None) -> StateRepresentation:
    pdg = REPRESENTATIONS["pdg"]
    if "phase_distribution" in required:
        if pdg.available and required <= pdg.supports:
            return pdg
        raise CapabilityMismatch(
            f"required capabilities {sorted(required)} are unavailable: {pdg.explanation}"
        )
    ssepg = REPRESENTATIONS["ssepg"]
    if "slice_selective" in required:
        if ssepg.available and required <= ssepg.supports:
            return ssepg
        raise CapabilityMismatch(
            f"required capabilities {sorted(required)} are unavailable: {ssepg.explanation}"
        )
    hybrid = REPRESENTATIONS["hybrid"]
    if (
        {"shaped_rf", "configuration_states"} <= required
        and hybrid.available
        and required <= hybrid.supports
    ):
        return hybrid
    candidates = (
        [REPRESENTATIONS[preferred]]
        if preferred in REPRESENTATIONS
        else list(REPRESENTATIONS.values())
    )
    matches = [item for item in candidates if item.available and required <= item.supports]
    if matches:
        return matches[0]
    future = [item for item in REPRESENTATIONS.values() if required <= item.supports]
    hint = future[0].explanation if future else f"no representation declares {sorted(required)}"
    raise CapabilityMismatch(f"required capabilities {sorted(required)} are unavailable: {hint}")
