from typing import Any
from fastapi import HTTPException
from pydantic import BaseModel, Field

from mrqlab_experiment import (
    ExperimentGraph,
    build_clinical_recipe,
    build_preset,
    build_result_graph,
    list_clinical_recipes,
    run_experiment,
    validate_experiment,
)
from mrqlab_experiment.objectives import evaluate_multi_tissue_contrast


class TissueSignalRequest(BaseModel):
    experiment: ExperimentGraph | None = None
    recipe_id: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class CustomRecipeRequest(BaseModel):
    id: str
    experiment: ExperimentGraph


# In-memory store for custom scenarios / recipes in v0.43
_CUSTOM_RECIPES: dict[str, ExperimentGraph] = {}


def compute_tissue_signals(graph: ExperimentGraph) -> dict[str, Any]:
    """Compute exact tissue-level signals and relative contrast values via the authoritative physics kernel."""
    res = evaluate_multi_tissue_contrast(graph)
    # Extract mean magnitude for each tissue
    signals_by_id = {}
    for info, sig_list in zip(res["tissues"], res["tissue_signals"]):
        mag = sum(abs(complex(v["real"], v["imag"]) if isinstance(v, dict) else v) for v in sig_list) / max(1, len(sig_list))
        signals_by_id[info["id"]] = float(mag)

    return {
        "tissues": res["tissues"],
        "signals": signals_by_id,
        "contrast_difference": res["contrast_difference"],
        "normalized_cnr_proxy": res["normalized_cnr_proxy"],
        "signal_ratio": res["signal_ratio"],
    }
