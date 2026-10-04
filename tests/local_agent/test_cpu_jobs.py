import time

from mrqlab_experiment import build_protocol_experiment, plan_experiment
from mrqlab_agent.providers import CpuExecutionProvider
from mrqlab_agent.store import JobStore


def _wait(store, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = store.get_job(job_id)
        if job.status in {"succeeded", "failed", "cancelled"}:
            return job
        time.sleep(.01)
    raise AssertionError("CPU job did not finish")


def test_cpu_worker_emits_events_and_content_addressed_result():
    store = JobStore()
    provider = CpuExecutionProvider(store, max_workers=1)
    plan = plan_experiment(build_protocol_experiment("brain_lesion_t2_tse"))
    handle = provider.submit(plan)
    job = _wait(store, handle.id)
    assert job.status == "succeeded"
    assert [event.kind for event in store.events(handle.id)] == ["queued", "running", "artifact", "succeeded"]
    artifact = store.get_artifact(job.artifact_id)
    assert artifact.media_type == "application/vnd.mrqlab.result+json"
    assert artifact.sha256 == job.artifact_id
    provider.shutdown()


def test_cancelled_queued_job_never_runs():
    store = JobStore()
    provider = CpuExecutionProvider(store, max_workers=0)
    plan = plan_experiment(build_protocol_experiment("brain_lesion_t2_tse"))
    handle = provider.submit(plan)
    provider.cancel(handle.id)
    assert store.get_job(handle.id).status == "cancelled"
