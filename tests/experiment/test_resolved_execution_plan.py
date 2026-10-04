import pytest
from pydantic import ValidationError

from mrqlab_experiment import build_protocol_experiment, plan_experiment


def test_protocol_plan_resolves_units_sources_and_versions():
    plan = plan_experiment(build_protocol_experiment("brain_lesion_t2_tse"))
    states = {item.name: item for item in plan.parameters}
    assert plan.scanner_profile == "research-3t@1.0.0"
    assert plan.tissue_prior_set == "brain-lesion-t2-priors@1.0.0"
    assert states["te"].unit == "s"
    assert states["te"].state == "authored"
    assert states["b0_t"].unit == "T"
    assert states["b0_t"].state == "scanner_default"
    assert states["max_work"].unit == "work_unit"
    assert all(item.unit for item in plan.parameters)


def test_resolved_plan_is_deeply_immutable_and_detached_from_caller():
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    plan = plan_experiment(graph)
    original = plan.model_dump(mode="json")
    graph.sequence.params["te"] = .5
    assert plan.model_dump(mode="json") == original
    with pytest.raises(ValidationError, match="frozen"):
        plan.engine = "bloch"
    with pytest.raises(TypeError, match="immutable"):
        plan.options["epg_kmax"] = 99
    with pytest.raises(TypeError, match="immutable"):
        plan.experiment_snapshot["sequence"]["params"]["te"] = .5


def test_fingerprint_is_canonical_and_changes_with_resolved_input():
    first = build_protocol_experiment("brain_lesion_t2_tse")
    second = build_protocol_experiment("brain_lesion_t2_tse")
    second.engine.options = {"return_configurations": True, "epg_kmax": 8}
    first.engine.options = {"epg_kmax": 8, "return_configurations": True}
    assert plan_experiment(first).fingerprint == plan_experiment(second).fingerprint
    second.sequence.params["te"] = .02
    assert plan_experiment(first).fingerprint != plan_experiment(second).fingerprint
