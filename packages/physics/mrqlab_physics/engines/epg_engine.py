from ..backends.epg import EPGBackend
from ..base import EnginePlugin, SimulationEngine


def _state_width(phantom, scanner, options) -> int:
    return 3 * (2 * options.epg_kmax + 1)


def _backend(phantom, scanner, options):
    return EPGBackend(phantom, options.epg_kmax)


def _metadata(phantom, scanner, options):
    return {
        "available": True,
        "kmax": options.epg_kmax,
        "n_orders": 2 * options.epg_kmax + 1,
        "assumptions": ["classic single-pool EPG", "metadata-first integer dk"],
    }


EPG_PLUGIN = EnginePlugin(
    name="epg",
    description="Classic bounded-order extended phase graph",
    state_width=_state_width,
    backend_factory=_backend,
    metadata_factory=_metadata,
    snapshot_field="configurations",
    representation="epg",
    supports=frozenset({"hard_rf", "configuration_states", "steady_state"}),
)


class EPGEngine(SimulationEngine):
    name = "epg"
    description = "Classic bounded-order extended phase graph"
    available = True

    def __init__(self):
        super().__init__(EPG_PLUGIN)
