import time

import pytest
from fastapi.testclient import TestClient

from mrqlab_experiment import build_protocol_experiment
from mrqlab_agent.main import app, local_security, require_compute_entitlement

HEADERS = {
    "origin": "https://app.mrqlab.local",
    "x-mrqlab-pairing": local_security.pairing_secret,
    "x-mrqlab-csrf": local_security.csrf_token,
}
client = TestClient(app)


@pytest.fixture(autouse=True)
def entitled_request():
    app.dependency_overrides[require_compute_entitlement] = lambda: object()
    yield
    app.dependency_overrides.clear()


def test_job_api_runs_cpu_and_serves_opaque_artifact():
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    created = client.post(
        "/jobs",
        json={"provider_id": "local_cpu_numpy", "experiment": graph.model_dump(mode="json")},
        headers=HEADERS,
    )
    assert created.status_code == 202
    job_id = created.json()["id"]
    assert client.get(f"/jobs/{job_id}/events", headers=HEADERS).status_code == 200
    status_body = client.get(f"/jobs/{job_id}", headers=HEADERS).json()
    for _ in range(200):
        if status_body["status"] in {"succeeded", "failed"}:
            break
        time.sleep(.01)
        status_body = client.get(f"/jobs/{job_id}", headers=HEADERS).json()
    assert status_body["status"] == "succeeded"
    artifact = client.get(f"/artifacts/{status_body['artifact_id']}", headers=HEADERS)
    assert artifact.status_code == 200
    assert artifact.headers["content-type"].startswith("application/vnd.mrqlab.result+json")


def test_job_api_never_accepts_a_filesystem_path():
    response = client.post(
        "/jobs",
        json={"provider_id": "local_cpu_numpy", "experiment_path": "/tmp/private.json"},
        headers=HEADERS,
    )
    assert response.status_code == 422
