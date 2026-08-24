from ..backends.spectral import SpectralBackend, spectral_state_width
from ..base import EnginePlugin, SimulationEngine


def _state_width(phantom, scanner, options) -> int:
    return spectral_state_width(phantom)


def _backend(phantom, scanner, options, sequence):
    return SpectralBackend(phantom, scanner)


def _metadata(phantom, scanner, options, sequence):
    return {
        "available": True,
        "model": "independent chemical-shift pools",
        "pools": [pool.name for pool in phantom.pools],
        "n_isochromats": spectral_state_width(phantom),
        "assumptions": [
            "no exchange",
            "instantaneous RF",
            "Lorentzian relaxation only",
        ],
    }


SPECTRAL_PLUGIN = EnginePlugin(
    name="spectral",
    description="Independent fat/water chemical-shift pools",
    state_width=_state_width,
    backend_factory=_backend,
    metadata_factory=_metadata,
    snapshot_field="magnetization",
    representation="spectral",
    supports=frozenset(
        {"hard_rf", "off_resonance", "multi_pool", "magnetization_states"}
    ),
)


class SpectralEngine(SimulationEngine):
    name = "spectral"
    description = "Independent fat/water chemical-shift pools"
    available = True

    def __init__(self):
        super().__init__(SPECTRAL_PLUGIN)
