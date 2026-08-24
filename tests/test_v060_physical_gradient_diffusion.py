import numpy as np
import pytest

from mrqlab_experiment import build_preset, plan_experiment, run_experiment, TissueModel, validate_experiment
from mrqlab_experiment.capabilities import REPRESENTATIONS
from mrqlab_physics import EPGEngine, EngineOptions, Phantom, ScannerModel
from mrqlab_physics import BlochMcConnellPools
from mrqlab_physics.backends.epg_x import apply_bloch_mcconnell
from mrqlab_sequence import build_sequence


def _physical_tse():
    sequence = build_sequence("TSE", {})
    sequence.metadata.update(gradient_units="mt_m", fov_m=0.22)
    for channel in sequence.channels:
        if channel.name in {"gx", "gy", "gz"}:
            for event in channel.events:
                if event.value:
                    event.value = 20.0 if event.value > 0 else -20.0
    return sequence


def test_default_tse_remains_teaching_epg_without_diffusion():
    graph = build_preset("dark-blood-tse")
    assert plan_experiment(graph).engine == "epg"
    run = run_experiment(graph)
    assert run.sequence.metadata.get("gradient_units", "teaching") == "teaching"
    assert "isotropic_diffusion_applied" not in run.sim_result.meta["assumptions"]


def test_adc_with_teaching_units_fails_closed():
    graph = build_preset("dark-blood-tse")
    graph.tissue = TissueModel(diffusion_adc_mm2_s=0.8e-3)
    assert not validate_experiment(graph).valid
    with pytest.raises(ValueError, match="gradient_units='mt_m'"):
        run_experiment(graph)


def test_physical_epg_diffusion_is_applied_and_monotone():
    sequence = _physical_tse()
    graph = build_preset("dark-blood-tse")
    graph.sequence = sequence
    graph.tissue = TissueModel(diffusion_adc_mm2_s=0.8e-3)
    assert plan_experiment(graph).engine == plan_experiment(graph).representation == "epg"
    assert "isotropic_diffusion_applied" in run_experiment(graph).sim_result.meta["assumptions"]
    options = EngineOptions(return_configurations=True)
    values = []
    for adc in (0.0, 0.8e-3, 1.6e-3):
        result = EPGEngine().simulate(
            sequence, Phantom(diffusion_adc_mm2_s=adc), ScannerModel(), options
        )
        values.append(np.abs(result.signal))
        assert ("isotropic_diffusion_applied" in result.meta["assumptions"]) == (adc > 0)
    assert not np.allclose(values[0], values[1], rtol=1e-10, atol=1e-12)
    assert np.all(values[2] <= values[1] + 1e-14)


def test_non_epg_engines_do_not_claim_diffusion_and_bm_is_open():
    for name in ("bloch", "hybrid", "ssepg", "pdg", "spectral", "epg-x"):
        assert REPRESENTATIONS[name].validity.diffusion == "unsupported"
        assert "isotropic_diffusion" not in REPRESENTATIONS[name].supports
    graph = build_preset("dark-blood-tse")
    graph.sequence = _physical_tse()
    graph.tissue = TissueModel(diffusion_adc_mm2_s=0.8e-3)
    graph.engine.preferred = "bloch"
    assert not validate_experiment(graph).valid
    with pytest.raises(ValueError, match="does not support diffusion"):
        run_experiment(graph)
    state = np.zeros((6, 3), dtype=complex)
    apply_bloch_mcconnell(state, 0.01, BlochMcConnellPools(1, .1, .5, 1, .1, .5, 1, 1))
