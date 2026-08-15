from mrqlab_experiment import build_preset, run_experiment
from mrqlab_experiment.observations import build_result_graph


def test_result_graph_wraps_signal_kspace_image_and_provenance():
    graph = build_preset("gradient-echo", {"te": 0.02, "tr": 0.1})
    result = build_result_graph(run_experiment(graph))
    assert [item.kind for item in result.observations] == ["signal", "k_trajectory", "image"]
    image = result.observations[-1]
    assert image.derived_from == (result.observations[0].id,)
    assert image.provenance.engine == "bloch"
    assert image.provenance.experiment_hash
