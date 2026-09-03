from fastapi.testclient import TestClient

from mrqlab_api.main import app


client = TestClient(app)


def block(identifier, kind, t0_s, params):
    return {"id": identifier, "kind": kind, "t0_s": t0_s, "params": params}


def compose(blocks):
    response = client.post("/sequences/compose", json={"name": "Lego RUN", "blocks": blocks})
    assert response.status_code == 200, response.text
    return response.json()


def tse_recipe_json():
    response = client.get("/clinical-recipes")
    assert response.status_code == 200, response.text
    recipes = response.json()["recipes"]
    recipe = next((item for item in recipes if item["id"] == "brain_t2_tse"), None)
    if recipe is None:
        recipe = next(item for item in recipes if "tse" in item["id"].lower())
    return recipe["experiment"]


def test_http_run_accepts_composed_physical_ir_on_clinical_recipe():
    sequence = compose([
        block("rf1", "excite_sinc", 0, {"duration_s": .001, "time_bandwidth": 4, "flip_angle_deg": 90, "phase_deg": 0}),
        block("g1", "trap_gx", .001, {"amplitude_mt_m": 20, "duration_s": .004, "ramp_time_s": .0004, "unit": "mT_m"}),
        block("a1", "adc_gate", .005, {"duration_s": .001}),
    ])
    graph = tse_recipe_json()
    graph["sequence"] = sequence

    response = client.post("/experiments/run", json=graph)

    assert response.status_code == 200, response.text
    assert response.json()["observations"][0]["provenance"]["engine"] == "epg"


def test_http_run_rejects_teaching_ir_with_diffusion():
    sequence = compose([
        block("rf1", "excite_sinc", 0, {"duration_s": .001, "time_bandwidth": 4, "flip_angle_deg": 90, "phase_deg": 0}),
    ])
    graph = tse_recipe_json()
    graph["sequence"] = sequence
    graph["tissue"]["diffusion_adc_mm2_s"] = .8e-3

    response = client.post("/experiments/run", json=graph)

    assert response.status_code == 422, response.text
    assert "gradient_units" in response.text
