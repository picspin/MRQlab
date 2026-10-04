import math

import pytest
from pydantic import ValidationError

from mrqlab_experiment.clinical import (
    AcquisitionConstraint,
    ClinicalProtocolRecipe,
    ClinicalQuestion,
    Confounder,
    ContrastMetric,
    ObjectiveVector,
    ParameterState,
    Reference,
    RobustnessScenario,
    ScannerProfile,
    Target,
    TissuePrior,
    TissuePriorSet,
)


def _priors() -> TissuePriorSet:
    return TissuePriorSet(
        id="brain-lesion-v1",
        version="1.0.0",
        tissues=(
            TissuePrior(id="lesion", label="Lesion", role="target", t1=1.4, t2=.12),
            TissuePrior(id="wm", label="White matter", role="reference", t1=.9, t2=.08),
            TissuePrior(id="csf", label="CSF", role="background", t1=4.0, t2=2.0),
        ),
        targets=(Target(tissue_id="lesion", rationale="T2 hyperintense focus"),),
        references=(Reference(tissue_id="wm", rationale="normal-appearing white matter"),),
        confounders=(Confounder(tissue_id="csf", rationale="long-T2 fluid blooming"),),
    )


def test_clinical_contract_is_frozen_and_round_trips():
    priors = _priors()
    scanner = ScannerProfile(
        id="research-3t",
        version="1.0.0",
        b0_t=3.0,
        max_gradient_mt_m=80.0,
        max_slew_rate_t_m_s=200.0,
        gradient_raster_s=10e-6,
        rf_raster_s=1e-6,
        adc_raster_s=1e-7,
        rf_dead_time_s=100e-6,
        rf_ringdown_time_s=30e-6,
        adc_dead_time_s=10e-6,
        defaults=(
            ParameterState(
                name="adc_bandwidth_hz",
                value=62500.0,
                unit="Hz",
                state="scanner_default",
                source="research-3t@1.0.0",
            ),
        ),
    )
    recipe = ClinicalProtocolRecipe(
        id="brain_lesion_t2_tse",
        version="1.0.0",
        vertical="brain_lesion_t2_tse",
        question=ClinicalQuestion(
            anatomy="brain",
            research_question="Maximize lesion-to-WM T2 contrast",
            target_finding="T2-hyperintense lesion",
            contrast_mechanism="T2 TSE",
        ),
        tissue_priors=priors,
        objective=ObjectiveVector(
            terms=(
                ContrastMetric(
                    id="lesion-wm",
                    target_tissue_id="lesion",
                    reference_tissue_id="wm",
                    metric="normalized_cnr_proxy",
                    direction="maximize",
                    weight=1.0,
                ),
            )
        ),
        robustness=(
            RobustnessScenario(
                id="routine-3t",
                delta_b0_hz=(-50.0, 50.0),
                b1_scale=(.85, 1.15),
                motion_mm=(0.0, 1.0),
                t1_scale=(.9, 1.1),
                t2_scale=(.9, 1.1),
            ),
        ),
        constraints=(
            AcquisitionConstraint(
                id="scan-time",
                metric="scan_time_s",
                operator="le",
                value=300.0,
                unit="s",
                severity="hard",
            ),
        ),
        scanner_profile=scanner,
        experiment_recipe_id="brain_t2_tse",
    )
    assert ClinicalProtocolRecipe.model_validate_json(recipe.model_dump_json()) == recipe
    with pytest.raises(ValidationError, match="frozen"):
        recipe.version = "2.0.0"
    with pytest.raises(ValidationError, match="frozen"):
        recipe.tissue_priors.tissues[0].t2 = .5


def test_tissue_roles_reject_dangling_and_duplicate_ids():
    with pytest.raises(ValidationError, match="tissue ids must be unique"):
        TissuePriorSet(id="bad", version="1", tissues=(TissuePrior(id="x"), TissuePrior(id="x")))
    with pytest.raises(ValidationError, match="unknown tissue id 'missing'"):
        _priors().model_copy(
            update={"confounders": (Confounder(tissue_id="missing", rationale="invalid"),)}
        ).model_validate(
            {
                **_priors().model_dump(),
                "confounders": [{"tissue_id": "missing", "rationale": "invalid"}],
            }
        )


def test_numeric_values_are_finite_and_units_are_explicit():
    with pytest.raises(ValidationError, match="finite"):
        AcquisitionConstraint(
            id="bad",
            metric="scan_time_s",
            operator="le",
            value=math.nan,
            unit="s",
            severity="hard",
        )
    with pytest.raises(ValidationError):
        ParameterState(name="te", value=.1, unit="", state="authored", source="user")
