import pytest
from fastapi.testclient import TestClient
from mrqlab_api.main import app

client = TestClient(app)


def test_tissue_signal_endpoint_for_clinical_recipe():
    res = client.post("/tissue-signal", json={"recipe_id": "brain_t2_tse", "params": {"te": 0.012, "tr": 3.5}})
    assert res.status_code == 200
    data = res.json()
    assert "signals" in data
    assert "tissues" in data
    assert "contrast_difference" in data
    assert len(data["tissues"]) >= 2


def test_custom_recipe_crud_and_signal():
    # Fetch a base recipe first
    base_recipe_res = client.get("/clinical-recipes")
    assert base_recipe_res.status_code == 200
    recipes = base_recipe_res.json()["recipes"]
    assert len(recipes) > 0
    exp = recipes[0]["experiment"]

    # Save as custom recipe
    save_res = client.post("/recipes/custom", json={"id": "my_custom_scenario", "experiment": exp})
    assert save_res.status_code == 200
    assert save_res.json()["id"] == "my_custom_scenario"

    # Get custom recipe
    get_res = client.get("/recipes/custom/my_custom_scenario")
    assert get_res.status_code == 200
    assert get_res.json()["experiment"]["id"] == exp["id"]

    # Evaluate tissue signal on custom recipe
    signal_res = client.post("/tissue-signal", json={"recipe_id": "my_custom_scenario"})
    assert signal_res.status_code == 200
    assert "signals" in signal_res.json()
