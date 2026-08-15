from dataclasses import dataclass

Capability = str


@dataclass(frozen=True, slots=True)
class StateRepresentation:
    name: str
    supports: frozenset[Capability]
    available: bool
    explanation: str


class CapabilityMismatch(ValueError):
    pass


REPRESENTATIONS = {
    "bloch": StateRepresentation(
        "bloch",
        frozenset({"hard_rf", "off_resonance", "spatial_encoding", "magnetization_states"}),
        True,
        "Cartesian magnetization for spatial and off-resonance evolution",
    ),
    "epg": StateRepresentation(
        "epg",
        frozenset({"hard_rf", "configuration_states", "steady_state"}),
        True,
        "Classic single-pool configuration states for echo trains",
    ),
    "spectral": StateRepresentation(
        "spectral",
        frozenset({"hard_rf", "off_resonance", "multi_pool", "magnetization_states"}),
        True,
        "Independent chemical-shift pools without exchange",
    ),
    "ssepg": StateRepresentation(
        "ssepg",
        frozenset({"hard_rf", "shaped_rf", "configuration_states", "spatial_encoding"}),
        False,
        "ssEPG is a dedicated future compiler path for slice-selective RF",
    ),
    "pdg": StateRepresentation(
        "pdg",
        frozenset({"hard_rf", "configuration_states", "spatial_encoding", "off_resonance"}),
        False,
        "PDG is an optional provider seam bridging pathways and image formation",
    ),
    "epg-x": StateRepresentation(
        "epg-x",
        frozenset({"hard_rf", "configuration_states", "exchange", "multi_pool"}),
        False,
        "EPG-X combines EPG state with exchange operators",
    ),
}


def select_representation(required: frozenset[str], preferred: str | None) -> StateRepresentation:
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
