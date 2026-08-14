from fastapi.testclient import TestClient
from mrqlab_api.main import app
client = TestClient(app)

def test_health_and_engines():
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/engines").json()["default"] == "bloch"

def test_build_and_simulate_gre():
    built = client.post("/sequences/build", json={"template":"GRE", "params":{"te":.02,"tr":.1}})
    assert built.status_code == 200
    response = client.post("/simulate", json={"sequence":built.json()})
    assert response.status_code == 200
    assert response.json()["signal"]

def test_matrix_cap():
    response = client.post("/simulate", json={"template":{"template":"SE"}, "matrix":65})
    assert response.status_code == 422
