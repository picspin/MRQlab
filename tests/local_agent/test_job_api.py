import time

from fastapi.testclient import TestClient
from mrqlab_experiment import build_protocol_experiment
from mrqlab_agent.main import app

client = TestClient(app)


def test_job_api_runs_cpu_and_serves_opaque_artifact():
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    created = client.post("/jobs", json={"provider_id": "local_cpu_numpy", "experiment": graph.model_dump(mode="json")})
    assert created.status_code == 202
    job_id = created.json()["id"]
    with client.stream("GET", f"/jobs/{job_id}/events") as response:
        assert response.status_code == 200
    status = client.get(f"/jobs/{job_id}").json()
    for _ in range(200):
        if status["status"] in {"succeeded", "failed"}:
            break
        time.sleep(.01)
        status = client.get(f"/jobs/{job_id}").json()
    assert status["status"] == "succeeded"
    artifact = client.get(f"/artifacts/{status['artifact_id']}")
    assert artifact.status_code == 200
    assert artifact.headers["content-type"].startswith("application/vnd.mrqlab.result+json")


def test_job_api_never_accepts_a_filesystem_path():
    response = client.post("/jobs", json={"provider_id": "local_cpu_numpy", "experiment_path": "/tmp/private.json"})
    assert response.status_code == 422
