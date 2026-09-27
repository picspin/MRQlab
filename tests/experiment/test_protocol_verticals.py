import pytest

from mrqlab_experiment.clinical_catalog import get_protocol_recipe, list_protocol_recipes


def test_catalog_contains_exactly_the_two_locked_verticals():
    recipes = list_protocol_recipes()
    assert [recipe.id for recipe in recipes] == [
        "brain_lesion_t2_tse",
        "knee_cartilage_meniscus_pd_t2_tse",
    ]
    assert {recipe.experiment_recipe_id for recipe in recipes} == {"brain_t2_tse", "msk_knee_tse"}


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
    for recipe_id in ("abdomen_dixon_gre", "angio_tof_gre", "cest_amide_z_spectrum"):
        with pytest.raises(KeyError, match="not a Milestone A protocol recipe"):
            get_protocol_recipe(recipe_id)
