import pytest
import numpy as np

from mrqlab_experiment import (
    ExperimentGraph,
    TissueModel,
    PhysiologyModel,
    ScannerModel,
    build_clinical_recipe,
    build_result_graph,
    run_experiment,
    plan_experiment,
)
from mrqlab_experiment.models import ReadoutSpec, TemplateRef
from mrqlab_experiment.objectives import (
    ObjectiveFunction,
    ClinicalCNRTerm,
    evaluate_objective,
    evaluate_multi_tissue_contrast,
)


def test_multi_tissue_contrast_calculation():
    # Two tissues: vessel wall (T1=1.0, T2=0.06) vs blood (T1=1.4, T2=0.20)
    tissues = (
        TissueModel(t1=1.0, t2=0.06, proton_density=0.8),
        TissueModel(t1=1.4, t2=0.20, proton_density=1.0),
    )
    graph = ExperimentGraph(
        id="tse_contrast_test",
        name="TSE Contrast Test",
        intent="clinical_contrast",
        nodes=(),
        edges=(),
        sequence=TemplateRef(template="TSE", params={"echo_count": 8, "te": 0.012, "tr": 1.5}),
        tissue=tissues,
    )
    contrast_res = evaluate_multi_tissue_contrast(graph)
    assert "tissue_signals" in contrast_res
    assert len(contrast_res["tissue_signals"]) == 2
    assert "cnr" in contrast_res
    assert isinstance(contrast_res["cnr"], float)


def test_clinical_cnr_objective_function():
    obj = ObjectiveFunction(
        kind="clinical_cnr",
        cnr_term=ClinicalCNRTerm(
            tissue_a_index=0,
            tissue_b_index=1,
            metric="difference",
            target=0.5,
        ),
    )
    signals = [
        np.array([0.8 + 0.0j, 0.6 + 0.0j]),
        np.array([0.2 + 0.0j, 0.1 + 0.0j]),
    ]
    score = evaluate_objective(obj, {"tissue_signals": signals})
    assert score is not None
    assert isinstance(score, float)


def test_result_graph_emits_tissue_contrast_observation():
    graph = build_clinical_recipe("dark_blood_vessel_wall_tse")
    graph.readout = ReadoutSpec(products=("signal", "tissue_contrast", "image"))
    run = run_experiment(graph)
    result_graph = build_result_graph(run)
    obs_kinds = [o.kind for o in result_graph.observations]
    assert "tissue_contrast" in obs_kinds
    contrast_obs = next(o for o in result_graph.observations if o.kind == "tissue_contrast")
    assert "cnr" in contrast_obs.data
    assert "tissue_signals" in contrast_obs.data
