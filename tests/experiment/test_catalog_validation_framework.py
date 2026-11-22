import json
import random
from pathlib import Path

import pytest
from pydantic import ValidationError

from mrqlab_experiment.clinical import ClinicalProtocolRecipe
from mrqlab_experiment.clinical_catalog import list_protocol_recipes


BASELINE = Path(__file__).parent / "fixtures" / "protocol-catalog-337cd8a.json"


def test_existing_catalog_matches_frozen_337cd8a_baseline():
    baseline = json.loads(BASELINE.read_text())
    assert set(baseline) == {"brain_lesion_t2_tse", "knee_cartilage_meniscus_pd_t2_tse"}
    current = {r.id: r.model_dump(mode="json") for r in list_protocol_recipes()}
    for recipe_id, old_recipe in baseline.items():
        assert current[recipe_id] == old_recipe


@pytest.mark.parametrize("seed", range(30))
def test_catalog_contract_generated_roundtrip_and_duplicate_rejection(seed):
    rng = random.Random(seed)
    recipe = rng.choice(list_protocol_recipes())
    data = recipe.model_dump(mode="json")
    rng.shuffle(data["tissue_priors"]["tissues"])
    parsed = ClinicalProtocolRecipe.model_validate(data)
    assert ClinicalProtocolRecipe.model_validate_json(parsed.model_dump_json()) == parsed
    targets = data["tissue_priors"]["targets"]
    targets.append(dict(targets[0]))
    with pytest.raises(ValidationError, match="unique"):
        ClinicalProtocolRecipe.model_validate(data)
