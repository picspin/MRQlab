import pytest
from mrqlab_experiment import build_preset, run_experiment
from mrqlab_experiment.models import ReadoutSpec
from mrqlab_experiment.observations import build_result_graph


def test_result_graph_emits_only_requested_products_in_order():
    graph = build_preset("gradient-echo", {"te": 0.02, "tr": 0.1})
    graph.readout = ReadoutSpec(products=("image", "signal"))
    result = build_result_graph(run_experiment(graph))
    assert [item.id for item in result.observations] == ["image", "signal"]
    assert [item.kind for item in result.observations] == ["image", "signal"]
    image = result.observations[0]
    assert image.derived_from == ()


def test_unknown_readout_product_fails_closed():
    graph = build_preset("spin-echo", {"te": 0.02, "tr": 0.1})
    graph.readout = ReadoutSpec(products=("not_a_product",))
    with pytest.raises(ValueError, match="unknown"):
        build_result_graph(run_experiment(graph))


def test_empty_products_emit_no_observations():
    graph = build_preset("spin-echo", {"te": 0.02, "tr": 0.1})
    graph.readout = ReadoutSpec(products=())
    result = build_result_graph(run_experiment(graph))
    assert result.observations == ()
    assert result.edges == ()
