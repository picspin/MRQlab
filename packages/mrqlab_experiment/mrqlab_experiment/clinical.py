from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NonEmpty = Annotated[str, Field(min_length=1)]
ParameterStateKind = Literal[
    "authored",
    "derived",
    "scanner_default",
    "estimated",
    "visual_only",
    "unsupported",
    "stale",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def reject_non_finite_numbers(cls, value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("numeric values must be finite")
        return value


class ClinicalQuestion(FrozenModel):
    anatomy: NonEmpty
    research_question: NonEmpty
    target_finding: NonEmpty
    contrast_mechanism: NonEmpty


class TissueRole(FrozenModel):
    tissue_id: NonEmpty
    rationale: NonEmpty


class Target(TissueRole):
    pass


class Reference(TissueRole):
    pass


class Confounder(TissueRole):
    pass


class TissuePrior(FrozenModel):
    id: NonEmpty = "tissue"
    label: NonEmpty = "Tissue"
    role: Literal["target", "reference", "background", "lumen", "contrast"] = "target"
    t1: float = Field(default=1.0, gt=0)
    t2: float = Field(default=.1, gt=0)
    t2_star: float | None = Field(default=None, gt=0)
    proton_density: float = Field(default=1.0, ge=0)
    flow_velocity_mps: float = 0.0
    exchange_rate_hz: float = Field(default=0.0, ge=0)
    pool_fraction: float = Field(default=1.0, ge=0, le=1.0)
    bound_pool: bool = False
    diffusion_adc_mm2_s: float | None = Field(default=None, ge=0)
    chemical_shift_ppm: float = 0.0


class TissuePriorSet(FrozenModel):
    id: NonEmpty
    version: NonEmpty
    tissues: tuple[TissuePrior, ...]
    targets: tuple[Target, ...] = ()
    references: tuple[Reference, ...] = ()
    confounders: tuple[Confounder, ...] = ()

    @model_validator(mode="after")
    def validate_roles(self):
        ids = [tissue.id for tissue in self.tissues]
        if len(ids) != len(set(ids)):
            raise ValueError("tissue ids must be unique")
        known = set(ids)
        for role in (*self.targets, *self.references, *self.confounders):
            if role.tissue_id not in known:
                raise ValueError(f"unknown tissue id {role.tissue_id!r}")
        return self


class ContrastMetric(FrozenModel):
    id: NonEmpty
    target_tissue_id: NonEmpty
    reference_tissue_id: NonEmpty
    metric: Literal["absolute_signal_difference", "signal_ratio", "normalized_cnr_proxy"]
    direction: Literal["maximize", "minimize", "target"]
    target_value: float | None = None
    weight: float = Field(gt=0)


class RobustnessScenario(FrozenModel):
    id: NonEmpty
    delta_b0_hz: tuple[float, float]
    b1_scale: tuple[float, float]
    motion_mm: tuple[float, float]
    t1_scale: tuple[float, float]
    t2_scale: tuple[float, float]

    @model_validator(mode="after")
    def ordered_bounds(self):
        for name in ("delta_b0_hz", "b1_scale", "motion_mm", "t1_scale", "t2_scale"):
            low, high = getattr(self, name)
            if not all(math.isfinite(v) for v in (low, high)) or low > high:
                raise ValueError(f"{name} must be finite ordered bounds")
        return self


class AcquisitionConstraint(FrozenModel):
    id: NonEmpty
    metric: Literal[
        "scan_time_s",
        "sar_relative",
        "resolution_mm",
        "coverage_mm",
        "echo_spacing_s",
        "bandwidth_hz",
    ]
    operator: Literal["le", "ge", "eq"]
    value: float
    unit: NonEmpty
    severity: Literal["hard", "soft"]


class ParameterState(FrozenModel):
    name: NonEmpty
    value: float | int | str | bool
    unit: NonEmpty
    state: ParameterStateKind
    source: NonEmpty


class ObjectiveVector(FrozenModel):
    terms: tuple[ContrastMetric, ...]

    @model_validator(mode="after")
    def unique_term_ids(self):
        ids = [term.id for term in self.terms]
        if len(ids) != len(set(ids)):
            raise ValueError("objective term ids must be unique")
        return self


class ScannerProfile(FrozenModel):
    id: NonEmpty
    version: NonEmpty
    b0_t: float = Field(gt=0)
    max_gradient_mt_m: float = Field(gt=0)
    max_slew_rate_t_m_s: float = Field(gt=0)
    gradient_raster_s: float = Field(gt=0)
    rf_raster_s: float = Field(gt=0)
    adc_raster_s: float = Field(gt=0)
    rf_dead_time_s: float = Field(ge=0)
    rf_ringdown_time_s: float = Field(ge=0)
    adc_dead_time_s: float = Field(ge=0)
    defaults: tuple[ParameterState, ...] = ()


class ClinicalProtocolRecipe(FrozenModel):
    id: NonEmpty
    version: NonEmpty
    vertical: Literal["brain_lesion_t2_tse", "knee_cartilage_meniscus_pd_t2_tse"]
    question: ClinicalQuestion
    tissue_priors: TissuePriorSet
    objective: ObjectiveVector
    robustness: tuple[RobustnessScenario, ...]
    constraints: tuple[AcquisitionConstraint, ...]
    scanner_profile: ScannerProfile
    experiment_recipe_id: NonEmpty

    @model_validator(mode="after")
    def objective_references_priors(self):
        known = {tissue.id for tissue in self.tissue_priors.tissues}
        for term in self.objective.terms:
            if term.target_tissue_id not in known or term.reference_tissue_id not in known:
                raise ValueError(f"objective term {term.id!r} references unknown tissue")
        return self
