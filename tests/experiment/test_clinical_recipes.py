import pytest
import numpy as np

from mrqlab_experiment import (
    ExperimentGraph,
    TissueModel,
    PhysiologyModel,
    ScannerModel,
    build_preset,
    plan_experiment,
    validate_experiment,
    run_experiment,
)
from mrqlab_experiment.presets import (
    build_clinical_recipe,
    list_clinical_recipes,
    ClinicalRecipeSpec,
)


def test_list_clinical_recipes_contains_expected_benchmarks():
    recipes = list_clinical_recipes()
    assert "dark_blood_vessel_wall_tse" in recipes
    assert "cardiac_cine_gre" in recipes
    assert "brain_t2_tse" in recipes


def test_build_dark_blood_vessel_wall_recipe_structure():
    graph = build_clinical_recipe("dark_blood_vessel_wall_tse")
    assert graph.intent == "clinical_contrast"
    assert graph.tissue is not None
    # Check multi-tissue definition (vessel wall + lumen blood)
    if isinstance(graph.tissue, tuple):
        assert len(graph.tissue) >= 2
    assert graph.physiology is not None
    # Validate and plan
    report = validate_experiment(graph)
    assert report.valid is True
    plan = plan_experiment(graph)
    assert plan.engine == "epg"
    assert plan.validity.steady_state == "supported"


def test_build_cardiac_cine_recipe_structure():
    graph = build_clinical_recipe("cardiac_cine_gre")
    assert graph.intent == "clinical_contrast"
    assert graph.physiology is not None
    assert graph.physiology.cardiac_phase >= 0.0
    report = validate_experiment(graph)
    assert report.valid is True
    plan = plan_experiment(graph)
    assert plan.engine == "bloch"


def test_clinical_recipe_execution_generates_valid_result_graph():
    graph = build_clinical_recipe("brain_t2_tse")
    run = run_experiment(graph)
    assert run.sim_result is not None
    assert run.sim_result.signal is not None
    assert len(run.sim_result.signal) > 0
