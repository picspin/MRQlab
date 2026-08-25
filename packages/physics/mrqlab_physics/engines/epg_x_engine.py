import numpy as np

from ..backends.epg_x import EpgXBackend
from ..base import EnginePlugin, SimulationEngine
from ..kernel.units import GAMMA_BAR_HZ_T
from ..models import SimResult
from ..ops.types import Relax, SaturationOp


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

    def simulate(self, sequence, phantom, scanner, options):
        cest = sequence.metadata.get("cest")
        if cest is None:
            return super().simulate(sequence, phantom, scanner, options)
        if phantom.bloch_mcconnell is None or phantom.magnetization_transfer is not None:
            raise ValueError("CEST requires exactly two liquid Bloch-McConnell pools")
        required = ("offsets_ppm", "offset_unit", "saturation_duration_s", "saturation_power_uT")
        if any(key not in cest for key in required):
            raise ValueError("CEST metadata requires offsets_ppm, offset_unit, duration, and power")
        if cest["offset_unit"] != "ppm":
            raise ValueError("CEST offsets must declare offset_unit='ppm'")
        offsets = np.asarray(cest["offsets_ppm"], dtype=float)
        duration, power = float(cest["saturation_duration_s"]), float(cest["saturation_power_uT"])
        if offsets.ndim != 1 or not offsets.size or not np.all(np.isfinite(offsets)):
            raise ValueError("CEST offsets_ppm must be a non-empty finite list")
        if not np.isfinite(duration) or duration <= 0 or not np.isfinite(power) or power <= 0:
            raise ValueError("CEST saturation duration and power must be finite and positive")
        if cest.get("reference", "unsaturated_control") != "unsaturated_control":
            raise ValueError("v0.64 CEST supports only unsaturated_control reference")
        order = np.argsort(offsets)
        offsets = offsets[order]
        offset_hz = offsets * GAMMA_BAR_HZ_T * scanner.b0_t * 1e-6
        mz = []
        for hz in offset_hz:
            backend = EpgXBackend(phantom, 0)
            backend.apply(SaturationOp(0.0, duration, float(hz), power))
            mz.append(float(np.real(backend.omega[2, 0])))
        control = EpgXBackend(phantom, 0)
        control.apply(Relax(0.0, duration))
        mz_ref = float(np.real(control.omega[2, 0]))
        if not np.isfinite(mz_ref) or mz_ref <= 0:
            raise ValueError("unsaturated CEST control Mz_ref must be finite and positive")
        z = np.clip(np.asarray(mz) / mz_ref, 0.0, 1.0 + 1e-9)
        assumptions = [
            "two-pool liquid EPG-X", "bloch-mcconnell", "single_voxel",
            "cest_z_spectrum_applied", "unsaturated_control",
        ]
        return SimResult(
            signal=np.array([], dtype=complex), k_trajectory=np.empty((0, 3)),
            z_spectrum={"offset_ppm": offsets, "offset_hz": offset_hz, "Z": z,
                        "Mz_sat": np.asarray(mz), "Mz_ref": np.asarray([mz_ref])},
            meta={"engine": "epg-x", "assumptions": assumptions, "n_ops": len(offsets) + 1,
                  "estimated_work": (len(offsets) + 1) * 7},
            timing={},
        )
