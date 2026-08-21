"""v0.50: RUN must use a canonical clinical recipe, not a hand-built cockpit graph."""
from fastapi.testclient import TestClient

from mrqlab_api.main import app

client = TestClient(app)

COCKPIT_HAND_BUILT = {
    "schema_version": "1.0",
    "id": "exp-ms_brain-test",
    "name": "Brain & Neuro — MS Plaque Demarcation",
    "sequence": {
        "template": {
            "ref": "TSE",
            "parameters": {
                "te": 0.1,
                "tr": 3.0,
                "refocusing_flip_angle": 150,
                "echo_count": 16,
            },
        }
    },
    "sample": {"tissues": [{"id": "lesion", "t1": 1.4, "t2": 0.12, "proton_density": 0.95}]},
    "scanner": {"b0_t": 3.0},
    "engine": {"target_representation": "epg"},
    "readout": {"products": ["signal", "k_trajectory", "magnetization"]},
    "constraints": {},
    "disturbances": [],
    "provenance": {},
}


def test_hand_built_cockpit_graph_is_rejected_as_422():
    response = client.post("/experiments/run", json=COCKPIT_HAND_BUILT)
    assert response.status_code == 422


def test_run_from_recipe_brain_t2_tse_returns_result_graph():
    response = client.post(
        "/experiments/run-from-recipe",
        json={
            "recipe_id": "brain_t2_tse",
            "params": {
                "te": 0.1,
                "tr": 3.0,
                "refocusing_flip_angle": 150,
                "echo_count": 16,
            },
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema_version"] == "1.0"
    kinds = {item["kind"] for item in body["observations"]}
    assert "signal" in kinds
    engines = {item.get("provenance", {}).get("engine") for item in body["observations"]}
    assert any(engines)


def test_run_from_recipe_unknown_id_is_404():
    response = client.post(
        "/experiments/run-from-recipe",
        json={"recipe_id": "does-not-exist"},
    )
    assert response.status_code == 404
