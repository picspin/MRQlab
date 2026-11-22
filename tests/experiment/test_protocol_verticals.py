import pytest

from mrqlab_experiment import build_protocol_experiment
from mrqlab_experiment.clinical_catalog import get_protocol_recipe, list_protocol_recipes


def test_catalog_contains_four_verticals():
    recipes = list_protocol_recipes()
    assert [recipe.id for recipe in recipes] == [
        "brain_lesion_t2_tse",
        "knee_cartilage_meniscus_pd_t2_tse",
        "abdomen_liver_relaxation_gre",
        "heart_myocardium_blood_gre",
    ]
    assert {recipe.experiment_recipe_id for recipe in recipes} == {"brain_t2_tse", "msk_knee_tse", "abdomen_dixon_gre", "cardiac_cine_gre"}


def test_brain_and_knee_roles_are_clinically_explicit():
    brain = get_protocol_recipe("brain_lesion_t2_tse")
    knee = get_protocol_recipe("knee_cartilage_meniscus_pd_t2_tse")
    assert [item.tissue_id for item in brain.tissue_priors.targets] == ["lesion"]
    assert [item.tissue_id for item in brain.tissue_priors.references] == ["white_matter"]
    assert {item.tissue_id for item in brain.tissue_priors.confounders} == {"gray_matter", "csf"}
    assert [item.tissue_id for item in knee.tissue_priors.targets] == ["cartilage", "meniscal_tear"]
    assert {item.tissue_id for item in knee.tissue_priors.confounders} == {
        "joint_fluid",
        "marrow_fat",
    }


def test_parked_verticals_are_not_promoted_into_the_a_catalog():
    for recipe_id in ("angio_tof_gre", "cest_amide_z_spectrum"):
        with pytest.raises(KeyError, match="not a Milestone A protocol recipe"):
            get_protocol_recipe(recipe_id)


@pytest.mark.parametrize("recipe_id,target,reference", [
    ("abdomen_liver_relaxation_gre", "focal_fatty_liver", "liver"),
    ("heart_myocardium_blood_gre", "myocardium", "blood"),
])
def test_new_gre_verticals_run_with_named_tissues_and_replay(recipe_id, target, reference):
    from mrqlab_experiment import build_result_graph, plan_experiment, run_experiment

    graph = build_protocol_experiment(recipe_id)
    recipe = graph.clinical_recipe
    assert graph.sequence.template == "GRE"
    assert recipe.tissue_priors.targets[0].tissue_id == target
    assert recipe.tissue_priors.references[0].tissue_id == reference
    assert recipe.objective.terms[0].target_tissue_id == target
    assert recipe.objective.terms[0].reference_tissue_id == reference
    plan = plan_experiment(graph)
    assert plan.fingerprint == plan_experiment(graph.model_copy(deep=True)).fingerprint
    assert plan.clinical_recipe_id == recipe_id
    observations = {o.id: o for o in build_result_graph(run_experiment(graph)).observations}
    assert observations["tissue_contrast"].data["pairs"][0]["target_tissue_id"] == target
    assert observations["objective_score"].data is not None


@pytest.mark.parametrize("recipe_id", ["abdomen_liver_relaxation_gre", "heart_myocardium_blood_gre"])
def test_new_protocol_name_and_bandwidth_match_research_scope(recipe_id):
    from mrqlab_experiment import plan_experiment

    graph = build_protocol_experiment(recipe_id)
    plan = plan_experiment(graph)
    bandwidth = next(p for p in plan.parameters if p.name == "adc_bandwidth_hz")
    default = next(p for p in graph.clinical_recipe.scanner_profile.defaults if p.name == "adc_bandwidth_hz")
    assert bandwidth.value == default.value
    assert bandwidth.source == "ExperimentGraph.effective_scanner"
    assert graph.scanner_model.adc_bandwidth_hz == default.value
    assert "dixon" not in graph.name.lower()
    assert "cine" not in graph.name.lower()


def test_protocol_recipe_extends_existing_experiment_recipe():
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    assert graph.id == "recipe:brain_t2_tse"
    assert graph.clinical_recipe.id == "brain_lesion_t2_tse"
    assert graph.sequence.template == "TSE"
    assert [item.model_dump() for item in graph.tissue] == [
        item.model_dump() for item in graph.clinical_recipe.tissue_priors.tissues
    ]
    assert graph.effective_scanner.b0_t == graph.clinical_recipe.scanner_profile.b0_t
