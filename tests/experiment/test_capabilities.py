import pytest

from mrqlab_experiment import build_preset, validate_experiment
from mrqlab_experiment.capabilities import CapabilityMismatch, select_representation


def test_capability_selection_is_set_inclusion_not_inheritance():
    selected = select_representation(frozenset({"configuration_states", "hard_rf"}), "epg")
    assert selected.name == "epg"
    assert selected.supports >= {"configuration_states", "hard_rf"}


def test_missing_shaped_rf_fails_closed_with_ssepg_explanation():
    graph = build_preset("dark-blood-tse")
    graph.engine.required_capabilities = frozenset({"configuration_states", "shaped_rf"})
    report = validate_experiment(graph)
    assert report.valid is False
    assert report.errors[0].code == "capability_mismatch"
    assert "ssEPG" in report.errors[0].message


def test_no_base_simulator_skill_tree_exists():
    with pytest.raises(CapabilityMismatch):
        select_representation(frozenset({"exchange"}), "epg")
