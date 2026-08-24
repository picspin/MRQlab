from ..backends.epg_x import EpgXBackend
from ..base import EnginePlugin, SimulationEngine


def _state_width(phantom, scanner, options):
    return 6 * (2 * options.epg_kmax + 1)


def _backend(phantom, scanner, options, sequence):
    return EpgXBackend(phantom, options.epg_kmax)


def _metadata(phantom, scanner, options, sequence):
    assumptions = ["two-pool liquid EPG-X", "hard RF applied independently to both pools"]
    if phantom.bloch_mcconnell and phantom.bloch_mcconnell.k_ab_hz > 0:
        assumptions.append("bloch_mcconnell_exchange_applied")
    return {
        "available": True,
        "kmax": options.epg_kmax,
        "n_orders": 2 * options.epg_kmax + 1,
        "assumptions": assumptions,
    }


EPG_X_PLUGIN = EnginePlugin(
    name="epg-x",
    description="Two-liquid-pool Bloch-McConnell extended phase graph",
    state_width=_state_width,
    backend_factory=_backend,
    metadata_factory=_metadata,
    snapshot_field="configurations",
    representation="epg-x",
    supports=frozenset({"hard_rf", "configuration_states", "exchange", "multi_pool"}),
)


class EpgXEngine(SimulationEngine):
    name = "epg-x"
    description = "Two-liquid-pool Bloch-McConnell extended phase graph"
    available = True

    def __init__(self):
        super().__init__(EPG_X_PLUGIN)
