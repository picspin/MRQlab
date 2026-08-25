from ..backends.epg_x import EpgXBackend
from ..base import EnginePlugin, SimulationEngine


def _state_width(phantom, scanner, options):
    rows = 4 if phantom.magnetization_transfer is not None else 6
    return rows * (2 * options.epg_kmax + 1)


def _backend(phantom, scanner, options, sequence):
    return EpgXBackend(phantom, options.epg_kmax)


def _metadata(phantom, scanner, options, sequence):
    if phantom.magnetization_transfer is not None:
        assumptions = [
            "free-plus-bound-pool EPG-X",
            "hard RF rotates only the free-pool triplet; bound Z is untouched",
            "magnetization_transfer_applied",
        ]
        rf_times = {event.time for event in sequence.channel("rf_amp")}
        if any(
            isinstance(event, dict)
            and event.get("duration_s", 0) > 0
            and event.get("offset_hz", 0) != 0
            and event.get("b1_ut", 0) > 0
            and any(abs(float(event.get("t", float("inf"))) - t) <= 1e-12 for t in rf_times)
            for event in sequence.metadata.get("rf_events", [])
        ):
            assumptions.append("super_lorentzian_saturation_applied")
    else:
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
    description="Two-pool Bloch-McConnell or free/bound MT extended phase graph",
    state_width=_state_width,
    backend_factory=_backend,
    metadata_factory=_metadata,
    snapshot_field="configurations",
    representation="epg-x",
    supports=frozenset({"hard_rf", "configuration_states", "exchange", "multi_pool"}),
)


class EpgXEngine(SimulationEngine):
    name = "epg-x"
    description = "Two-pool Bloch-McConnell or free/bound MT extended phase graph"
    available = True

    def __init__(self):
        super().__init__(EPG_X_PLUGIN)
