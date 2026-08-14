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

def test_tse_uses_preferred_epg_engine_when_request_omits_engine():
    response = client.post("/simulate", json={
        "template": {"template": "TSE", "params": {"te": 0.02, "tr": 0.1, "echoes": 2}},
        "options": {"epg_kmax": 8},
    })
    assert response.status_code == 200
    assert response.json()["meta"]["engine"] == "epg"
    assert len(response.json()["signal"]) == 4

def test_explicit_engine_overrides_template_preference():
    response = client.post("/simulate", json={
        "template": {"template": "TSE", "params": {"te": 0.02, "tr": 0.1}},
        "engine": "bloch",
    })
    assert response.status_code == 200
    assert response.json()["meta"]["engine"] == "bloch"

def test_unknown_engine_is_a_validation_error():
    response = client.post("/simulate", json={
        "template": {"template": "GRE"},
        "engine": "missing",
    })
    assert response.status_code == 422
    assert "unknown engine" in response.json()["detail"]

def test_server_work_cap_cannot_be_raised_by_request(monkeypatch):
    monkeypatch.setattr("mrqlab_api.main.MAX_WORK", 1)
    response = client.post("/simulate", json={
        "template": {"template": "GRE"},
        "options": {"max_work": 999999},
    })
    assert response.status_code == 422
    assert "estimated work" in response.json()["detail"]


def test_simulate_spectral_parses_nested_pool_and_isochromat_payloads():
    response = client.post("/simulate", json={
        "template": {"template": "GRE", "params": {"te": 0.02, "tr": 0.1}},
        "engine": "spectral",
        "phantom": {
            "isochromats": [{"t1": 1.0, "t2": 0.1, "proton_density": 1.0}],
            "pools": [{"name": "water", "fraction": 1.0, "chemical_shift_ppm": 0.0, "t1": 1.0, "t2": 0.1}],
        },
    })

    assert response.status_code == 200
    assert response.json()["meta"]["engine"] == "spectral"
