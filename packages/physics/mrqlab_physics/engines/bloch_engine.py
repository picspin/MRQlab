from ..backends.bloch import BlochBackend
from ..base import EnginePlugin, SimulationEngine


def _state_width(phantom, scanner, options) -> int:
    return len(phantom.resolved_isochromats())


def _backend(phantom, scanner, options, sequence):
    return BlochBackend(phantom.resolved_isochromats(), scanner, sequence.metadata.get("gradient_units", "teaching"))


def _metadata(phantom, scanner, options, sequence):
    units = sequence.metadata.get("gradient_units", "teaching")
    return {
        "n_isochromats": len(phantom.resolved_isochromats()),
        "assumptions": ["instantaneous RF", "dimensionless teaching gradients" if units == "teaching" else "physical mt_m gradients"],
    }


BLOCH_PLUGIN = EnginePlugin(
    name="bloch",
    description="Vectorized multi-isochromat Bloch simulation",
    state_width=_state_width,
    backend_factory=_backend,
    metadata_factory=_metadata,
    snapshot_field="magnetization",
    representation="bloch",
    supports=frozenset(
        {"hard_rf", "off_resonance", "spatial_encoding", "magnetization_states"}
    ),
)


class BlochEngine(SimulationEngine):
    name = "bloch"
    description = "Vectorized multi-isochromat Bloch simulation"

    def __init__(self):
        super().__init__(BLOCH_PLUGIN)
