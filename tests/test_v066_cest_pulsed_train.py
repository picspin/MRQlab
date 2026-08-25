import numpy as np
import pytest

from mrqlab_experiment import CapabilityMismatch, build_clinical_recipe, build_result_graph, plan_experiment, run_experiment
from mrqlab_experiment.kernel import _phantom_from_sample
from mrqlab_physics.backends.epg_x import EpgXBackend
from mrqlab_physics.ops.types import Relax


def _observations(graph):
    return {item.kind: item for item in build_result_graph(run_experiment(graph)).observations}


def test_pulsed_recipe_contract_and_elapsed_control():
    graph = build_clinical_recipe("cest_amide_pulsed_z_spectrum")
    assert plan_experiment(graph).engine == "epg-x"
    run = run_experiment(graph)
    data = run.sim_result.z_spectrum
    assert data["mode"] == "pulsed"
    assert data["duty_cycle"] == pytest.approx(20 * .05 / 1.95)
    assert run.sim_result.meta["n_ops"] == 9 * 39 + 1
    assert "cest_pulsed_train_applied" in run.sim_result.meta["assumptions"]
    control = EpgXBackend(_phantom_from_sample(graph), 0)
    control.apply(Relax(0, 1.95))
    assert data["Mz_ref"][0] == pytest.approx(float(np.real(control.omega[2, 0])), abs=1e-9)
    observed = _observations(graph)["z_spectrum"].data
    assert observed["mode"] == "pulsed"
    assert observed["duty_cycle"] == pytest.approx(20 * .05 / 1.95)


def test_one_pulse_collapses_to_cw_and_default_train_differs():
    cw = build_clinical_recipe("cest_amide_z_spectrum")
    pulsed = build_clinical_recipe("cest_amide_pulsed_z_spectrum")
    assert "cest_pulsed_train_applied" not in run_experiment(cw).sim_result.meta["assumptions"]
    default_delta = np.max(np.abs(run_experiment(cw).sim_result.z_spectrum["Z"] - run_experiment(pulsed).sim_result.z_spectrum["Z"]))
    assert default_delta > 1e-4
    pulsed.sequence.metadata["cest"].update(n_pulses=1, pulse_duration_s=2.0, gap_duration_s=0.0, saturation_duration_s=2.0)
    assert run_experiment(pulsed).sim_result.z_spectrum["Z"] == pytest.approx(run_experiment(cw).sim_result.z_spectrum["Z"], abs=1e-9)


@pytest.mark.parametrize("mutation", ["missing", "n", "pulse", "gap", "mode", "elapsed", "image", "bound", "engine"])
def test_pulsed_contract_fails_closed(mutation):
    graph = build_clinical_recipe("cest_amide_pulsed_z_spectrum")
    cest = graph.sequence.metadata["cest"]
    if mutation == "missing": cest.pop("n_pulses")
    elif mutation == "n": cest["n_pulses"] = 0
    elif mutation == "pulse": cest["pulse_duration_s"] = 0
    elif mutation == "gap": cest["gap_duration_s"] = -1
    elif mutation == "mode": cest["mode"] = "waltz"
    elif mutation == "elapsed": cest["saturation_duration_s"] = 2
    elif mutation == "image": graph.readout.products += ("image",)
    elif mutation == "bound": graph.tissue[1].bound_pool = True
    elif mutation == "engine": graph.engine.preferred = "epg"
    with pytest.raises((ValueError, CapabilityMismatch)):
        run_experiment(graph)


def test_pulsed_exchange_deepens_amide_and_mtr_asym_is_positive():
    exchanging = _observations(build_clinical_recipe("cest_amide_pulsed_z_spectrum"))
    baseline_graph = build_clinical_recipe("cest_amide_pulsed_z_spectrum")
    baseline_graph.tissue[0].exchange_rate_hz = 0.0
    baseline = _observations(baseline_graph)
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


def test_default_tse_still_has_no_cest_assumptions():
    run = run_experiment(build_clinical_recipe("brain_t2_tse"))
    assumptions = run.sim_result.meta.get("assumptions", [])
    assert "cest_z_spectrum_applied" not in assumptions
    assert "cest_pulsed_train_applied" not in assumptions
    assert run.sim_result.z_spectrum is None


def test_physics_docs_close_rectangular_train_and_keep_imaging_closed():
    from pathlib import Path

    text = Path("docs/PHYSICS.md").read_text()
    assert "rectangular pulsed-train" in text
    assert "CEST imaging" in text
    assert "remain unavailable" in text
    assert "pulsed saturation trains remain unavailable" not in text
