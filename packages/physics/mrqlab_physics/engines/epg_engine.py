from ..backends.epg import EPGBackend
from ..base import EnginePlugin, SimulationEngine


def _state_width(phantom, scanner, options) -> int:
    return 3 * (2 * options.epg_kmax + 1)


def _physical_context(sequence):
    units = sequence.metadata.get("gradient_units", "teaching")
    if units not in {"teaching", "mt_m"}:
        raise ValueError("gradient_units must be 'teaching' or 'mt_m'")
    fov = float(sequence.metadata.get("fov_m", 0.22))
    if not __import__("math").isfinite(fov) or fov <= 0:
        raise ValueError("fov_m must be finite and positive")
    return units, fov


def _backend(phantom, scanner, options, sequence):
    units, fov = _physical_context(sequence)
    return EPGBackend(phantom, options.epg_kmax, gradient_units=units, fov_m=fov)


def _metadata(phantom, scanner, options, sequence):
    assumptions = ["classic single-pool EPG", "metadata-first integer dk"]
    return {
        "available": True,
        "kmax": options.epg_kmax,
        "n_orders": 2 * options.epg_kmax + 1,
        "assumptions": assumptions,
    }


EPG_PLUGIN = EnginePlugin(
    name="epg",
    description="Classic bounded-order extended phase graph",
    state_width=_state_width,
    backend_factory=_backend,
    metadata_factory=_metadata,
    snapshot_field="configurations",
    representation="epg",
    supports=frozenset({"hard_rf", "configuration_states", "steady_state", "isotropic_diffusion"}),
)


class EPGEngine(SimulationEngine):
    name = "epg"
    description = "Classic bounded-order extended phase graph"
    available = True

    def __init__(self):
        super().__init__(EPG_PLUGIN)
