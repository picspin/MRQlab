import pytest
from mrqlab_experiment import build_protocol_experiment, plan_experiment
from mrqlab_experiment.execution_provider import InProcessNumpyProvider


def test_in_process_provider_consumes_resolved_plan_and_returns_observations():
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    plan = plan_experiment(graph)
    provider = InProcessNumpyProvider()
    assert provider.validate(plan).valid is True
    assert provider.capabilities().features >= frozenset({"cpu.numpy", "sync.experiment"})
    handle = provider.submit(plan)
    assert handle.status == "succeeded"
    assert handle.plan_fingerprint == plan.fingerprint
    assert handle.result is not None
    assert handle.result.experiment_id == graph.id


def test_in_process_provider_rejects_a_plan_it_cannot_reconstruct():
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    plan = plan_experiment(graph).model_copy(update={"experiment_snapshot": {}})
    handle = InProcessNumpyProvider().submit(plan)
    assert handle.status == "failed"
    assert "ExperimentGraph" in handle.error


def test_in_process_provider_cannot_cancel():
    provider = InProcessNumpyProvider()
    with pytest.raises(ValueError, match="cannot be cancelled"):
        provider.cancel("some-id")
