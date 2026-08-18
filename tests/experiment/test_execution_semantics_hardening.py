import pytest
import numpy as np

from mrqlab_experiment import (
    ExperimentGraph,
    TissueModel,
    PhysiologyModel,
    ScannerModel,
    build_clinical_recipe,
    build_result_graph,
    plan_experiment,
    validate_experiment,
    run_experiment,
)
from mrqlab_experiment.models import ReadoutSpec, TemplateRef
from mrqlab_experiment.objectives import (
    ObjectiveFunction,
    ClinicalCNRTerm,
    evaluate_objective,
    evaluate_multi_tissue_contrast,
)
from mrqlab_experiment.pulse import (
    PulseDefinition,
    PulseResponse,
    PulseCompiler,
    compile_pulse,
)


def test_unified_scanner_model_runtime_consumption():
    # 1. ScannerModel is consumed uniformly by run_experiment and contrast evaluators
    scanner_model = ScannerModel(
        b0_t=3.0,
        gradient_scale=1.2,
        max_gradient_mt_m=80.0,
        max_slew_rate_t_m_s=200.0,
        adc_bandwidth_hz=62500.0,
    )
    graph = ExperimentGraph(
        id="scanner_unification_test",
        name="Scanner Unification Test",
        intent="clinical_contrast",
        nodes=(),
        edges=(),
        sequence=TemplateRef(template="SE", params={"te": 0.01, "tr": 1.0}),
        scanner=scanner_model,  # Direct ScannerModel instance on scanner
    )
    assert graph.effective_scanner.b0_t == 3.0
    run = run_experiment(graph)
    assert run.sim_result is not None


def test_tissue_model_identity_and_semantic_objective_terms():
    # 2. Tissue identity (id, label, role) & target/reference named objectives
    wm = TissueModel(
        id="white_matter",
        label="White Matter",
        role="reference",
        t1=0.9,
        t2=0.08,
        proton_density=0.75,
    )
    lesion = TissueModel(
        id="ms_lesion",
        label="MS Lesion",
        role="target",
        t1=1.4,
        t2=0.12,
        proton_density=0.90,
    )
    graph = ExperimentGraph(
        id="ms_brain_test",
        name="MS Brain Test",
        intent="clinical_contrast",
        nodes=(),
        edges=(),
        sequence=TemplateRef(template="TSE", params={"echo_count": 8, "te": 0.012, "tr": 2.0}),
        tissue=(wm, lesion),
    )
    contrast_res = evaluate_multi_tissue_contrast(graph)
    assert "contrast_difference" in contrast_res
    assert "signal_ratio" in contrast_res
    assert "normalized_cnr_proxy" in contrast_res
    assert "tissues" in contrast_res
    assert contrast_res["tissues"][0]["id"] == "white_matter"
    assert contrast_res["tissues"][1]["id"] == "ms_lesion"

    # Named objective term (target="ms_lesion", reference="white_matter")
    obj = ObjectiveFunction(
        kind="clinical_cnr",
        cnr_term=ClinicalCNRTerm(
            target_tissue_id="ms_lesion",
            reference_tissue_id="white_matter",
            metric="contrast_difference",
            target=0.3,
        ),
    )
    score = evaluate_objective(obj, {"multi_tissue_contrast": contrast_res})
    assert isinstance(score, float)


def test_execution_plan_declares_physics_modeling_status():
    # 4. Honesty in ExecutionPlan: physics status of declared tissue/physiology features
    tissue = TissueModel(
        id="artery",
        label="Carotid Artery",
        role="target",
        t1=1.2,
        t2=0.08,
        flow_velocity_mps=0.25,
    )
    graph = ExperimentGraph(
        id="flow_status_test",
        name="Flow Status Test",
        intent="clinical_contrast",
        nodes=(),
        edges=(),
        sequence=TemplateRef(template="TSE", params={"echo_count": 4, "te": 0.01, "tr": 1.0}),
        tissue=tissue,
    )
    plan = plan_experiment(graph)
    assert "physics_status" in plan.model_dump()
    assert plan.physics_status.get("flow") == "declared_approximate_in_epg"


def test_pulse_response_and_epg_transition_propagator():
    # 5. PulseResponse unified structure and epg_transition branch
    pulse = PulseDefinition(
        kind="shaped_sinc",
        flip_angle_deg=90.0,
        phase_deg=0.0,
        duration_s=0.002,
        time_bandwidth=4.0,
        slice_thickness_m=0.005,
    )
    response = PulseCompiler.analyze(pulse)
    assert isinstance(response, PulseResponse)
    assert response.flip_angle_deg == 90.0
    assert response.slice_thickness_m == 0.005
    assert response.slice_profile is not None
    assert response.frequency_response is not None

    epg_prop = compile_pulse(pulse, method="epg_transition")
    mat = epg_prop.transition_matrix()
    assert mat.shape == (3, 3)
