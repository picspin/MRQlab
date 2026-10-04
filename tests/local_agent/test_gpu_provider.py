import pytest
from mrqlab_experiment import build_protocol_experiment, build_result_graph, plan_experiment, run_experiment
from mrqlab_experiment.models import ExperimentGraph
from mrqlab_agent.providers import GpuExecutionProvider, ProviderRegistry
from mrqlab_agent.store import JobStore


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
