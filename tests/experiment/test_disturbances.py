from mrqlab_experiment import build_preset, run_experiment, validate_experiment
from mrqlab_experiment.observations import build_result_graph
from mrqlab_experiment.disturbances import Disturbance, DisturbanceStack, stack_from_reality


def test_reality_slider_maps_to_reproducible_stack():
    assert stack_from_reality(0).items == ()
    assert [item.kind for item in stack_from_reality(50).items] == ["thermal_noise", "b0_map"]


def test_slice_profile_selects_ssepg_and_runs():
    graph = build_preset("dark-blood-tse")
    graph.disturbances = DisturbanceStack(
        items=(
            Disturbance(
                id="slice",
                kind="slice_profile",
                domain="sequence",
                parameters={"samples": 32},
            ),
        )
    )
    report = validate_experiment(graph)
    assert report.valid is True
    run = run_experiment(graph)
    assert run.plan.engine == run.plan.representation == "ssepg"
    result = build_result_graph(run)
    assert any(item.kind == "slice_profile" for item in result.observations)


def test_reality_b0_map_selects_pdg_and_runs():
    graph = build_preset("dark-blood-tse")
    graph.disturbances = stack_from_reality(50)
    assert validate_experiment(graph).valid is True
    run = run_experiment(graph)
    assert run.plan.engine == run.plan.representation == "pdg"
