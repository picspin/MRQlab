from pathlib import Path

import numpy as np
import pytest
from mrqlab_sequence import Channel, Event, SequenceIR

from mrqlab_experiment import build_preset, run_experiment
from mrqlab_physics import BlochMcConnellPools, EngineOptions, MagnetizationTransferPools, Phantom, ScannerModel
from mrqlab_physics.backends.epg_x import EpgXBackend
from mrqlab_physics.engines import EpgXEngine
from mrqlab_physics.kernel.scheduler import schedule
from mrqlab_physics.ops.super_lorentzian import (
    apply_super_lorentzian_saturation,
    super_lorentzian_absorption_rate,
    super_lorentzian_lineshape,
)
from mrqlab_physics.ops.types import RfOp


def _pools():
    return MagnetizationTransferPools(1, 0.1, 0.8, 1.5, 0.2, 2, 8, 12e-6)


def _sequence(metadata=None):
    return SequenceIR(
        name="MT saturation",
        duration=0.02,
        channels=[Channel(name="rf_amp", events=[Event(time=0, value=0)])],
        metadata=metadata or {},
    )


def test_lineshape_is_even_positive_and_decays_at_far_offsets():
    positive = super_lorentzian_lineshape(2000, 12e-6)
    assert positive > 0
    assert positive == pytest.approx(super_lorentzian_lineshape(-2000, 12e-6))
    values = [super_lorentzian_lineshape(offset, 12e-6) for offset in (2000, 5000, 10000, 20000)]
    assert values == sorted(values, reverse=True)


def test_absorption_rate_scales_with_b1_squared():
    rate = super_lorentzian_absorption_rate(4, 2000, 12e-6)
    assert super_lorentzian_absorption_rate(8, 2000, 12e-6) == pytest.approx(4 * rate)


def test_saturation_changes_only_bound_z_and_zero_offset_fails_closed():
    state = np.ones((4, 3), dtype=complex)
    apply_super_lorentzian_saturation(state, 0.01, 8, 2000, 12e-6)
    np.testing.assert_array_equal(state[:3], 1)
    assert np.all((state[3].real > 0) & (state[3].real < 1))
    with pytest.raises(ValueError, match="nonzero"):
        apply_super_lorentzian_saturation(state, 0.01, 8, 0, 12e-6)


def test_mt_sat_event_attenuates_zb_and_records_assumption():
    sequence = _sequence({"rf_events": [{"t": 0, "duration_s": 0.01, "offset_hz": 2000, "b1_ut": 8}]})
    result = EpgXEngine().simulate(sequence, Phantom(magnetization_transfer=_pools()), ScannerModel(), EngineOptions(epg_kmax=0))
    assert result.meta["engine"] == "epg-x"
    assert "super_lorentzian_saturation_applied" in result.meta["assumptions"]
    backend = EpgXBackend(Phantom(magnetization_transfer=_pools()), 0)
    rf = next(op for op in schedule(sequence, EngineOptions()) if isinstance(op, RfOp))
    backend.apply(rf)
    assert backend.omega[3, 0].real < _pools().pd_b


def test_instantaneous_hard_rf_leaves_bound_z_untouched():
    backend = EpgXBackend(Phantom(magnetization_transfer=_pools()), 0)
    before = backend.omega[3].copy()
    backend.apply(RfOp(0, np.pi / 2, 0))
    np.testing.assert_array_equal(backend.omega[3], before)


def test_scheduler_populates_declared_rf_fields_and_rejects_missing_b1():
    sequence = _sequence({"rf_events": [{"t": 0, "duration_s": 0.01, "offset_hz": 2000, "b1_ut": 8, "extra": True}]})
    rf = next(op for op in schedule(sequence, EngineOptions()) if isinstance(op, RfOp))
    assert (rf.duration_s, rf.offset_hz, rf.b1_ut) == (0.01, 2000, 8)
    bad = _sequence({"rf_events": [{"t": 0, "duration_s": 0.01, "offset_hz": 2000}]})
    with pytest.raises(ValueError, match="positive b1_ut"):
        schedule(bad, EngineOptions())


def test_default_tse_does_not_claim_super_lorentzian():
    run = run_experiment(build_preset("dark-blood-tse"))
    assert run.plan.engine == "epg"
    assert "super_lorentzian_saturation_applied" not in run.sim_result.meta["assumptions"]


def test_two_liquid_bm_ignores_declared_saturation():
    sequence = _sequence({"rf_events": [{"t": 0, "duration_s": 0.01, "offset_hz": 2000, "b1_ut": 8}]})
    pools = BlochMcConnellPools(1, 0.1, 0.8, 1.5, 0.1, 0.2, 2, 8)
    result = EpgXEngine().simulate(
        sequence, Phantom(bloch_mcconnell=pools), ScannerModel(), EngineOptions(epg_kmax=0)
    )
    assert "super_lorentzian_saturation_applied" not in result.meta["assumptions"]
    assert "bloch_mcconnell_exchange_applied" in result.meta["assumptions"]


def test_cest_imaging_and_mrs_remain_documented_closed():
    assert not Path("packages/physics/mrqlab_physics/ops/cest.py").exists()
    text = Path("docs/PHYSICS.md").read_text()
    assert "CEST imaging" in text
    assert "remain unavailable" in text
