from mrqlab_experiment import build_preset, plan_experiment, run_experiment, validate_experiment
from mrqlab_experiment.models import ReadoutSpec
from mrqlab_experiment.observations import build_result_graph


def test_tse_plan_selects_epg_from_template_metadata_not_preferred_field():
    graph = build_preset("dark-blood-tse", {"te": 0.02, "tr": 0.1, "echoes": 2})
    assert graph.engine.preferred is None
    plan = plan_experiment(graph)
    assert plan.engine == "epg"
    assert plan.representation == "epg"
    assert plan.preferred == "epg"
    run = run_experiment(graph)
    assert run.plan.engine == "epg"
    assert run.sim_result.meta["engine"] == "epg"


def test_explicit_preferred_override_still_wins_when_capabilities_allow():
    graph = build_preset("dark-blood-tse", {"te": 0.02, "tr": 0.1, "echoes": 2})
    graph.engine.preferred = "bloch"
    plan = plan_experiment(graph)
    assert plan.engine == "bloch"
    assert run_experiment(graph).sim_result.meta["engine"] == "bloch"


def test_shaped_rf_configuration_plan_selects_hybrid():
    graph = build_preset("dark-blood-tse")
    graph.engine.required_capabilities = frozenset({"shaped_rf", "configuration_states"})
    report = validate_experiment(graph)
    assert report.valid is True
    assert plan_experiment(graph).engine == "hybrid"


def test_run_experiment_does_not_alias_caller_graph():
    graph = build_preset("spin-echo", {"te": 0.02, "tr": 0.1})
    run = run_experiment(graph)
    assert run.experiment is not graph
    graph.readout = ReadoutSpec(products=())
    result = build_result_graph(run)
    assert [item.kind for item in result.observations] == ["signal", "k_trajectory", "image"]
