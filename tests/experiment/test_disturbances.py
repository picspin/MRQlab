from mrqlab_experiment import build_preset, validate_experiment
from mrqlab_experiment.disturbances import Disturbance, DisturbanceStack, stack_from_reality


def test_reality_slider_maps_to_reproducible_stack():
    assert stack_from_reality(0).items == ()
    assert [item.kind for item in stack_from_reality(50).items] == ["thermal_noise", "b0_map"]


def test_slice_profile_teaches_ssepg_reselection_and_fails_closed():
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
    assert report.valid is False
    assert report.errors[0].code == "unavailable_representation"
    assert "EPG → ssEPG" in report.errors[0].message
