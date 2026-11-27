import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

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


def test_worker_claim_and_cancel_are_atomic():
    store = JobStore()
    provider = CpuExecutionProvider(store, max_workers=0)
    plan = plan_experiment(build_protocol_experiment("brain_lesion_t2_tse"))
    job = provider.submit(plan)
    gate = Barrier(2)

    def start():
        gate.wait()
        return store.start_if_queued(job.id)

    def cancel():
        gate.wait()
        try:
            provider.cancel(job.id)
            return "cancelled"
        except ValueError as exc:
            assert "not preemptible" in str(exc)
            return "running"

    with ThreadPoolExecutor(max_workers=2) as workers:
        start_future = workers.submit(start)
        cancel_future = workers.submit(cancel)
        claimed, outcome = start_future.result(), cancel_future.result()
    assert (claimed, outcome) in {(True, "running"), (False, "cancelled")}
    assert [event.kind for event in store.events(job.id)] == ["queued", outcome]
    provider.shutdown()
