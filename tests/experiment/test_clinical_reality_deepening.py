import pytest
from pydantic import ValidationError

from mrqlab_experiment import (
    ExperimentGraph,
    ExecutionPlan,
    TissueModel,
    PhysiologyModel,
    ScannerModel,
    DisturbanceModel,
    plan_experiment,
    validate_experiment,
    run_experiment,
    build_preset,
)
from mrqlab_experiment.models import TemplateRef


def test_experiment_graph_accepts_clinical_reality_models():
    tissue = TissueModel(
        t1=1.2,
        t2=0.08,
        t2_star=0.04,
        proton_density=0.9,
        flow_velocity_mps=0.15,
        exchange_rate_hz=20.0,
        pool_fraction=0.1,
    )
    physio = PhysiologyModel(
        cardiac_phase=0.3,
        rr_interval_s=0.85,
        respiratory_phase=0.5,
    )
    scanner_model = ScannerModel(
        b0_t=3.0,
        max_gradient_mt_m=80.0,
        max_slew_rate_t_m_s=200.0,
        adc_bandwidth_hz=100000.0,
    )
    graph = ExperimentGraph(
        id="clinical_dark_blood_test",
        name="Clinical Dark Blood Test",
        intent="clinical_contrast",
        nodes=(),
        edges=(),
        sequence=TemplateRef(template="TSE", params={"echo_count": 8, "te": 0.012, "tr": 2.0}),
        tissue=tissue,
        physiology=physio,
        scanner_model=scanner_model,
    )
    assert graph.tissue == tissue
    assert graph.physiology == physio
    assert graph.scanner_model == scanner_model


def test_execution_plan_includes_cost_estimate_and_validity_checks():
    graph = build_preset("spin-echo")
    plan = plan_experiment(graph)
    assert hasattr(plan, "cost_estimate")
    assert isinstance(plan.cost_estimate, float)
    assert plan.cost_estimate > 0.0
    assert plan.validity is not None


def test_tissue_model_compilation_to_phantom():
    tissue = TissueModel(
        t1=1.5,
        t2=0.1,
        proton_density=0.8,
        flow_velocity_mps=0.0,
    )
    graph = ExperimentGraph(
        id="tissue_phantom_test",
        name="Tissue Phantom Test",
        intent="clinical_contrast",
        nodes=(),
        edges=(),
        sequence=TemplateRef(template="SE", params={"te": 0.01, "tr": 1.0}),
        tissue=tissue,
    )
    report = validate_experiment(graph)
    assert report.valid is True
    run = run_experiment(graph)
    assert run.sim_result is not None
    assert run.sim_result.signal is not None


def test_unsupported_flow_or_exchange_validity_fails_closed():
    # EPG has validity.exchange = "unsupported"
    tissue = TissueModel(
        t1=1.2,
        t2=0.08,
        exchange_rate_hz=50.0,
        pool_fraction=0.2,
    )
    graph = ExperimentGraph(
        id="exchange_epg_test",
        name="Exchange EPG Test",
        intent="clinical_contrast",
        nodes=(),
        edges=(),
        sequence=TemplateRef(template="TSE", params={"echo_count": 4, "te": 0.01, "tr": 1.0}),
        tissue=tissue,
    )
    report = validate_experiment(graph)
    assert report.valid is False
    assert any("exchange" in err.message.lower() or "exchange" in err.code.lower() for err in report.errors)
