from ..backends.bloch import BlochBackend
from ..base import EnginePlugin, SimulationEngine


def _state_width(phantom, scanner, options) -> int:
    return len(phantom.resolved_isochromats())


def _backend(phantom, scanner, options):
    return BlochBackend(phantom.resolved_isochromats(), scanner)


def _metadata(phantom, scanner, options):
    return {
        "n_isochromats": len(phantom.resolved_isochromats()),
        "assumptions": ["instantaneous RF", "dimensionless teaching gradients"],
    }


BLOCH_PLUGIN = EnginePlugin(
    name="bloch",
    description="Vectorized multi-isochromat Bloch simulation",
    state_width=_state_width,
    backend_factory=_backend,
    metadata_factory=_metadata,
    snapshot_field="magnetization",
)


class BlochEngine(SimulationEngine):
    name = "bloch"
    description = "Vectorized multi-isochromat Bloch simulation"

    def __init__(self):
        super().__init__(BLOCH_PLUGIN)
