import time

import pytest
from fastapi.testclient import TestClient

from mrqlab_experiment import build_protocol_experiment
from mrqlab_agent.main import app, local_security, verify_lease
from mrqlab_agent.models import LeaseClaims, LeaseDecision

HEADERS = {
    "origin": "https://app.mrqlab.local",
    "x-mrqlab-pairing": local_security.pairing_secret,
    "x-mrqlab-csrf": local_security.csrf_token,
}
client = TestClient(app)


@pytest.fixture(autouse=True)
def entitled_request():
    claims = LeaseClaims(
        iss="mrqlab-license", aud="mrqlab-local-runtime", lease_id="l1",
        organization_id="o1", device_id="d1", device_public_key_hash="pkh",
        fingerprint_hash="fph", issued_at=1000, not_before=1000, expires_at=2000,
        offline_grace_until=2100, product="pro", features=frozenset({"compute.cpu", "jobs.cancel"}),
        limits={}, software={"min_version": "1.0"}, key_id="k1",
    )
    decision = LeaseDecision(state="active", claims=claims)
    app.dependency_overrides[verify_lease] = lambda: decision
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


def test_job_api_enforces_lease_concurrency_limit():
    from mrqlab_agent.main import store
    from mrqlab_agent.models import JobRecord
    claims = LeaseClaims(
        iss="mrqlab-license", aud="mrqlab-local-runtime", lease_id="l1",
        organization_id="o1", device_id="d1", device_public_key_hash="pkh",
        fingerprint_hash="fph", issued_at=1000, not_before=1000, expires_at=2000,
        offline_grace_until=2100, product="pro", features=frozenset({"compute.cpu", "jobs.cancel"}),
        limits={"max_concurrent_jobs": 1}, software={"min_version": "1.0"}, key_id="k1",
    )
    decision = LeaseDecision(state="active", claims=claims)
    app.dependency_overrides[verify_lease] = lambda: decision

    # Pre-occupy concurrency slot with a running job
    store.create(JobRecord(id="busy_job", provider_id="local_cpu_numpy", plan_fingerprint="fp", status="running"))

    graph = build_protocol_experiment("brain_lesion_t2_tse").model_copy(update={"id": "different_exp_id"})
    res = client.post("/jobs", json={"provider_id": "local_cpu_numpy", "experiment": graph.model_dump(mode="json")}, headers=HEADERS)
    assert res.status_code == 429
    assert "concurrent jobs reached" in res.text


def test_job_api_is_idempotent_by_plan_fingerprint_and_provider():
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    payload = {"provider_id": "local_cpu_numpy", "experiment": graph.model_dump(mode="json")}

    res1 = client.post("/jobs", json=payload, headers=HEADERS)
    assert res1.status_code == 202
    job_id_1 = res1.json()["id"]

    # Re-submitting the exact same experiment returns the identical job
    res2 = client.post("/jobs", json=payload, headers=HEADERS)
    assert res2.status_code == 202
    job_id_2 = res2.json()["id"]
    assert job_id_1 == job_id_2
