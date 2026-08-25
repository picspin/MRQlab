import numpy as np
import pytest

from mrqlab_experiment import (
    CapabilityMismatch,
    build_clinical_recipe,
    build_result_graph,
    plan_experiment,
    run_experiment,
)
from mrqlab_physics.backends.epg_x import EpgXBackend
from mrqlab_physics.engines.epg_x_engine import EpgXEngine
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from mrqlab_physics.models import EngineOptions, ScannerModel
from mrqlab_physics.ops.types import Relax


def _spectrum(graph):
    result = build_result_graph(run_experiment(graph))
    return {observation.kind: observation for observation in result.observations}


def test_cest_recipe_runs_epgx_and_emits_backend_spectrum_and_asymmetry():
    graph = build_clinical_recipe("cest_amide_z_spectrum")
    assert plan_experiment(graph).engine == "epg-x"
    assert graph.readout.products == ("z_spectrum", "mtr_asym")
    by_kind = _spectrum(graph)
    spectrum = by_kind["z_spectrum"]
    assert spectrum.data["offset_ppm"] == sorted(spectrum.data["offset_ppm"])
    assert np.all(np.isfinite(spectrum.data["Z"]))
    assert spectrum.data["normalization"] == "unsaturated_control"
    assert spectrum.provenance.engine == "epg-x"
    assert "cest_z_spectrum_applied" in spectrum.provenance.assumptions
    assert by_kind["mtr_asym"].derived_from == ("z_spectrum",)
    assert "image" not in by_kind


def test_mz_ref_is_unsaturated_control_not_thermal_m0():
    graph = build_clinical_recipe("cest_amide_z_spectrum")
    run = run_experiment(graph)
    control = EpgXBackend(_phantom(graph), 0)
    control.apply(Relax(0.0, graph.sequence.metadata["cest"]["saturation_duration_s"]))
    expected = float(np.real(control.omega[2, 0]))
    assert run.sim_result.z_spectrum["Mz_ref"][0] == pytest.approx(expected, rel=0, abs=1e-9)
    assert "unsaturated_control" in run.sim_result.meta["assumptions"]


def _phantom(graph):
    from mrqlab_experiment.kernel import _phantom_from_sample

    return _phantom_from_sample(graph)


def test_no_exchange_z_spectrum_is_symmetric_direct_saturation():
    graph = build_clinical_recipe("cest_amide_z_spectrum")
    graph.tissue[0].exchange_rate_hz = 0.0
    by_kind = _spectrum(graph)
    offsets = np.asarray(by_kind["z_spectrum"].data["offset_ppm"])
    z = np.asarray(by_kind["z_spectrum"].data["Z"])
    plus = z[np.isclose(offsets, 3.5)][0]
    minus = z[np.isclose(offsets, -3.5)][0]
    on_res = z[np.isclose(offsets, 0.0)][0]
    far = z[np.isclose(offsets, 5.0)][0]
    assert plus == pytest.approx(minus, rel=0, abs=2e-3)
    assert on_res < far
    assert all(abs(value) < 2e-3 for value in by_kind["mtr_asym"].data["MTR_asym"])


def test_exchange_creates_amide_dip_and_positive_mtr_asym():
    exchanging = _spectrum(build_clinical_recipe("cest_amide_z_spectrum"))
    baseline_graph = build_clinical_recipe("cest_amide_z_spectrum")
    baseline_graph.tissue[0].exchange_rate_hz = 0.0
    baseline = _spectrum(baseline_graph)
    offsets = np.asarray(exchanging["z_spectrum"].data["offset_ppm"])
    z_ex = np.asarray(exchanging["z_spectrum"].data["Z"])
    z_base = np.asarray(baseline["z_spectrum"].data["Z"])
    plus = np.isclose(offsets, 3.5)
    minus = np.isclose(offsets, -3.5)
    assert z_ex[plus][0] < z_base[plus][0]
    assert z_ex[plus][0] < z_ex[minus][0]
    asym_offsets = np.asarray(exchanging["mtr_asym"].data["offset_ppm"])
    asym = np.asarray(exchanging["mtr_asym"].data["MTR_asym"])
    assert asym[np.isclose(asym_offsets, 3.5)][0] > 0


def test_offset_order_does_not_change_per_point_z():
    graph = build_clinical_recipe("cest_amide_z_spectrum")
    first = np.asarray(_spectrum(graph)["z_spectrum"].data["Z"])
    graph.sequence.metadata["cest"]["offsets_ppm"] = [5, 3.5, -4, 0, -3.5, 4.5, -5, 4, -4.5]
    second = np.asarray(_spectrum(graph)["z_spectrum"].data["Z"])
    assert first == pytest.approx(second, rel=0, abs=1e-12)


def test_far_offset_recovers_relative_to_on_resonance_and_amide():
    by_kind = _spectrum(build_clinical_recipe("cest_amide_z_spectrum"))
    offsets = np.asarray(by_kind["z_spectrum"].data["offset_ppm"])
    z = np.asarray(by_kind["z_spectrum"].data["Z"])
    assert z[np.isclose(offsets, 5.0)][0] > z[np.isclose(offsets, 3.5)][0]
    assert z[np.isclose(offsets, -5.0)][0] > z[np.isclose(offsets, 0.0)][0]


@pytest.mark.parametrize("mutation", ["offsets", "duration", "power", "water_shift", "bound", "image", "engine"])
def test_cest_contract_fails_closed(mutation):
    graph = build_clinical_recipe("cest_amide_z_spectrum")
    if mutation == "offsets":
        graph.sequence.metadata["cest"]["offsets_ppm"] = []
    elif mutation == "duration":
        graph.sequence.metadata["cest"]["saturation_duration_s"] = 0
    elif mutation == "power":
        graph.sequence.metadata["cest"]["saturation_power_uT"] = 0
    elif mutation == "water_shift":
        graph.tissue[0].chemical_shift_ppm = 1
    elif mutation == "bound":
        graph.tissue[1].bound_pool = True
    elif mutation == "image":
        graph.readout.products = (*graph.readout.products, "image")
    elif mutation == "engine":
        graph.engine.preferred = "epg"
    with pytest.raises((ValueError, RuntimeError, CapabilityMismatch)):
        run_experiment(graph)


def test_default_tse_has_no_cest_result_or_assumption():
    run = run_experiment(build_clinical_recipe("brain_t2_tse"))
    assert run.sim_result.z_spectrum is None
    assert "cest_z_spectrum_applied" not in run.sim_result.meta.get("assumptions", [])


def test_ppm_axis_is_water_referenced_at_three_tesla():
    graph = build_clinical_recipe("cest_amide_z_spectrum")
    spectrum = run_experiment(graph).sim_result.z_spectrum
    expected = np.asarray(spectrum["offset_ppm"]) * GAMMA_BAR_HZ_T * 3.0 * 1e-6
    assert spectrum["offset_hz"] == pytest.approx(expected, rel=0, abs=1e-6)
    engine = EpgXEngine()
    assert engine.name == "epg-x"
    assert ScannerModel(b0_t=3.0).b0_t == 3.0
    assert EngineOptions(epg_kmax=0).epg_kmax == 0
