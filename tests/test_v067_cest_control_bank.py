"""v0.67: run-from-recipe overlays CEST knobs into metadata.cest, not the top level."""
from fastapi.testclient import TestClient

from mrqlab_api.main import app, _overlay_sequence_params
from mrqlab_experiment import build_clinical_recipe, run_experiment

client = TestClient(app)


def test_cest_params_overlay_into_metadata_cest_not_top_level():
    graph = build_clinical_recipe("cest_amide_z_spectrum")
    overlaid = _overlay_sequence_params(graph, {"saturation_power_uT": 1.0, "offset_span_ppm": 6.0})
    cest = overlaid.sequence.metadata["cest"]
    assert cest["saturation_power_uT"] == 1.0
    assert cest["offsets_ppm"][0] == -6.0
    assert cest["offsets_ppm"][-1] == 6.0
    assert 3.5 in cest["offsets_ppm"]
    assert cest["offset_span_ppm"] == 6.0
    assert "saturation_power_uT" not in overlaid.sequence.metadata
    assert "offset_span_ppm" not in overlaid.sequence.metadata


def test_pulsed_duty_cycle_rebuilds_train_and_keeps_elapsed():
    graph = build_clinical_recipe("cest_amide_pulsed_z_spectrum")
    overlaid = _overlay_sequence_params(graph, {"duty_cycle": 0.8})
    cest = overlaid.sequence.metadata["cest"]
    elapsed = cest["n_pulses"] * cest["pulse_duration_s"] + (cest["n_pulses"] - 1) * cest["gap_duration_s"]
    assert elapsed == cest["saturation_duration_s"]
    assert cest["n_pulses"] * cest["pulse_duration_s"] / elapsed == 0.8
    assert cest["duty_cycle"] == 0.8
    assert "duty_cycle" not in overlaid.sequence.metadata


def test_cest_power_overlay_changes_amide_z():
    baseline = run_experiment(build_clinical_recipe("cest_amide_z_spectrum")).sim_result.z_spectrum
    stronger = run_experiment(
        _overlay_sequence_params(build_clinical_recipe("cest_amide_z_spectrum"), {"saturation_power_uT": 4.0})
    ).sim_result.z_spectrum
    plus = [i for i, offset in enumerate(baseline["offset_ppm"]) if abs(offset - 3.5) < 1e-12][0]
    assert stronger["Z"][plus] < baseline["Z"][plus]


def test_cw_rejects_duty_cycle_overlay():
    graph = build_clinical_recipe("cest_amide_z_spectrum")
    try:
        _overlay_sequence_params(graph, {"duty_cycle": 0.5})
    except ValueError as exc:
        assert "duty" in str(exc).lower()
    else:
        raise AssertionError("CW duty overlay must fail closed")


def test_tse_overlay_still_writes_sequence_params():
    graph = build_clinical_recipe("brain_t2_tse")
    overlaid = _overlay_sequence_params(graph, {"te": 0.08, "echo_count": 8})
    assert overlaid.sequence.params["te"] == 0.08
    assert overlaid.sequence.params["echo_count"] == 8


def test_empty_cest_overlay_leaves_recipe_metadata_untouched():
    graph = build_clinical_recipe("cest_amide_pulsed_z_spectrum")
    overlaid = _overlay_sequence_params(graph, {})
    assert overlaid.sequence.metadata["cest"] == graph.sequence.metadata["cest"]


def test_pulsed_recipe_declares_duty_cycle_in_metadata_cest():
    pulsed = build_clinical_recipe("cest_amide_pulsed_z_spectrum").sequence.metadata["cest"]
    assert pulsed["duty_cycle"] == pulsed["n_pulses"] * pulsed["pulse_duration_s"] / pulsed["saturation_duration_s"]
    assert "duty_cycle" not in build_clinical_recipe("cest_amide_z_spectrum").sequence.metadata["cest"]


def test_cest_recipe_declares_offset_span_ppm_in_metadata_cest():
    cw = build_clinical_recipe("cest_amide_z_spectrum").sequence.metadata["cest"]
    pulsed = build_clinical_recipe("cest_amide_pulsed_z_spectrum").sequence.metadata["cest"]
    assert cw["offset_span_ppm"] == max(abs(v) for v in cw["offsets_ppm"])
    assert pulsed["offset_span_ppm"] == max(abs(v) for v in pulsed["offsets_ppm"])


def test_run_from_recipe_accepts_cest_knobs():
    response = client.post("/experiments/run-from-recipe", json={
        "recipe_id": "cest_amide_pulsed_z_spectrum",
        "params": {"saturation_power_uT": 1.5, "offset_span_ppm": 5.0, "duty_cycle": 0.6},
        "products": ["z_spectrum", "mtr_asym"],
    })
    assert response.status_code == 200, response.text
    spectrum = next(item for item in response.json()["observations"] if item["kind"] == "z_spectrum")
    assert spectrum["data"]["mode"] == "pulsed"
    assert abs(spectrum["data"]["duty_cycle"] - 0.6) < 1e-9
    assert spectrum["provenance"]["engine"] == "epg-x"
