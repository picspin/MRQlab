import numpy as np
import pytest

from mrqlab_experiment import build_clinical_recipe, list_clinical_recipes, plan_experiment, run_experiment, validate_experiment


def test_amine_recipe_is_listed_and_not_an_amide_alias():
    assert "cest_amine_z_spectrum" in list_clinical_recipes()
    graph = build_clinical_recipe("cest_amine_z_spectrum")
    amide = build_clinical_recipe("cest_amide_z_spectrum")
    assert graph.id == "recipe:cest_amine_z_spectrum"
    assert "amine" in graph.name.lower()
    assert "amide" not in graph.name.lower()
    assert graph.tissue[1].id == "amine"
    assert graph.tissue[1].chemical_shift_ppm == pytest.approx(2.0)
    assert amide.tissue[1].id == "amide"
    assert amide.tissue[1].chemical_shift_ppm == pytest.approx(3.5)
    assert graph.sequence.metadata["cest"]["mode"] == "cw"
    assert graph.engine.preferred == "epg-x"
    assert graph.readout.products == ("z_spectrum", "mtr_asym")


def test_amine_recipe_runs_epgx_and_dips_at_two_ppm_not_amide():
    graph = build_clinical_recipe("cest_amine_z_spectrum")
    assert validate_experiment(graph).valid
    assert plan_experiment(graph).engine == "epg-x"
    run = run_experiment(graph)
    offsets = np.asarray(run.sim_result.z_spectrum["offset_ppm"])
    z = np.asarray(run.sim_result.z_spectrum["Z"])
    plus_amine = z[np.isclose(offsets, 2.0)][0]
    minus_amine = z[np.isclose(offsets, -2.0)][0]
    plus_amide = z[np.isclose(offsets, 3.5)][0]
    assert plus_amine < minus_amine
    assert plus_amine < plus_amide
    assert "cest_z_spectrum_applied" in run.sim_result.meta["assumptions"]


def test_unknown_cest_solute_still_fails_closed():
    with pytest.raises(ValueError, match="unknown clinical recipe"):
        build_clinical_recipe("cest_guanidinium_z_spectrum")
