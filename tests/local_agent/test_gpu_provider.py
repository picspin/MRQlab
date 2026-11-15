import pytest
from mrqlab_experiment import build_protocol_experiment, build_result_graph, plan_experiment, run_experiment
from mrqlab_experiment.models import ExperimentGraph
from mrqlab_agent.providers import CpuExecutionProvider, GpuExecutionProvider, ProviderRegistry
from mrqlab_agent.store import JobStore
from mrqlab_agent.models import JobRecord
from mrqlab_agent.main import app, providers as app_providers, local_security, verify_lease
from mrqlab_agent.models import LeaseClaims, LeaseDecision
from fastapi.testclient import TestClient


@pytest.mark.parametrize("provider_factory", [
    lambda store: CpuExecutionProvider(store, max_workers=0),
    lambda store: GpuExecutionProvider(store, backend=object(), max_workers=0),
])
def test_cancelled_job_is_never_claimed_by_cpu_or_gpu_worker(provider_factory):
    """Cancellation winning before a worker starts leaves no untracked execution."""
    store = JobStore()
    provider = provider_factory(store)
    job = JobRecord(id="cancelled-before-worker", provider_id=provider.descriptor.id, plan_fingerprint="claim-race", status="queued")
    store.create(job)
    provider.cancel(job.id)

    provider._run(job.id, plan=object())

    assert store.get_job(job.id).status == "cancelled"
    assert [event.kind for event in store.events(job.id)] == ["queued", "cancelled"]


def test_claim_queued_is_atomic_against_cancel():
    """Only one of the queued->running claim or queued->cancelled transition wins."""
    store = JobStore()
    job = JobRecord(id="atomic-claim", provider_id="test", plan_fingerprint="atomic", status="queued")
    store.create(job)

    assert store.claim_queued(job.id)
    # Cancellation after a successful claim is a tracked running-job transition;
    # cancellation before the claim instead makes claim_queued return False.
    store.transition(job.id, "cancelled")
    assert not store.claim_queued(job.id)
    assert store.get_job(job.id).status == "cancelled"


def test_gpu_provider_fails_closed_until_an_optional_provider_is_registered():
    registry = ProviderRegistry()
    with pytest.raises(KeyError, match="provider 'local_gpu' is unavailable"):
        registry.get("local_gpu")


def test_registered_gpu_backend_runs_through_the_same_job_contract():
    class FakeGpuBackend:
        def execute(self, plan):
            graph = ExperimentGraph.model_validate(dict(plan.experiment_snapshot))
            return build_result_graph(run_experiment(graph))

    store = JobStore()
    provider = GpuExecutionProvider(store, FakeGpuBackend(), max_workers=1)
    registry = ProviderRegistry()
    registry.register(provider)
    plan = plan_experiment(build_protocol_experiment("brain_lesion_t2_tse"))
    handle = registry.get("local_gpu").submit(plan)
    provider.futures[handle.id].result(timeout=5)
    assert store.get_job(handle.id).status == "succeeded"
    assert "gpu.batch" in provider.capabilities().features
    provider.shutdown()


def test_gpu_job_submission_fails_closed_without_gpu_entitlement():
    class FakeGpuBackend:
        def execute(self, plan):
            return object()

    store = JobStore()
    gpu_provider = GpuExecutionProvider(store, FakeGpuBackend(), max_workers=1)
    app_providers.register(gpu_provider)

    client = TestClient(app)
    cpu_only_claims = LeaseClaims(
        iss="mrqlab-license", aud="mrqlab-local-runtime", lease_id="l1",
        organization_id="o1", device_id="d1", device_public_key_hash="pkh",
        fingerprint_hash="fph", issued_at=1000, not_before=1000, expires_at=2000,
        offline_grace_until=2100, product="pro", features=frozenset({"compute.cpu", "jobs.cancel"}),
        limits={}, software={"min_version": "1.0"}, key_id="k1",
    )
    decision = LeaseDecision(state="active", claims=cpu_only_claims)
    app.dependency_overrides[verify_lease] = lambda: decision

    headers = {
        "origin": "https://app.mrqlab.local",
        "x-mrqlab-pairing": local_security.pairing_secret,
        "x-mrqlab-csrf": local_security.csrf_token,
    }
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    res = client.post("/jobs", json={"provider_id": "local_gpu", "experiment": graph.model_dump(mode="json")}, headers=headers)
    assert res.status_code == 403
    assert "compute.gpu" in res.text
    app.dependency_overrides.clear()
