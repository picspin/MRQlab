from fastapi.testclient import TestClient
from mrqlab_api.main import app

client = TestClient(app)


def test_clinical_recipes_endpoint():
    response = client.get("/clinical-recipes")
    assert response.status_code == 200
    data = response.json()
    assert "recipes" in data
    assert len(data["recipes"]) >= 3
    recipe_ids = [r["id"] for r in data["recipes"]]
    assert "dark_blood_vessel_wall_tse" in recipe_ids
    # Run the experiment through /experiments/run
    exp = data["recipes"][0]["experiment"]
    run_response = client.post("/experiments/run", json=exp)
    assert run_response.status_code == 200
    run_data = run_response.json()
    assert "observations" in run_data
