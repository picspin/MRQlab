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


def test_objective_score_without_objective_fails_closed():
    graph = build_preset("spin-echo", {"te": 0.02, "tr": 0.1})
    graph.readout = ReadoutSpec(products=("objective_score",))
    with pytest.raises(ValueError, match="objective"):
        build_result_graph(run_experiment(graph))


def test_snapshot_products_fail_closed_while_collection_is_disabled():
    graph = build_preset("spin-echo", {"te": 0.02, "tr": 0.1})
    graph.readout = ReadoutSpec(products=("magnetization",))
    with pytest.raises(ValueError, match="snapshot"):
        build_result_graph(run_experiment(graph))


def test_provenance_representation_comes_from_plan_not_sim_meta():
    from dataclasses import replace

    graph = build_preset("spin-echo", {"te": 0.02, "tr": 0.1})
    run = run_experiment(graph)
    run.plan.representation = "spectral"
    run.sim_result = replace(run.sim_result, meta={**run.sim_result.meta, "engine": "bloch"})
    result = build_result_graph(run)
    assert result.observations[0].provenance.representation == "spectral"
    assert result.observations[0].provenance.engine == "bloch"
