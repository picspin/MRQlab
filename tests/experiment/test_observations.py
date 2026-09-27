from mrqlab_experiment import (
    build_preset,
    build_protocol_experiment,
    plan_experiment,
    run_experiment,
)
from mrqlab_experiment.observations import build_result_graph


def test_result_graph_wraps_signal_kspace_image_and_provenance():
    graph = build_preset("gradient-echo", {"te": 0.02, "tr": 0.1})
    result = build_result_graph(run_experiment(graph))
    assert [item.kind for item in result.observations] == ["signal", "k_trajectory", "image"]
    image = result.observations[-1]
    assert image.derived_from == (result.observations[0].id,)
    assert image.provenance.engine == "bloch"
    assert image.provenance.experiment_hash


def test_every_observation_carries_resolved_plan_and_parameter_provenance():
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    result = build_result_graph(run_experiment(graph))
    fingerprints = {item.provenance.plan_fingerprint for item in result.observations}
    assert fingerprints == {plan_experiment(graph).fingerprint}
    for observation in result.observations:
        assert observation.provenance.clinical_recipe_id == "brain_lesion_t2_tse"
        assert observation.provenance.scanner_profile == "research-3t@1.0.0"
        assert {item.name for item in observation.provenance.parameters} >= {
            "te",
            "b0_t",
            "max_work",
        }
