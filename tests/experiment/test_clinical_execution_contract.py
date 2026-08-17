from typing import Any, Literal
import pytest

from mrqlab_experiment import build_preset, plan_experiment, validate_experiment
from mrqlab_experiment.models import (
    ExperimentGraph,
    TissueModel,
    PhysiologyModel,
    ScannerModel,
    DisturbanceModel,
)
from mrqlab_experiment.capabilities import EngineValidity, REPRESENTATIONS


def test_clinical_reality_models_exist_and_decouple_sample_and_hardware():
    tissue = TissueModel(t1=1.2, t2=0.08, proton_density=0.9, flow_velocity_mps=0.25)
    physio = PhysiologyModel(cardiac_phase=0.2, rr_interval_s=0.8, respiratory_phase=0.5)
    scanner = ScannerModel(b0_t=3.0, max_gradient_mt_m=45.0, max_slew_rate_t_m_s=200.0)
    disturbance = DisturbanceModel(kind="slice_profile", enabled=True, parameters={"thickness_factor": 1.1})

    assert tissue.flow_velocity_mps == 0.25
    assert physio.cardiac_phase == 0.2
    assert scanner.max_gradient_mt_m == 45.0
    assert disturbance.kind == "slice_profile"


def test_engine_validity_matrix_declared_for_all_representations():
    for name, rep in REPRESENTATIONS.items():
        assert hasattr(rep, "validity")
        assert isinstance(rep.validity, EngineValidity)

    epg_validity = REPRESENTATIONS["epg"].validity
    assert epg_validity.flow in ("unsupported", "approximate")
    assert epg_validity.spatial_encoding in ("none", "limited")

    bloch_validity = REPRESENTATIONS["bloch"].validity
    assert bloch_validity.spatial_encoding == "full"


def test_execution_plan_contains_rich_clinical_execution_fields():
    graph = build_preset("dark-blood-tse", {"te": 0.02, "tr": 0.1, "echoes": 4})
    plan = plan_experiment(graph)

    assert hasattr(plan, "fingerprint")
    assert len(plan.fingerprint) == 64  # sha256 hex
    assert hasattr(plan, "requested_observations")
    assert hasattr(plan, "approximations")
    assert hasattr(plan, "differentiable")
    assert hasattr(plan, "stale_dependencies")
