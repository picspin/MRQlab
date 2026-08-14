import pytest
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


def test_raw_json_nan_cannot_bypass_server_work_cap(monkeypatch):
    monkeypatch.setattr("mrqlab_api.main.MAX_WORK", 1)
    response = client.post(
        "/simulate",
        content='{"template":{"template":"GRE"},"options":{"max_work":NaN}}',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert "finite" in response.json()["detail"]


@pytest.mark.parametrize(
    "options",
    [
        {"epg_kmax": True},
        {"epg_kmax": 2.5},
        {"max_work": True},
        {"max_work": 100.0},
        {"return_magnetization": 1},
    ],
)
def test_http_options_reject_non_strict_integer_and_boolean_fields(options):
    response = client.post(
        "/simulate",
        json={"template": {"template": "GRE"}, "options": options},
    )

    assert response.status_code == 422
    assert "strict" in response.json()["detail"]


def test_http_rejects_post_duration_sequence_events():
    response = client.post(
        "/simulate",
        json={
            "sequence": {
                "name": "post-duration",
                "duration": 0.01,
                "channels": [
                    {
                        "name": "adc_gate",
                        "events": [
                            {"time": 0.02, "value": 1.0},
                            {"time": 0.021, "value": 0.0},
                        ],
                    }
                ],
            }
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize("endpoint", ["/sequences/build", "/simulate"])
@pytest.mark.parametrize("echoes", [0, 1.5, True])
def test_http_template_endpoints_reject_invalid_echo_counts(endpoint, echoes):
    template = {
        "template": "TSE",
        "params": {"te": 0.02, "tr": 0.1, "echoes": echoes},
    }
    payload = template if endpoint == "/sequences/build" else {"template": template}

    response = client.post(endpoint, json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize("endpoint", ["/sequences/build", "/simulate"])
@pytest.mark.parametrize("echoes", [2, 10**400])
def test_http_template_endpoints_reject_echo_tr_overflow(endpoint, echoes):
    template = {
        "template": "TSE",
        "params": {"te": 0.03, "tr": 0.05, "echoes": echoes},
    }
    payload = template if endpoint == "/sequences/build" else {"template": template}

    response = client.post(endpoint, json=payload)

    assert response.status_code == 422


def test_http_malformed_epg_shift_metadata_is_a_validation_error():
    response = client.post(
        "/simulate",
        json={
            "sequence": {
                "name": "malformed-shift",
                "duration": 0.01,
                "channels": [],
                "metadata": {"epg_dk_events": [{}]},
            },
            "engine": "epg",
        },
    )

    assert response.status_code == 422
    assert "epg_dk_event" in response.json()["detail"]


def test_api_does_not_collect_snapshots_that_it_does_not_return(monkeypatch):
    def fail_if_snapshotted(self):
        raise AssertionError("API collected an omitted snapshot")

    monkeypatch.setattr("mrqlab_physics.backends.bloch.BlochBackend.snapshot", fail_if_snapshotted)
    response = client.post(
        "/simulate",
        json={
            "template": {"template": "GRE", "params": {"te": 0.02, "tr": 0.1}},
            "options": {"return_magnetization": True},
        },
    )

    assert response.status_code == 200
