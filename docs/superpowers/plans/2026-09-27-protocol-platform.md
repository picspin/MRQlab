# Protocol Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend MRQLab's experiment kernel into a research-use-only MRI contrast and protocol engineering platform with an immutable clinical execution contract, a later executable-sequence lowering path, and a later licensed local-compute gateway.

**Architecture:** Preserve `ExperimentGraph`, synchronous `POST /experiments/run*`, the existing physics microkernel, and typed `Observation` provenance. Add the clinical contract and immutable `ResolvedExecutionPlan` first; only after its review add `LogicalSequenceIR → ExecutableSequenceIR → ExportIR`; only after a second review add an `ExecutionProvider`-based local job gateway where capability and entitlement are separate and licensing never enters physics operators.

**Tech Stack:** Python >=3.11, Pydantic >=2, NumPy >=1.26, FastAPI >=0.110, pytest >=8; Next.js 14.2.5, React 18.3.1, TypeScript >=5.5, Vitest, jsdom, Testing Library; existing npm lockfile; `uv` for Python environment management. Milestone C's Ed25519 verifier requires separately approved `cryptography>=46,<47` before that task executes.

**Spec:** `docs/superpowers/specs/2026-09-27-protocol-platform.md`

**Existing files to touch:** `packages/mrqlab_experiment/mrqlab_experiment/models.py`, `packages/mrqlab_experiment/mrqlab_experiment/presets.py`, `packages/mrqlab_experiment/mrqlab_experiment/kernel.py`, `packages/mrqlab_experiment/mrqlab_experiment/observations.py`, `packages/mrqlab_experiment/mrqlab_experiment/__init__.py`, `services/api/mrqlab_api/main.py`, `apps/web/components/workbench/WorkbenchCockpit.tsx`, `apps/web/lib/workbench-types.ts`, `docs/ARCHITECTURE.md`, `docs/PHYSICS.md`, `docs/ROADMAP.md`, and `pyproject.toml`. New files are listed in the file map below.

## Global Constraints

- Product position is exactly: research-use-only MRI contrast and protocol engineering platform.
- Keep teaching Explore. Do not claim scanner control, diagnostic clinical decision support, pulse safety, or clinical readiness.
- Product layers remain Explore / Protocol Studio / Compute / Export / Enterprise Control Plane.
- Tier 0 browser preview, Tier 1 in-process NumPy, and Tier 2 local high-fidelity share `ExperimentGraph`, `ResolvedExecutionPlan`, `Observation`, and provenance.
- Keep `POST /experiments/run` and `POST /experiments/run-from-recipe` synchronous; Tier 2 uses a new job/provider path.
- Capability is not entitlement. License enforcement belongs at the execution gateway and never in physics operators.
- Milestone A has exactly two first verticals: Brain lesion T2/TSE and Knee cartilage/meniscus PD/T2 TSE.
- Dixon, TOF, and CEST research mode remain A+ candidates, not Milestone A verticals.
- Every resolved value has an explicit unit and `ParameterState`; every default has a source.
- `ResolvedExecutionPlan` is immutable and has a deterministic SHA-256 fingerprint.
- Preserve all currently honest UI labels and payload omissions for ADC bandwidth, acceleration, readout width, Partial Fourier, Lego recipe seeds, and clinical geometry.
- Do not start Milestone B until Milestone A is reviewed and accepted or the human explicitly unlocks B.
- Do not start Milestone C until Milestone B is reviewed and accepted or the human explicitly unlocks C.
- Every task begins with a failing test, implements the smallest passing behavior, runs focused and regression tests, performs the ablation pass, and creates one reviewable commit on the execution branch.

## Review Focus

- Non-finite or unitless clinical values must fail validation; Task 1 tests NaN and empty units.
- Tissue-role references must resolve within the same prior set; Task 1 tests a dangling confounder and duplicate tissue ids.
- Caller mutation and dictionary order must not change a resolved plan; Task 4 tests frozen models, deep snapshots, and canonical fingerprints.
- Raster/dead-time rounding must never silently change logical intent; Task 9 tests a non-raster duration and RF/ADC dead-time violations.
- Expired, wrong-device, unpaired-origin, and unentitled job requests must fail before provider submission; Tasks 15 and 16 test each boundary.

---

## File and Module Map

| Wave | Path | Action | Single responsibility |
|---|---|---|---|
| A | `packages/mrqlab_experiment/mrqlab_experiment/clinical.py` | Create | Immutable clinical-question, tissue-role, constraint, scanner-profile, parameter-state, and objective-vector models. |
| A | `packages/mrqlab_experiment/mrqlab_experiment/clinical_catalog.py` | Create | The two locked protocol recipes and compatibility bridge to existing experiment recipes. |
| A | `packages/mrqlab_experiment/mrqlab_experiment/resolution.py` | Create | Parameter resolution, canonical payload construction, and immutable plan fingerprinting. |
| A | `tests/experiment/test_clinical_contract_models.py` | Create | Model validation and serialization contract. |
| A | `tests/experiment/test_protocol_verticals.py` | Create | Exactly-two vertical catalog and graph bridge. |
| A | `tests/experiment/test_resolved_execution_plan.py` | Create | Defaults, units, provenance, immutability, and fingerprint gates. |
| A | `apps/web/lib/parameter-honesty.ts` | Create | UI-only manifest for unwired controls and exact parameter states. |
| A | `apps/web/tests/protocol-parameter-honesty.test.tsx` | Create | Visible labels and execution-payload omission tests. |
| A | `tests/experiment/test_protocol_platform_docs.py` | Create | Product layer, vertical, safety, and ssEPG/PDG documentation alignment. |
| B | `packages/mrqlab_experiment/mrqlab_experiment/executable_sequence.py` | Create | Logical, executable, RF, gradient, ADC, and timing contracts. |
| B | `packages/mrqlab_experiment/mrqlab_experiment/sequence_lowering.py` | Create | Deterministic scanner-profile lowering and raster validation. |
| B | `packages/mrqlab_experiment/mrqlab_experiment/export_ir.py` | Create | Export IR, validation states, and adapter-neutral shape deduplication. |
| B | `tests/experiment/test_executable_sequence_contract.py` | Create | Sequence-contract validation. |
| B | `tests/experiment/test_sequence_lowering.py` | Create | Lowering and hardware-boundary gates. |
| B | `tests/experiment/test_export_ir.py` | Create | Export-state and no-scanner-ready-claim gates. |
| C | `packages/mrqlab_experiment/mrqlab_experiment/execution_provider.py` | Create | Provider protocol and in-process compatibility provider. |
| C | `services/local_agent/mrqlab_agent/models.py` | Create | Job, event, artifact, capability, pairing, and lease wire models. |
| C | `services/local_agent/mrqlab_agent/store.py` | Create | Thread-safe job/event metadata and content-addressed artifacts. |
| C | `services/local_agent/mrqlab_agent/providers.py` | Create | CPU worker and optional GPU-provider registration. |
| C | `services/local_agent/mrqlab_agent/license.py` | Create | Ed25519 lease verification, entitlement checks, and trusted-time anchor. |
| C | `services/local_agent/mrqlab_agent/security.py` | Create | Loopback, strict origin, pairing, and CSRF enforcement. |
| C | `services/local_agent/mrqlab_agent/main.py` | Create | Local job/cancel/events/artifacts/capabilities API. |
| C | `tests/local_agent/` | Create | Provider, job lifecycle, lease, and localhost-security tests. |

## Wave Gates

| Wave | Tasks | Entry gate | Exit evidence |
|---|---:|---|---|
| A — Clinical Contract | 1–7 | Human says `开工` | Immutable plan, two verticals, honest UI, aligned docs, full regression |
| B — Executable Sequence | 8–10 | A accepted or explicit B unlock | Deterministic lowering and bounded export states; no Pulseq adapter |
| C — Licensed Local Compute | 11–16 | B accepted or explicit C unlock; crypto dependency approved before Task 14 | CPU jobs, GPU fail-closed seam, signed lease enforcement, localhost security |
| Acceptance | 17 | Tasks 1–16 complete | Full Python/web/static gates and ablation report |

## Milestone A — Clinical Contract

### Task 1: Add the Clinical Contract Models Only

**Files:**
- Create: `packages/mrqlab_experiment/mrqlab_experiment/clinical.py`
- Test: `tests/experiment/test_clinical_contract_models.py`

**Interfaces:**
- Consumes: Pydantic's frozen-model support.
- Produces: `ClinicalQuestion`, `TissuePrior`, `TissuePriorSet`, `Target`, `Reference`, `Confounder`, `ContrastMetric`, `RobustnessScenario`, `AcquisitionConstraint`, `ClinicalProtocolRecipe`, `ScannerProfile`, `ParameterState`, and `ObjectiveVector`.

- [ ] **Step 1: Write the failing model contract tests**

```python
# tests/experiment/test_clinical_contract_models.py
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
        defaults=(ParameterState(name="adc_bandwidth_hz", value=62500.0, unit="Hz", state="scanner_default", source="research-3t@1.0.0"),),
    )
    recipe = ClinicalProtocolRecipe(
        id="brain_lesion_t2_tse",
        version="1.0.0",
        vertical="brain_lesion_t2_tse",
        question=ClinicalQuestion(anatomy="brain", research_question="Maximize lesion-to-WM T2 contrast", target_finding="T2-hyperintense lesion", contrast_mechanism="T2 TSE"),
        tissue_priors=priors,
        objective=ObjectiveVector(terms=(ContrastMetric(id="lesion-wm", target_tissue_id="lesion", reference_tissue_id="wm", metric="normalized_cnr_proxy", direction="maximize", weight=1.0),)),
        robustness=(RobustnessScenario(id="routine-3t", delta_b0_hz=(-50.0, 50.0), b1_scale=(.85, 1.15), motion_mm=(0.0, 1.0), t1_scale=(.9, 1.1), t2_scale=(.9, 1.1)),),
        constraints=(AcquisitionConstraint(id="scan-time", metric="scan_time_s", operator="le", value=300.0, unit="s", severity="hard"),),
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
        _priors().model_copy(update={"confounders": (Confounder(tissue_id="missing", rationale="invalid"),)}).model_validate(
            {**_priors().model_dump(), "confounders": [{"tissue_id": "missing", "rationale": "invalid"}]}
        )


def test_numeric_values_are_finite_and_units_are_explicit():
    with pytest.raises(ValidationError, match="finite"):
        AcquisitionConstraint(id="bad", metric="scan_time_s", operator="le", value=math.nan, unit="s", severity="hard")
    with pytest.raises(ValidationError):
        ParameterState(name="te", value=.1, unit="", state="authored", source="user")
```

- [ ] **Step 2: Run the tests and verify the module is absent**

Run: `uv run --python 3.11 pytest tests/experiment/test_clinical_contract_models.py -q`

Expected: FAIL during import because `mrqlab_experiment.clinical` does not exist.

- [ ] **Step 3: Add the complete immutable model file**

```python
# packages/mrqlab_experiment/mrqlab_experiment/clinical.py
from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NonEmpty = Annotated[str, Field(min_length=1)]
ParameterStateKind = Literal[
    "authored", "derived", "scanner_default", "estimated",
    "visual_only", "unsupported", "stale",
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
    metric: Literal["scan_time_s", "sar_relative", "resolution_mm", "coverage_mm", "echo_spacing_s", "bandwidth_hz"]
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
```

- [ ] **Step 4: Run focused tests**

Run: `uv run --python 3.11 pytest tests/experiment/test_clinical_contract_models.py -q`

Expected: PASS.

- [ ] **Step 5: Perform the ablation pass**

Delete no model: each remaining class is named in the locked Milestone A contract, `FrozenModel` enforces the shared immutability/non-finite boundary, and `TissueRole` removes duplicate fields used by three concrete role types.

- [ ] **Step 6: Commit the model-only slice**

```bash
git add packages/mrqlab_experiment/mrqlab_experiment/clinical.py tests/experiment/test_clinical_contract_models.py
git commit -m "feat(protocol): add clinical contract models"
```

### Task 2: Add Exactly Two Locked Clinical Verticals

**Files:**
- Create: `packages/mrqlab_experiment/mrqlab_experiment/clinical_catalog.py`
- Test: `tests/experiment/test_protocol_verticals.py`

**Interfaces:**
- Consumes: all Task 1 models.
- Produces: `list_protocol_recipes() -> tuple[ClinicalProtocolRecipe, ...]` and `get_protocol_recipe(recipe_id: str) -> ClinicalProtocolRecipe`.

- [ ] **Step 1: Write the failing catalog tests**

```python
# tests/experiment/test_protocol_verticals.py
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
    assert {item.tissue_id for item in knee.tissue_priors.confounders} == {"joint_fluid", "marrow_fat"}


def test_parked_verticals_are_not_promoted_into_the_a_catalog():
    for recipe_id in ("abdomen_dixon_gre", "angio_tof_gre", "cest_amide_z_spectrum"):
        with pytest.raises(KeyError, match="not a Milestone A protocol recipe"):
            get_protocol_recipe(recipe_id)
```

- [ ] **Step 2: Run the tests and verify the catalog is absent**

Run: `uv run --python 3.11 pytest tests/experiment/test_protocol_verticals.py -q`

Expected: FAIL during import because `clinical_catalog.py` does not exist.

- [ ] **Step 3: Add the complete two-recipe catalog**

```python
# packages/mrqlab_experiment/mrqlab_experiment/clinical_catalog.py
from .clinical import (
    AcquisitionConstraint, ClinicalProtocolRecipe, ClinicalQuestion, Confounder,
    ContrastMetric, ObjectiveVector, ParameterState, Reference, RobustnessScenario,
    ScannerProfile, Target, TissuePrior, TissuePriorSet,
)


RESEARCH_3T = ScannerProfile(
    id="research-3t", version="1.0.0", b0_t=3.0,
    max_gradient_mt_m=80.0, max_slew_rate_t_m_s=200.0,
    gradient_raster_s=10e-6, rf_raster_s=1e-6, adc_raster_s=1e-7,
    rf_dead_time_s=100e-6, rf_ringdown_time_s=30e-6, adc_dead_time_s=10e-6,
    defaults=(ParameterState(name="adc_bandwidth_hz", value=62500.0, unit="Hz", state="scanner_default", source="research-3t@1.0.0"),),
)


BRAIN_LESION_T2_TSE = ClinicalProtocolRecipe(
    id="brain_lesion_t2_tse", version="1.0.0", vertical="brain_lesion_t2_tse",
    question=ClinicalQuestion(
        anatomy="brain", research_question="Maximize lesion-to-white-matter T2 contrast without treating CSF brightness as lesion evidence",
        target_finding="T2-hyperintense lesion", contrast_mechanism="T2-weighted turbo spin echo",
    ),
    tissue_priors=TissuePriorSet(
        id="brain-lesion-t2-priors", version="1.0.0",
        tissues=(
            TissuePrior(id="lesion", label="T2-hyperintense lesion", role="target", t1=1.4, t2=.12, proton_density=.95),
            TissuePrior(id="white_matter", label="White matter", role="reference", t1=.9, t2=.08, proton_density=.75),
            TissuePrior(id="gray_matter", label="Gray matter", role="background", t1=1.3, t2=.10, proton_density=.85),
            TissuePrior(id="csf", label="CSF", role="background", t1=4.0, t2=2.0, proton_density=1.0),
        ),
        targets=(Target(tissue_id="lesion", rationale="research contrast target"),),
        references=(Reference(tissue_id="white_matter", rationale="normal-appearing reference"),),
        confounders=(Confounder(tissue_id="gray_matter", rationale="intermediate T2 parenchyma"), Confounder(tissue_id="csf", rationale="long-T2 fluid")),
    ),
    objective=ObjectiveVector(terms=(ContrastMetric(id="lesion-vs-wm", target_tissue_id="lesion", reference_tissue_id="white_matter", metric="normalized_cnr_proxy", direction="maximize", weight=1.0),)),
    robustness=(RobustnessScenario(id="routine-3t", delta_b0_hz=(-50, 50), b1_scale=(.85, 1.15), motion_mm=(0, 1), t1_scale=(.9, 1.1), t2_scale=(.9, 1.1)),),
    constraints=(
        AcquisitionConstraint(id="scan-time", metric="scan_time_s", operator="le", value=300, unit="s", severity="hard"),
        AcquisitionConstraint(id="resolution", metric="resolution_mm", operator="le", value=1.0, unit="mm", severity="soft"),
    ),
    scanner_profile=RESEARCH_3T, experiment_recipe_id="brain_t2_tse",
)


KNEE_CARTILAGE_MENISCUS_PD_T2_TSE = ClinicalProtocolRecipe(
    id="knee_cartilage_meniscus_pd_t2_tse", version="1.0.0", vertical="knee_cartilage_meniscus_pd_t2_tse",
    question=ClinicalQuestion(
        anatomy="knee", research_question="Separate cartilage and meniscal pathology from normal fibrocartilage while tracking fluid and fat confounders",
        target_finding="cartilage fissure or meniscal tear", contrast_mechanism="proton-density/T2 turbo spin echo",
    ),
    tissue_priors=TissuePriorSet(
        id="knee-pd-t2-priors", version="1.0.0",
        tissues=(
            TissuePrior(id="cartilage", label="Hyaline cartilage", role="target", t1=1.2, t2=.04, proton_density=.80),
            TissuePrior(id="meniscal_tear", label="Meniscal tear", role="target", t1=1.5, t2=.09, proton_density=.95),
            TissuePrior(id="meniscus", label="Fibrocartilage meniscus", role="reference", t1=.9, t2=.015, proton_density=.50),
            TissuePrior(id="joint_fluid", label="Joint fluid", role="background", t1=3.8, t2=1.5, proton_density=1.0),
            TissuePrior(id="marrow_fat", label="Marrow fat", role="background", t1=.3, t2=.06, proton_density=.85),
        ),
        targets=(Target(tissue_id="cartilage", rationale="cartilage-surface target"), Target(tissue_id="meniscal_tear", rationale="fluid-sensitive tear target")),
        references=(Reference(tissue_id="meniscus", rationale="normal low-T2 fibrocartilage"),),
        confounders=(Confounder(tissue_id="joint_fluid", rationale="bright fluid"), Confounder(tissue_id="marrow_fat", rationale="fat signal")),
    ),
    objective=ObjectiveVector(terms=(
        ContrastMetric(id="tear-vs-meniscus", target_tissue_id="meniscal_tear", reference_tissue_id="meniscus", metric="normalized_cnr_proxy", direction="maximize", weight=1.0),
        ContrastMetric(id="cartilage-vs-meniscus", target_tissue_id="cartilage", reference_tissue_id="meniscus", metric="absolute_signal_difference", direction="maximize", weight=.5),
    )),
    robustness=(RobustnessScenario(id="routine-knee-3t", delta_b0_hz=(-75, 75), b1_scale=(.8, 1.2), motion_mm=(0, 2), t1_scale=(.9, 1.1), t2_scale=(.85, 1.15)),),
    constraints=(
        AcquisitionConstraint(id="scan-time", metric="scan_time_s", operator="le", value=240, unit="s", severity="hard"),
        AcquisitionConstraint(id="resolution", metric="resolution_mm", operator="le", value=.6, unit="mm", severity="soft"),
    ),
    scanner_profile=RESEARCH_3T, experiment_recipe_id="msk_knee_tse",
)


_RECIPES = (BRAIN_LESION_T2_TSE, KNEE_CARTILAGE_MENISCUS_PD_T2_TSE)
_BY_ID = {recipe.id: recipe for recipe in _RECIPES}


def list_protocol_recipes() -> tuple[ClinicalProtocolRecipe, ...]:
    return _RECIPES


def get_protocol_recipe(recipe_id: str) -> ClinicalProtocolRecipe:
    try:
        return _BY_ID[recipe_id]
    except KeyError:
        raise KeyError(f"{recipe_id!r} is not a Milestone A protocol recipe") from None
```

- [ ] **Step 4: Run focused tests**

Run: `uv run --python 3.11 pytest tests/experiment/test_protocol_verticals.py -q`

Expected: PASS; the returned tuple has two entries and no parked vertical.

- [ ] **Step 5: Perform the ablation pass and commit**

The shared `RESEARCH_3T` object is used by both recipes; all other constants encode a distinct locked vertical. Then commit:

```bash
git add packages/mrqlab_experiment/mrqlab_experiment/clinical_catalog.py tests/experiment/test_protocol_verticals.py
git commit -m "feat(protocol): add two locked clinical verticals"
```

### Task 3: Attach the Clinical Recipe to ExperimentGraph Without Replacing the Kernel

**Files:**
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/models.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/clinical_catalog.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/__init__.py`
- Modify: `services/api/mrqlab_api/main.py`
- Modify: `tests/experiment/test_protocol_verticals.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: existing `build_clinical_recipe(name) -> ExperimentGraph` and Task 2 recipes.
- Produces: optional `ExperimentGraph.clinical_recipe`, `build_protocol_experiment(recipe_id) -> ExperimentGraph`, and `GET /protocol-recipes`.

- [ ] **Step 1: Add failing bridge and API tests**

```python
# append to tests/experiment/test_protocol_verticals.py
from mrqlab_experiment import build_protocol_experiment


def test_protocol_recipe_extends_existing_experiment_recipe():
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    assert graph.id == "recipe:brain_t2_tse"
    assert graph.clinical_recipe.id == "brain_lesion_t2_tse"
    assert graph.sequence.template == "TSE"
    assert [item.model_dump() for item in graph.tissue] == [item.model_dump() for item in graph.clinical_recipe.tissue_priors.tissues]
    assert graph.effective_scanner.b0_t == graph.clinical_recipe.scanner_profile.b0_t
```

```python
# append to tests/test_api.py
def test_protocol_recipe_endpoint_lists_only_the_two_a_verticals():
    response = client.get("/protocol-recipes")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["recipes"]] == [
        "brain_lesion_t2_tse", "knee_cartilage_meniscus_pd_t2_tse",
    ]
```

- [ ] **Step 2: Run the tests and verify the bridge is absent**

Run: `uv run --python 3.11 pytest tests/experiment/test_protocol_verticals.py tests/test_api.py -q`

Expected: FAIL because `clinical_recipe`, `build_protocol_experiment`, and `/protocol-recipes` do not exist.

- [ ] **Step 3: Add the exact ExperimentGraph field and validation**

Add this import behind `TYPE_CHECKING`, then rebuild forward references at the end of `models.py`:

```python
# packages/mrqlab_experiment/mrqlab_experiment/models.py
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .clinical import ClinicalProtocolRecipe

# inside ExperimentGraph, after provenance
    clinical_recipe: "ClinicalProtocolRecipe | None" = None

# after ExperimentGraph
from .clinical import ClinicalProtocolRecipe
ExperimentGraph.model_rebuild()
```

The existing edge validator stays unchanged.

- [ ] **Step 4: Add the complete compatibility bridge**

```python
# append to packages/mrqlab_experiment/mrqlab_experiment/clinical_catalog.py
def build_protocol_experiment(recipe_id: str):
    from .models import TissueModel
    from .presets import build_clinical_recipe

    recipe = get_protocol_recipe(recipe_id)
    graph = build_clinical_recipe(recipe.experiment_recipe_id).model_copy(deep=True)
    graph.clinical_recipe = recipe
    graph.tissue = tuple(TissueModel.model_validate(item.model_dump()) for item in recipe.tissue_priors.tissues)
    graph.scanner_model = graph.scanner_model.model_copy(update={
        "b0_t": recipe.scanner_profile.b0_t,
        "max_gradient_mt_m": recipe.scanner_profile.max_gradient_mt_m,
        "max_slew_rate_t_m_s": recipe.scanner_profile.max_slew_rate_t_m_s,
    })
    return graph
```

Export `ClinicalProtocolRecipe`, `ParameterState`, `ResolvedExecutionPlan` only after their defining tasks, plus these Task 3 names now:

```python
# packages/mrqlab_experiment/mrqlab_experiment/__init__.py additions
from .clinical import ClinicalProtocolRecipe, ParameterState
from .clinical_catalog import build_protocol_experiment, get_protocol_recipe, list_protocol_recipes

# __all__ additions
"ClinicalProtocolRecipe", "ParameterState", "build_protocol_experiment",
"get_protocol_recipe", "list_protocol_recipes",
```

- [ ] **Step 5: Add the read-only API route**

```python
# services/api/mrqlab_api/main.py imports
from mrqlab_experiment import list_protocol_recipes

@app.get("/protocol-recipes")
def protocol_recipes():
    return {"recipes": [recipe.model_dump(mode="json") for recipe in list_protocol_recipes()]}
```

- [ ] **Step 6: Run focused and compatibility regressions**

Run: `uv run --python 3.11 pytest tests/experiment/test_protocol_verticals.py tests/experiment/test_clinical_recipes.py tests/test_api.py -q`

Expected: PASS; all pre-existing clinical recipes remain callable, while the new endpoint lists only the two A contracts.

- [ ] **Step 7: Perform the ablation pass and commit**

The new field is optional for all legacy graphs, and the bridge reuses the existing builder instead of creating a second compiler path.

```bash
git add packages/mrqlab_experiment/mrqlab_experiment services/api/mrqlab_api/main.py tests/experiment/test_protocol_verticals.py tests/test_api.py
git commit -m "feat(protocol): attach clinical contract to experiment graph"
```

### Task 4: Resolve an Immutable, Unit-Explicit Execution Plan

**Files:**
- Create: `packages/mrqlab_experiment/mrqlab_experiment/resolution.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/kernel.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/objectives.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/__init__.py`
- Create: `tests/experiment/test_resolved_execution_plan.py`
- Modify: `tests/experiment/test_execution_plan.py`

**Interfaces:**
- Consumes: `ExperimentGraph`, compiled `SequenceIR`, existing engine selection, and Task 1 `ParameterState`.
- Produces: immutable `ResolvedExecutionPlan`, compatibility alias `ExecutionPlan`, `resolve_parameter_states`, and `fingerprint_resolved_plan`.

- [ ] **Step 1: Write failing resolution tests**

```python
# tests/experiment/test_resolved_execution_plan.py
import pytest
from pydantic import ValidationError

from mrqlab_experiment import build_protocol_experiment, plan_experiment


def test_protocol_plan_resolves_units_sources_and_versions():
    plan = plan_experiment(build_protocol_experiment("brain_lesion_t2_tse"))
    states = {item.name: item for item in plan.parameters}
    assert plan.scanner_profile == "research-3t@1.0.0"
    assert plan.tissue_prior_set == "brain-lesion-t2-priors@1.0.0"
    assert states["te"].unit == "s"
    assert states["te"].state == "authored"
    assert states["b0_t"].unit == "T"
    assert states["b0_t"].state == "scanner_default"
    assert states["max_work"].unit == "work_unit"
    assert all(item.unit for item in plan.parameters)


def test_resolved_plan_is_deeply_immutable_and_detached_from_caller():
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    plan = plan_experiment(graph)
    original = plan.model_dump(mode="json")
    graph.sequence.params["te"] = .5
    assert plan.model_dump(mode="json") == original
    with pytest.raises(ValidationError, match="frozen"):
        plan.engine = "bloch"
    with pytest.raises(TypeError, match="immutable"):
        plan.options["epg_kmax"] = 99
    with pytest.raises(TypeError, match="immutable"):
        plan.experiment_snapshot["sequence"]["params"]["te"] = .5


def test_fingerprint_is_canonical_and_changes_with_resolved_input():
    first = build_protocol_experiment("brain_lesion_t2_tse")
    second = build_protocol_experiment("brain_lesion_t2_tse")
    second.engine.options = {"return_configurations": True, "epg_kmax": 8}
    first.engine.options = {"epg_kmax": 8, "return_configurations": True}
    assert plan_experiment(first).fingerprint == plan_experiment(second).fingerprint
    second.sequence.params["te"] = .02
    assert plan_experiment(first).fingerprint != plan_experiment(second).fingerprint
```

- [ ] **Step 2: Run the tests and verify the resolved contract is absent**

Run: `uv run --python 3.11 pytest tests/experiment/test_resolved_execution_plan.py -q`

Expected: FAIL because the current mutable `ExecutionPlan` lacks parameter states and versioned clinical inputs.

- [ ] **Step 3: Add the complete resolution module**

```python
# packages/mrqlab_experiment/mrqlab_experiment/resolution.py
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .capabilities import EngineValidity
from .clinical import ParameterState
from .models import ExperimentGraph, TemplateRef


class FrozenDict(dict):
    def _immutable(self, *args, **kwargs):
        raise TypeError("resolved mappings are immutable")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _immutable


def _deep_freeze(value):
    if isinstance(value, dict):
        return FrozenDict({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    return value


class ResolvedExecutionPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    schema_version: Literal["2.0"] = "2.0"
    experiment_id: str
    clinical_recipe_id: str | None = None
    experiment_snapshot: FrozenDict
    fingerprint: str = ""
    representation: str
    engine: str
    validity: EngineValidity = Field(default_factory=EngineValidity)
    required_capabilities: tuple[str, ...]
    preferred: str | None
    requested_observations: tuple[str, ...] = ()
    parameters: tuple[ParameterState, ...] = ()
    scanner_profile: str | None = None
    tissue_prior_set: str | None = None
    approximations: tuple[str, ...] = ()
    differentiable: bool = False
    cost_estimate: float = 0.0
    physics_status: FrozenDict = Field(default_factory=FrozenDict)
    stale_dependencies: FrozenDict = Field(default_factory=FrozenDict)
    options: FrozenDict = Field(default_factory=FrozenDict)
    reasons: tuple[str, ...] = ()

    @field_validator("experiment_snapshot", "physics_status", "stale_dependencies", "options", mode="before")
    @classmethod
    def freeze_mappings(cls, value):
        return _deep_freeze(value)


_UNITS = {
    "te": "s", "tr": "s", "echoes": "count", "echo_count": "count",
    "flip_angle": "deg", "refocusing_flip_angle": "deg",
    "b0_t": "T", "max_gradient_mt_m": "mT/m",
    "max_slew_rate_t_m_s": "T/m/s", "adc_bandwidth_hz": "Hz",
    "matrix": "pixel", "max_work": "work_unit",
}


def resolve_parameter_states(graph: ExperimentGraph, sequence) -> tuple[ParameterState, ...]:
    authored = graph.sequence.params if isinstance(graph.sequence, TemplateRef) else {}
    derived = {
        key: value for key, value in sequence.metadata.items()
        if key in _UNITS and isinstance(value, (int, float, str, bool))
    }
    values = {**derived, **authored}
    states = [
        ParameterState(
            name=name, value=value, unit=_UNITS[name],
            state="authored" if name in authored else "derived",
            source="ExperimentGraph.sequence.params" if name in authored else "sequence compiler",
        )
        for name, value in sorted(values.items()) if name in _UNITS
    ]
    scanner = graph.effective_scanner
    states.extend((
        ParameterState(name="b0_t", value=scanner.b0_t, unit="T", state="scanner_default", source="ExperimentGraph.effective_scanner"),
        ParameterState(name="max_gradient_mt_m", value=scanner.max_gradient_mt_m, unit="mT/m", state="scanner_default", source="ExperimentGraph.effective_scanner"),
        ParameterState(name="max_slew_rate_t_m_s", value=scanner.max_slew_rate_t_m_s, unit="T/m/s", state="scanner_default", source="ExperimentGraph.effective_scanner"),
        ParameterState(name="adc_bandwidth_hz", value=scanner.adc_bandwidth_hz, unit="Hz", state="scanner_default", source="ExperimentGraph.effective_scanner"),
        ParameterState(name="matrix", value=graph.constraints.matrix, unit="pixel", state="authored", source="ExperimentGraph.constraints"),
        ParameterState(name="max_work", value=graph.constraints.max_work, unit="work_unit", state="authored", source="ExperimentGraph.constraints"),
    ))
    return tuple(sorted(states, key=lambda item: item.name))


def fingerprint_resolved_plan(plan: ResolvedExecutionPlan) -> str:
    payload = plan.model_dump(mode="json", exclude={"fingerprint"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Replace the mutable plan class and final plan construction**

In `kernel.py`, delete the current `ExecutionPlan` class, import the resolution helpers, and preserve the old public name:

```python
from .resolution import ResolvedExecutionPlan, fingerprint_resolved_plan, resolve_parameter_states

ExecutionPlan = ResolvedExecutionPlan
```

Replace the current `return ExecutionPlan(...)` at the end of `plan_experiment` with this complete construction:

```python
    clinical = graph.clinical_recipe
    resolved = ResolvedExecutionPlan(
        experiment_id=graph.id,
        clinical_recipe_id=clinical.id if clinical else None,
        experiment_snapshot=graph.model_dump(mode="json"),
        representation=selected.name,
        engine=selected.name,
        validity=selected.validity,
        required_capabilities=tuple(sorted(required)),
        preferred=preferred,
        requested_observations=graph.readout.products,
        parameters=resolve_parameter_states(graph, sequence),
        scanner_profile=(f"{clinical.scanner_profile.id}@{clinical.scanner_profile.version}" if clinical else None),
        tissue_prior_set=(f"{clinical.tissue_priors.id}@{clinical.tissue_priors.version}" if clinical else None),
        approximations=approximations,
        differentiable=selected.validity.differentiable,
        cost_estimate=cost_estimate,
        physics_status=physics_status,
        stale_dependencies=stale_deps,
        options=asdict(options),
        reasons=(*explanations, source),
    )
    return resolved.model_copy(update={"fingerprint": fingerprint_resolved_plan(resolved)})
```

Delete the old raw-graph `fingerprint = hashlib.sha256(...)` block and its unused `hashlib`/`json` imports. Change both plan consumers from `EngineOptions(**plan.options)` to `EngineOptions(**dict(plan.options))` in `kernel.py` and `objectives.py`.

- [ ] **Step 5: Export the new name while preserving the old one**

```python
# packages/mrqlab_experiment/mrqlab_experiment/__init__.py additions
from .resolution import ResolvedExecutionPlan

# __all__ addition
"ResolvedExecutionPlan",
```

- [ ] **Step 6: Run focused and existing plan tests**

Run: `uv run --python 3.11 pytest tests/experiment/test_resolved_execution_plan.py tests/experiment/test_execution_plan.py tests/experiment/test_clinical_execution_contract.py tests/experiment/test_execution_semantics_hardening.py -q`

Expected: PASS; the compatibility `ExecutionPlan` import and existing `.physics_status.get(...)` behavior remain valid through `FrozenDict`.

- [ ] **Step 7: Perform the ablation pass and commit**

`FrozenDict` exists only because Pydantic's frozen model setting does not freeze nested dictionaries; the unit table is used by all resolved scalar parameters.

```bash
git add packages/mrqlab_experiment/mrqlab_experiment tests/experiment/test_resolved_execution_plan.py tests/experiment/test_execution_plan.py
git commit -m "feat(protocol): resolve immutable execution plans"
```

### Task 5: Carry Resolved-Plan Provenance into Every Observation

**Files:**
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/observations.py`
- Modify: `apps/web/lib/workbench-types.ts`
- Modify: `tests/experiment/test_observations.py`
- Modify: `tests/experiment/test_readout_spec.py`

**Interfaces:**
- Consumes: `KernelRun.plan: ResolvedExecutionPlan`.
- Produces: observation provenance fields `plan_fingerprint`, `clinical_recipe_id`, `scanner_profile`, `tissue_prior_set`, and serialized parameter provenance.

- [ ] **Step 1: Add the failing provenance test**

```python
# append to tests/experiment/test_observations.py
from mrqlab_experiment import build_protocol_experiment


def test_every_observation_carries_resolved_plan_and_parameter_provenance():
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    result = build_result_graph(run_experiment(graph))
    fingerprints = {item.provenance.plan_fingerprint for item in result.observations}
    assert fingerprints == {plan_experiment(graph).fingerprint}
    for observation in result.observations:
        assert observation.provenance.clinical_recipe_id == "brain_lesion_t2_tse"
        assert observation.provenance.scanner_profile == "research-3t@1.0.0"
        assert {item.name for item in observation.provenance.parameters} >= {"te", "b0_t", "max_work"}
```

- [ ] **Step 2: Run the test and verify the fields are absent**

Run: `uv run --python 3.11 pytest tests/experiment/test_observations.py -q`

Expected: FAIL because `ObservationProvenance` does not expose resolved-plan provenance.

- [ ] **Step 3: Extend the provenance model and constructor**

```python
# packages/mrqlab_experiment/mrqlab_experiment/observations.py import
from .clinical import ParameterState

# add to ObservationProvenance
    plan_fingerprint: str
    clinical_recipe_id: str | None = None
    scanner_profile: str | None = None
    tissue_prior_set: str | None = None
    parameters: tuple[ParameterState, ...] = ()
```

Replace the `provenance = ObservationProvenance(...)` construction with:

```python
    if plan is None:
        raise ValueError("KernelRun must include a ResolvedExecutionPlan")
    provenance = ObservationProvenance(
        experiment_hash=digest,
        plan_fingerprint=plan.fingerprint,
        clinical_recipe_id=plan.clinical_recipe_id,
        scanner_profile=plan.scanner_profile,
        tissue_prior_set=plan.tissue_prior_set,
        parameters=plan.parameters,
        engine=str(plan.engine),
        representation=plan.representation,
        assumptions=tuple(meta.get("assumptions", ())),
        seed=run.experiment.provenance.seed,
        n_ops=int(meta.get("n_ops", 0)),
        estimated_work=int(meta.get("estimated_work", 0)),
    )
```

- [ ] **Step 4: Extend the web wire type without changing rendering behavior**

```ts
// apps/web/lib/workbench-types.ts
export type ParameterState = {
  name: string;
  value: number | string | boolean;
  unit: string;
  state: "authored" | "derived" | "scanner_default" | "estimated" | "visual_only" | "unsupported" | "stale";
  source: string;
};

// add to the existing observation provenance type
plan_fingerprint: string;
clinical_recipe_id?: string | null;
scanner_profile?: string | null;
tissue_prior_set?: string | null;
parameters: ParameterState[];
```

- [ ] **Step 5: Run observation, readout, API, and web type gates**

Run: `uv run --python 3.11 pytest tests/experiment/test_observations.py tests/experiment/test_readout_spec.py tests/test_api.py -q && cd apps/web && npm run typecheck`

Expected: PASS; observation order and exact requested-product behavior remain unchanged.

- [ ] **Step 6: Perform the ablation pass and commit**

No parallel top-level result-plan object is added; every observation already owns provenance and therefore carries the shared fingerprint directly.

```bash
git add packages/mrqlab_experiment/mrqlab_experiment/observations.py apps/web/lib/workbench-types.ts tests/experiment/test_observations.py tests/experiment/test_readout_spec.py
git commit -m "feat(protocol): attach resolved provenance to observations"
```

### Task 6: Keep Every Unwired Workbench Control Explicitly Labeled

**Files:**
- Create: `apps/web/lib/parameter-honesty.ts`
- Modify: `apps/web/components/workbench/WorkbenchCockpit.tsx`
- Create: `apps/web/tests/protocol-parameter-honesty.test.tsx`
- Modify: `apps/web/tests/wave-f-lego.test.tsx`
- Modify: `apps/web/tests/wave-h-ux-honesty.test.tsx`

**Interfaces:**
- Consumes: existing workbench control state only.
- Produces: `UNWIRED_PARAMETER_STATES` and visible labels; it adds no value to compose, patch, or run payloads.

- [ ] **Step 1: Write the failing UI honesty test**

```tsx
// apps/web/tests/protocol-parameter-honesty.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkbenchCockpit } from "../components/workbench/WorkbenchCockpit";
import { WorkspaceProvider, useWorkspace } from "../components/workspace/WorkspaceProvider";

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });
function Harness() {
  const { setProfile } = useWorkspace();
  return <><button onClick={() => setProfile("physics")}>Physics profile</button><WorkbenchCockpit /></>;
}

describe("protocol parameter honesty", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("labels all four unwired controls and omits them from run payloads", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/sequences/build")) return json({ name: "TSE", duration: .1, channels: [], metadata: {} });
      if (url.includes("/cockpit/signals")) return json({ signals: {} });
      if (url.includes("/clinical-recipes")) return json({ recipes: [] });
      return json({ schema_version: "1.0", experiment_id: "x", observations: [] });
    }));
    render(<WorkspaceProvider><Harness /></WorkspaceProvider>);
    expect(screen.getByTestId("clinical-acceleration-state")).toHaveTextContent("local only · not in execution plan");
    fireEvent.click(screen.getByRole("button", { name: "Physics profile" }));
    fireEvent.click(screen.getByTestId("edit-mode-toggle"));
    expect(screen.getByTestId("readout-width-state")).toHaveTextContent("local only · not in execution plan");
    expect(screen.getByTestId("partial-fourier-state")).toHaveTextContent("local only · not in execution plan");
    expect(screen.getByTestId("adc-bw-slider-seed")).toHaveTextContent("seed · not wired");
    fireEvent.click(screen.getByTestId("run-experiment-btn"));
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    for (const [url, init] of (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls) {
      if (String(url).includes("/experiments/run")) {
        expect(String(init?.body)).not.toMatch(/adc_bw|bandwidth_hz|acceleration|readout_width|partial_fourier/i);
      }
    }
  });
});
```

- [ ] **Step 2: Run the test and verify the three new labels are absent**

Run: `cd apps/web && npm test -- protocol-parameter-honesty.test.tsx`

Expected: FAIL because acceleration, readout width, and Partial Fourier do not have parameter-state labels.

- [ ] **Step 3: Add the complete UI-only manifest**

```ts
// apps/web/lib/parameter-honesty.ts
export type UnwiredParameterState = {
  state: "visual_only";
  label: string;
};

export const UNWIRED_PARAMETER_STATES = {
  adc_bandwidth_hz: { state: "visual_only", label: "seed · not wired" },
  acceleration_factor: { state: "visual_only", label: "local only · not in execution plan" },
  readout_width_factor: { state: "visual_only", label: "local only · not in execution plan" },
  partial_fourier_fraction: { state: "visual_only", label: "local only · not in execution plan" },
} as const satisfies Record<string, UnwiredParameterState>;
```

- [ ] **Step 4: Render the manifest labels without changing handlers or payloads**

Import `UNWIRED_PARAMETER_STATES` in `WorkbenchCockpit.tsx`. Keep every existing `value`, `disabled`, and `onChange` property unchanged. Add these spans beside the existing labels:

```tsx
<span data-testid="readout-width-state" className="parameter-state-label">
  {UNWIRED_PARAMETER_STATES.readout_width_factor.label}
</span>

<span data-testid="partial-fourier-state" className="parameter-state-label">
  {UNWIRED_PARAMETER_STATES.partial_fourier_fraction.label}
</span>

<span data-testid="clinical-acceleration-state" className="parameter-state-label">
  {UNWIRED_PARAMETER_STATES.acceleration_factor.label}
</span>
```

Replace only the literal body of the existing `adc-bw-slider-seed` span with:

```tsx
{UNWIRED_PARAMETER_STATES.adc_bandwidth_hz.label}
```

- [ ] **Step 5: Run honesty, Lego, recipe, and type gates**

Run: `cd apps/web && npm test -- protocol-parameter-honesty.test.tsx wave-f-lego.test.tsx wave-h-ux-honesty.test.tsx run-from-recipe.test.tsx && npm run typecheck`

Expected: PASS; current disabled/enabled states and all negative payload assertions remain unchanged.

- [ ] **Step 6: Perform the ablation pass and commit**

The manifest is used by four labels, so it removes repeated state/copy without changing execution data flow.

```bash
git add apps/web/lib/parameter-honesty.ts apps/web/components/workbench/WorkbenchCockpit.tsx apps/web/tests
git commit -m "feat(web): label unwired protocol parameters"
```

### Task 7: Align Architecture and Physics Truth, Then Close Milestone A

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/PHYSICS.md`
- Modify: `docs/ROADMAP.md`
- Create: `tests/experiment/test_protocol_platform_docs.py`

**Interfaces:**
- Consumes: completed A contracts and current docs-test literals.
- Produces: aligned product layers, execution profiles, two-vertical boundary, ssEPG/PDG availability, and parked B/C roadmap.

- [ ] **Step 1: Write the failing documentation contract test**

```python
# tests/experiment/test_protocol_platform_docs.py
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_architecture_names_product_layers_profiles_and_contract():
    text = (ROOT / "docs/ARCHITECTURE.md").read_text()
    for required in (
        "research-use-only MRI contrast and protocol engineering platform",
        "Explore", "Protocol Studio", "Compute", "Export", "Enterprise Control Plane",
        "Tier 0", "Tier 1", "Tier 2", "ResolvedExecutionPlan",
        "Capability is not entitlement", "POST /experiments/run", "POST /jobs",
    ):
        assert required in text


def test_architecture_and_physics_agree_ssepg_and_pdg_are_available():
    architecture = (ROOT / "docs/ARCHITECTURE.md").read_text()
    physics = (ROOT / "docs/PHYSICS.md").read_text()
    assert "| ssEPG | yes |" in architecture
    assert "| PDG | yes |" in architecture
    assert "| ssEPG | yes |" in physics
    assert "| PDG | yes |" in physics


def test_roadmap_locks_two_a_verticals_and_parks_b_and_c():
    text = (ROOT / "docs/ROADMAP.md").read_text()
    assert "Brain lesion T2/TSE" in text
    assert "Knee cartilage/meniscus PD/T2 TSE" in text
    assert "Dixon / TOF / CEST research" in text
    assert "Milestone B — Executable Sequence (parked)" in text
    assert "Milestone C — Licensed Local Compute (parked)" in text
```

- [ ] **Step 2: Run all documentation tests and record the current drift**

Run: `uv run --python 3.11 pytest tests/experiment/test_protocol_platform_docs.py tests/experiment/test_experiment_docs.py tests/physics/test_physics_docs.py tests/test_v063_epg_x_super_lorentzian.py tests/test_v066_cest_pulsed_train.py -q`

Expected: FAIL only in the new test because `ARCHITECTURE.md` still marks ssEPG and PDG unavailable and the protocol-platform sections are absent.

- [ ] **Step 3: Apply the exact architecture additions and matrix correction**

Insert after the product thesis in `docs/ARCHITECTURE.md`:

```markdown
MRQLab is a research-use-only MRI contrast and protocol engineering platform. It keeps teaching Explore and is not a scanner console, diagnostic clinical decision support system, or claim of clinical readiness.

The product layers are Explore / Protocol Studio / Compute / Export / Enterprise Control Plane. Tier 0 browser preview, Tier 1 in-process NumPy through synchronous `POST /experiments/run*`, and Tier 2 local high-fidelity through new `POST /jobs` providers share `ExperimentGraph`, immutable `ResolvedExecutionPlan`, `Observation`, and provenance. Capability is not entitlement: provider capability is selected by the experiment kernel, while commercial entitlement is enforced by an execution gateway outside physics operators.
```

Change only the availability cells for the existing ssEPG and PDG rows:

```markdown
| ssEPG | yes | hard_rf, shaped_rf, configuration_states, spatial_encoding, slice_selective | Dedicated slice-selective path with bounded current support |
| PDG | yes | hard_rf, configuration_states, spatial_encoding, off_resonance, phase_distribution | Dedicated spatial B0 pathway↔image adapter path |
```

Preserve all existing required strings including `ExperimentGraph`, `PhysicsOperator`, `StateRepresentation`, `ObjectiveFunction`, `Observation`, `Experiment IR`, `Sequence Compiler`, `Sequence IR`, `Physics Compiler`, `Physics IR`, `ONE Python process`, `packages/mrqlab_experiment`, `/experiments/run`, and `/simulate`.

- [ ] **Step 4: Add the protocol roadmap block without deleting current history**

Append this block before `## Delivery` in `docs/ROADMAP.md`:

```markdown
## Protocol platform milestones

### Milestone A — Clinical Contract

- First vertical: Brain lesion T2/TSE.
- Second vertical: Knee cartilage/meniscus PD/T2 TSE.
- Dixon / TOF / CEST research are A+ candidates, not A verticals.
- Resolve immutable, unit-explicit `ResolvedExecutionPlan` values and preserve honest UI parameter states.

### Milestone B — Executable Sequence (parked)

`LogicalSequenceIR → ExecutableSequenceIR → ExportIR`; frontend does not author Pulseq.

### Milestone C — Licensed Local Compute (parked)

New `ExecutionProvider` jobs, CPU then optional GPU, with capability separate from execution-gateway entitlement.
```

- [ ] **Step 5: Run Milestone A focused and full gates**

Run:

```bash
uv run --python 3.11 pytest tests/experiment -q
uv run --python 3.11 pytest tests/physics tests/test_api.py tests/test_v063_epg_x_super_lorentzian.py tests/test_v066_cest_pulsed_train.py -q
cd apps/web && npm test && npm run typecheck && npm run build
```

Expected: PASS. The docs retain `not a clinical`, `dimensionless teaching gradients`, `CEST imaging`, and `remain unavailable` exactly as required by existing tests.

- [ ] **Step 6: Run the Milestone A static anti-scope and docs-only-boundary checks**

Run:

```bash
rg -n "license|entitlement|lease" packages/physics
rg -n "POST /jobs|Pulseq adapter" packages apps services
git diff --check
```

Expected: the physics search has no licensing implementation; the second search has no Milestone B/C product implementation from A; `git diff --check` is silent.

- [ ] **Step 7: Perform the Milestone A ablation pass and commit**

Confirm every new model is referenced by a locked recipe or the resolved plan, every helper has at least two uses or enforces a cross-cutting invariant, and no A file introduces workers, licensing, Pulseq, shaped-RF design, Hybrid restacking, N-pool, MRS, or CEST imaging.

```bash
git add docs/ARCHITECTURE.md docs/PHYSICS.md docs/ROADMAP.md tests/experiment/test_protocol_platform_docs.py
git commit -m "docs(protocol): align clinical contract architecture"
```

## Milestone B — Executable Sequence (Parked)

Do not execute Tasks 8–10 until Milestone A is accepted or the human explicitly unlocks Milestone B.

### Task 8: Define Logical and Executable Sequence Contracts

**Files:**
- Create: `packages/mrqlab_experiment/mrqlab_experiment/executable_sequence.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/__init__.py`
- Create: `tests/experiment/test_executable_sequence_contract.py`

**Interfaces:**
- Consumes: Task 1 `ScannerProfile` by reference only.
- Produces: `LogicalSequenceIR`, `LogicalBlock`, `RfWaveform`, `GradientWaveform`, `AdcWindow`, `ExecutableBlock`, and `ExecutableSequenceIR`.

- [ ] **Step 1: Write the failing contract tests**

```python
# tests/experiment/test_executable_sequence_contract.py
import math
import pytest
from pydantic import ValidationError

from mrqlab_experiment.executable_sequence import (
    AdcWindow, GradientWaveform, LogicalBlock, LogicalSequenceIR, RfWaveform,
)


def test_logical_ir_carries_shaped_rf_arbitrary_g_and_adc_sampling():
    sequence = LogicalSequenceIR(
        id="tse-logical", duration_s=.02,
        blocks=(LogicalBlock(
            id="b0", start_s=0,
            rf=RfWaveform(samples_ut=(0, 2, 4, 2, 0), phase_rad=(0, 0, 0, 0, 0), raster_s=1e-6, carrier_offset_hz=0),
            gradients=(GradientWaveform(axis="gz", samples_mt_m=(0, 10, 10, 0), raster_s=10e-6),),
            adc=AdcWindow(delay_s=.005, dwell_s=2e-6, sample_count=128, frequency_offset_hz=0, phase_offset_rad=0),
        ),),
    )
    assert sequence.blocks[0].adc.sample_count == 128
    assert sequence.blocks[0].rf.samples_ut[2] == 4
    assert sequence.blocks[0].gradients[0].axis == "gz"


def test_contract_rejects_mismatched_rf_samples_and_non_finite_gradient():
    with pytest.raises(ValidationError, match="RF amplitude and phase sample counts must match"):
        RfWaveform(samples_ut=(1, 2), phase_rad=(0,), raster_s=1e-6)
    with pytest.raises(ValidationError, match="finite"):
        GradientWaveform(axis="gx", samples_mt_m=(0, math.inf), raster_s=10e-6)
```

- [ ] **Step 2: Run the tests and verify the contracts are absent**

Run: `uv run --python 3.11 pytest tests/experiment/test_executable_sequence_contract.py -q`

Expected: FAIL during import because `executable_sequence.py` does not exist.

- [ ] **Step 3: Add the complete sequence-contract module**

```python
# packages/mrqlab_experiment/mrqlab_experiment/executable_sequence.py
from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SequenceModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _finite(values: tuple[float, ...], label: str) -> tuple[float, ...]:
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"{label} samples must be finite")
    return values


class RfWaveform(SequenceModel):
    samples_ut: tuple[float, ...]
    phase_rad: tuple[float, ...]
    raster_s: float = Field(gt=0)
    carrier_offset_hz: float = 0.0

    @model_validator(mode="after")
    def valid_samples(self):
        _finite(self.samples_ut, "RF amplitude")
        _finite(self.phase_rad, "RF phase")
        if not self.samples_ut or len(self.samples_ut) != len(self.phase_rad):
            raise ValueError("RF amplitude and phase sample counts must match")
        return self


class GradientWaveform(SequenceModel):
    axis: Literal["gx", "gy", "gz"]
    samples_mt_m: tuple[float, ...]
    raster_s: float = Field(gt=0)

    @model_validator(mode="after")
    def valid_samples(self):
        _finite(self.samples_mt_m, "gradient")
        if len(self.samples_mt_m) < 2:
            raise ValueError("gradient waveform requires at least two samples")
        return self


class AdcWindow(SequenceModel):
    delay_s: float = Field(ge=0)
    dwell_s: float = Field(gt=0)
    sample_count: int = Field(gt=0)
    frequency_offset_hz: float = 0.0
    phase_offset_rad: float = 0.0


class LogicalBlock(SequenceModel):
    id: str = Field(min_length=1)
    start_s: float = Field(ge=0)
    rf: RfWaveform | None = None
    gradients: tuple[GradientWaveform, ...] = ()
    adc: AdcWindow | None = None

    @model_validator(mode="after")
    def unique_gradient_axes(self):
        axes = [gradient.axis for gradient in self.gradients]
        if len(axes) != len(set(axes)):
            raise ValueError("a logical block may contain at most one waveform per gradient axis")
        if self.rf is None and not self.gradients and self.adc is None:
            raise ValueError("logical block must contain RF, gradient, or ADC content")
        return self


class LogicalSequenceIR(SequenceModel):
    schema_version: Literal["1.0"] = "1.0"
    id: str = Field(min_length=1)
    duration_s: float = Field(gt=0)
    blocks: tuple[LogicalBlock, ...]

    @model_validator(mode="after")
    def unique_block_ids(self):
        ids = [block.id for block in self.blocks]
        if len(ids) != len(set(ids)):
            raise ValueError("logical block ids must be unique")
        return self


class ExecutableBlock(SequenceModel):
    id: str
    start_s: float
    duration_s: float
    rf: RfWaveform | None = None
    gradients: tuple[GradientWaveform, ...] = ()
    adc: AdcWindow | None = None


class ExecutableSequenceIR(SequenceModel):
    schema_version: Literal["1.0"] = "1.0"
    logical_sequence_id: str
    scanner_profile: str
    duration_s: float
    blocks: tuple[ExecutableBlock, ...]
    timing_adjustments: tuple[str, ...] = ()
```

- [ ] **Step 4: Export the contracts and run focused tests**

```python
# packages/mrqlab_experiment/mrqlab_experiment/__init__.py additions
from .executable_sequence import (
    AdcWindow, ExecutableBlock, ExecutableSequenceIR, GradientWaveform,
    LogicalBlock, LogicalSequenceIR, RfWaveform,
)

# __all__ additions
"AdcWindow", "ExecutableBlock", "ExecutableSequenceIR", "GradientWaveform",
"LogicalBlock", "LogicalSequenceIR", "RfWaveform",
```

Then run:

Run: `uv run --python 3.11 pytest tests/experiment/test_executable_sequence_contract.py -q`

Expected: PASS.

- [ ] **Step 5: Perform the ablation pass and commit**

The logical and executable records are distinct because Task 9 changes timing against a target scanner profile; no adapter or frontend Pulseq representation is introduced.

```bash
git add packages/mrqlab_experiment/mrqlab_experiment/executable_sequence.py packages/mrqlab_experiment/mrqlab_experiment/__init__.py tests/experiment/test_executable_sequence_contract.py
git commit -m "feat(sequence): add logical and executable IR contracts"
```

### Task 9: Lower LogicalSequenceIR Against Scanner Raster and Dead Time

**Files:**
- Create: `packages/mrqlab_experiment/mrqlab_experiment/sequence_lowering.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/__init__.py`
- Create: `tests/experiment/test_sequence_lowering.py`

**Interfaces:**
- Consumes: `LogicalSequenceIR` and `ScannerProfile`.
- Produces: `lower_sequence(logical, profile) -> ExecutableSequenceIR` with deterministic quantization and explicit adjustments.

- [ ] **Step 1: Write failing lowering and safety-boundary tests**

```python
# tests/experiment/test_sequence_lowering.py
import pytest

from mrqlab_experiment.clinical_catalog import RESEARCH_3T
from mrqlab_experiment.executable_sequence import AdcWindow, LogicalBlock, LogicalSequenceIR, RfWaveform
from mrqlab_experiment.sequence_lowering import lower_sequence


def test_lowering_quantizes_to_profile_rasters_and_records_adjustment():
    logical = LogicalSequenceIR(id="q", duration_s=.01, blocks=(LogicalBlock(
        id="rf", start_s=1.4e-6,
        rf=RfWaveform(samples_ut=(1, 1), phase_rad=(0, 0), raster_s=1e-6),
    ),))
    executable = lower_sequence(logical, RESEARCH_3T)
    assert executable.blocks[0].start_s == pytest.approx(1e-6)
    assert executable.timing_adjustments == ("rf.start_s: 1.4e-06 -> 1e-06",)


def test_lowering_fails_when_adc_begins_inside_rf_dead_time():
    logical = LogicalSequenceIR(id="bad", duration_s=.01, blocks=(
        LogicalBlock(id="rf", start_s=0, rf=RfWaveform(samples_ut=(1, 1), phase_rad=(0, 0), raster_s=1e-6)),
        LogicalBlock(id="adc", start_s=50e-6, adc=AdcWindow(delay_s=0, dwell_s=1e-6, sample_count=4)),
    ))
    with pytest.raises(ValueError, match="ADC begins before RF dead time and ringdown complete"):
        lower_sequence(logical, RESEARCH_3T)


def test_lowering_rejects_adc_dwell_off_profile_raster():
    logical = LogicalSequenceIR(id="bad-dwell", duration_s=.01, blocks=(LogicalBlock(
        id="adc", start_s=.001, adc=AdcWindow(delay_s=0, dwell_s=1.05e-6, sample_count=4),
    ),))
    with pytest.raises(ValueError, match="ADC dwell must be an exact adc_raster_s multiple"):
        lower_sequence(logical, RESEARCH_3T)
```

- [ ] **Step 2: Run the tests and verify the lowerer is absent**

Run: `uv run --python 3.11 pytest tests/experiment/test_sequence_lowering.py -q`

Expected: FAIL during import because `sequence_lowering.py` does not exist.

- [ ] **Step 3: Add the complete deterministic lowerer**

```python
# packages/mrqlab_experiment/mrqlab_experiment/sequence_lowering.py
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .clinical import ScannerProfile
from .executable_sequence import ExecutableBlock, ExecutableSequenceIR, LogicalSequenceIR


def _quantize(value: float, raster: float) -> float:
    ticks = (Decimal(str(value)) / Decimal(str(raster))).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return float(ticks * Decimal(str(raster)))


def _exact_multiple(value: float, raster: float, tolerance: float = 1e-12) -> bool:
    return abs(value - _quantize(value, raster)) <= tolerance


def lower_sequence(logical: LogicalSequenceIR, profile: ScannerProfile) -> ExecutableSequenceIR:
    blocks = []
    adjustments = []
    rf_guard_until = 0.0
    for block in sorted(logical.blocks, key=lambda item: (item.start_s, item.id)):
        raster = profile.rf_raster_s if block.rf is not None else profile.gradient_raster_s
        start = _quantize(block.start_s, raster)
        if start != block.start_s:
            adjustments.append(f"{block.id}.start_s: {block.start_s:g} -> {start:g}")

        durations = []
        if block.rf is not None:
            if not _exact_multiple(block.rf.raster_s, profile.rf_raster_s):
                raise ValueError("RF raster must be an exact rf_raster_s multiple")
            durations.append(len(block.rf.samples_ut) * block.rf.raster_s)
        for gradient in block.gradients:
            if not _exact_multiple(gradient.raster_s, profile.gradient_raster_s):
                raise ValueError("gradient raster must be an exact gradient_raster_s multiple")
            durations.append(len(gradient.samples_mt_m) * gradient.raster_s)
        if block.adc is not None:
            if not _exact_multiple(block.adc.dwell_s, profile.adc_raster_s):
                raise ValueError("ADC dwell must be an exact adc_raster_s multiple")
            adc_start = start + block.adc.delay_s
            if adc_start < rf_guard_until:
                raise ValueError("ADC begins before RF dead time and ringdown complete")
            durations.append(block.adc.delay_s + block.adc.dwell_s * block.adc.sample_count + profile.adc_dead_time_s)
        duration = max(durations)
        if start + duration > logical.duration_s:
            raise ValueError(f"block {block.id!r} exceeds logical sequence duration")
        if block.rf is not None:
            rf_guard_until = start + duration + profile.rf_dead_time_s + profile.rf_ringdown_time_s
        blocks.append(ExecutableBlock(
            id=block.id, start_s=start, duration_s=duration,
            rf=block.rf, gradients=block.gradients, adc=block.adc,
        ))
    return ExecutableSequenceIR(
        logical_sequence_id=logical.id,
        scanner_profile=f"{profile.id}@{profile.version}",
        duration_s=_quantize(logical.duration_s, profile.gradient_raster_s),
        blocks=tuple(blocks), timing_adjustments=tuple(adjustments),
    )
```

- [ ] **Step 4: Export and run focused tests**

```python
# packages/mrqlab_experiment/mrqlab_experiment/__init__.py additions
from .sequence_lowering import lower_sequence

# __all__ addition
"lower_sequence",
```

Then run:

Run: `uv run --python 3.11 pytest tests/experiment/test_sequence_lowering.py tests/experiment/test_executable_sequence_contract.py -q`

Expected: PASS.

- [ ] **Step 5: Perform the ablation pass and commit**

`_quantize` and `_exact_multiple` each serve RF, gradient, ADC, and sequence timing; there is no separate compiler class or configurable rounding policy.

```bash
git add packages/mrqlab_experiment/mrqlab_experiment/sequence_lowering.py packages/mrqlab_experiment/mrqlab_experiment/__init__.py tests/experiment/test_sequence_lowering.py
git commit -m "feat(sequence): lower logical IR against scanner timing"
```

### Task 10: Build Adapter-Neutral ExportIR and Exact Export States

**Files:**
- Create: `packages/mrqlab_experiment/mrqlab_experiment/export_ir.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/__init__.py`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/ROADMAP.md`
- Create: `tests/experiment/test_export_ir.py`

**Interfaces:**
- Consumes: `ExecutableSequenceIR`.
- Produces: `ExportIR`, `ExportShape`, `ExportBlock`, `ExportAssessment`, `build_export_ir`, and exact ordered export states. No Pulseq adapter is produced.

- [ ] **Step 1: Write failing export-state tests**

```python
# tests/experiment/test_export_ir.py
from pathlib import Path

from mrqlab_experiment.clinical_catalog import RESEARCH_3T
from mrqlab_experiment.executable_sequence import LogicalBlock, LogicalSequenceIR, RfWaveform
from mrqlab_experiment.export_ir import ExportState, assess_export, build_export_ir
from mrqlab_experiment.sequence_lowering import lower_sequence


def test_export_ir_deduplicates_shapes_and_stops_at_hardware_review():
    rf = RfWaveform(samples_ut=(0, 1, 0), phase_rad=(0, 0, 0), raster_s=1e-6)
    logical = LogicalSequenceIR(id="export", duration_s=.01, blocks=(
        LogicalBlock(id="a", start_s=0, rf=rf),
        LogicalBlock(id="b", start_s=.001, rf=rf),
    ))
    export_ir = build_export_ir(lower_sequence(logical, RESEARCH_3T))
    assert len(export_ir.shapes) == 1
    assert export_ir.blocks[0].rf_shape_id == export_ir.blocks[1].rf_shape_id
    assessment = assess_export(export_ir, target_profile_valid=True)
    assert assessment.states == (
        ExportState.SIMULATION_VALID, ExportState.IR_VALID, ExportState.EXPORTABLE,
        ExportState.TARGET_PROFILE_VALID, ExportState.HARDWARE_REVIEW_REQUIRED,
    )


def test_frontend_and_kernel_do_not_gain_a_pulseq_adapter_in_b_core():
    assert not Path("apps/web/lib/pulseq.ts").exists()
    assert not Path("packages/mrqlab_experiment/mrqlab_experiment/pulseq_adapter.py").exists()
```

- [ ] **Step 2: Run the tests and verify ExportIR is absent**

Run: `uv run --python 3.11 pytest tests/experiment/test_export_ir.py -q`

Expected: FAIL during import because `export_ir.py` does not exist.

- [ ] **Step 3: Add the complete adapter-neutral ExportIR**

```python
# packages/mrqlab_experiment/mrqlab_experiment/export_ir.py
from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .executable_sequence import AdcWindow, ExecutableSequenceIR


class ExportState(StrEnum):
    SIMULATION_VALID = "SIMULATION_VALID"
    IR_VALID = "IR_VALID"
    EXPORTABLE = "EXPORTABLE"
    TARGET_PROFILE_VALID = "TARGET_PROFILE_VALID"
    HARDWARE_REVIEW_REQUIRED = "HARDWARE_REVIEW_REQUIRED"


class ExportModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExportShape(ExportModel):
    id: str
    kind: Literal["rf", "gradient"]
    samples: tuple[float, ...]
    phase: tuple[float, ...] = ()
    raster_s: float


class ExportBlock(ExportModel):
    id: str
    start_s: float
    duration_s: float
    rf_shape_id: str | None = None
    gradient_shape_ids: tuple[str, ...] = ()
    adc: AdcWindow | None = None


class ExportIR(ExportModel):
    schema_version: Literal["1.0"] = "1.0"
    source_logical_sequence_id: str
    scanner_profile: str
    shapes: tuple[ExportShape, ...]
    blocks: tuple[ExportBlock, ...]


class ExportAssessment(ExportModel):
    states: tuple[ExportState, ...]
    messages: tuple[str, ...]


def _shape_id(kind: str, samples: tuple[float, ...], phase: tuple[float, ...], raster_s: float) -> str:
    raw = json.dumps([kind, samples, phase, raster_s], separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def build_export_ir(sequence: ExecutableSequenceIR) -> ExportIR:
    shapes = {}
    blocks = []
    for block in sequence.blocks:
        rf_id = None
        if block.rf is not None:
            rf_id = _shape_id("rf", block.rf.samples_ut, block.rf.phase_rad, block.rf.raster_s)
            shapes[rf_id] = ExportShape(id=rf_id, kind="rf", samples=block.rf.samples_ut, phase=block.rf.phase_rad, raster_s=block.rf.raster_s)
        gradient_ids = []
        for gradient in block.gradients:
            shape_id = _shape_id("gradient", gradient.samples_mt_m, (), gradient.raster_s)
            shapes[shape_id] = ExportShape(id=shape_id, kind="gradient", samples=gradient.samples_mt_m, raster_s=gradient.raster_s)
            gradient_ids.append(shape_id)
        blocks.append(ExportBlock(
            id=block.id, start_s=block.start_s, duration_s=block.duration_s,
            rf_shape_id=rf_id, gradient_shape_ids=tuple(gradient_ids),
            adc=block.adc,
        ))
    return ExportIR(
        source_logical_sequence_id=sequence.logical_sequence_id,
        scanner_profile=sequence.scanner_profile,
        shapes=tuple(shapes[key] for key in sorted(shapes)), blocks=tuple(blocks),
    )


def assess_export(export_ir: ExportIR, *, target_profile_valid: bool) -> ExportAssessment:
    states = [ExportState.SIMULATION_VALID, ExportState.IR_VALID, ExportState.EXPORTABLE]
    messages = ["simulation and IR validation do not imply scanner safety"]
    if target_profile_valid:
        states.extend((ExportState.TARGET_PROFILE_VALID, ExportState.HARDWARE_REVIEW_REQUIRED))
        messages.append("independent hardware review remains required")
    return ExportAssessment(states=tuple(states), messages=tuple(messages))
```

- [ ] **Step 4: Export names and document the boundary**

```python
# packages/mrqlab_experiment/mrqlab_experiment/__init__.py additions
from .export_ir import (
    ExportAssessment, ExportBlock, ExportIR, ExportShape, ExportState,
    assess_export, build_export_ir,
)

# __all__ additions
"ExportAssessment", "ExportBlock", "ExportIR", "ExportShape", "ExportState",
"assess_export", "build_export_ir",
```

Add this exact architecture sentence and roadmap gate:

```markdown
Frontend components author `LogicalSequenceIR`, never Pulseq. Lowering produces `ExecutableSequenceIR`, then adapter-neutral `ExportIR`; even `TARGET_PROFILE_VALID` always advances to `HARDWARE_REVIEW_REQUIRED`, never to a scanner-ready claim. A Pulseq adapter is a later separately reviewed wave.
```

- [ ] **Step 5: Run B tests and full regressions**

Run: `uv run --python 3.11 pytest tests/experiment/test_executable_sequence_contract.py tests/experiment/test_sequence_lowering.py tests/experiment/test_export_ir.py tests/experiment/test_experiment_docs.py -q && uv run --python 3.11 pytest tests/physics tests/test_api.py -q && cd apps/web && npm test && npm run typecheck`

Expected: PASS; existing `SequenceIR` and synchronous execution behavior are unchanged.

- [ ] **Step 6: Perform the Milestone B ablation pass and commit**

Confirm no Pulseq package, adapter, frontend authoring model, hardware-ready claim, or duplicate simulation IR was introduced.

```bash
git add packages/mrqlab_experiment/mrqlab_experiment docs/ARCHITECTURE.md docs/ROADMAP.md tests/experiment
git commit -m "feat(export): add executable and export IR boundary"
```

## Milestone C — Licensed Local Compute (Parked)

Do not execute Tasks 11–16 until Milestone B is accepted or the human explicitly unlocks Milestone C. Task 14 additionally requires human approval for the production crypto dependency.

### Task 11: Define ExecutionProvider and Preserve the Tier 1 In-Process Path

**Files:**
- Create: `packages/mrqlab_experiment/mrqlab_experiment/execution_provider.py`
- Modify: `packages/mrqlab_experiment/mrqlab_experiment/__init__.py`
- Create: `tests/experiment/test_execution_provider.py`

**Interfaces:**
- Consumes: immutable `ResolvedExecutionPlan`, embedded experiment snapshot, existing `run_experiment`, and `build_result_graph`.
- Produces: `ExecutionProvider`, `ProviderDescriptor`, `CapabilitySet`, `ResourceEstimate`, `JobHandle`, and `InProcessNumpyProvider`.

- [ ] **Step 1: Write failing provider tests**

```python
# tests/experiment/test_execution_provider.py
from mrqlab_experiment import build_protocol_experiment, plan_experiment
from mrqlab_experiment.execution_provider import InProcessNumpyProvider


def test_in_process_provider_consumes_resolved_plan_and_returns_observations():
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    plan = plan_experiment(graph)
    provider = InProcessNumpyProvider()
    assert provider.validate(plan).valid is True
    assert provider.capabilities().features >= frozenset({"cpu.numpy", "sync.experiment"})
    handle = provider.submit(plan)
    assert handle.status == "succeeded"
    assert handle.plan_fingerprint == plan.fingerprint
    assert handle.result is not None
    assert handle.result.experiment_id == graph.id


def test_in_process_provider_rejects_a_plan_it_cannot_reconstruct():
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    plan = plan_experiment(graph).model_copy(update={"experiment_snapshot": {}})
    handle = InProcessNumpyProvider().submit(plan)
    assert handle.status == "failed"
    assert "ExperimentGraph" in handle.error
```

- [ ] **Step 2: Run tests and verify provider contracts are absent**

Run: `uv run --python 3.11 pytest tests/experiment/test_execution_provider.py -q`

Expected: FAIL during import because `execution_provider.py` does not exist.

- [ ] **Step 3: Add the complete provider contract and Tier 1 adapter**

```python
# packages/mrqlab_experiment/mrqlab_experiment/execution_provider.py
from __future__ import annotations

from typing import Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from .kernel import ValidationReport, run_experiment
from .models import ExperimentGraph
from .observations import ResultGraph, build_result_graph
from .resolution import ResolvedExecutionPlan


class ProviderModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CapabilitySet(ProviderModel):
    features: frozenset[str]


class ProviderDescriptor(ProviderModel):
    id: str
    execution_profile: Literal["tier1", "tier2"]
    device: Literal["cpu", "gpu"]
    asynchronous: bool


class ResourceEstimate(ProviderModel):
    work_units: float
    memory_bytes: int


class JobHandle(ProviderModel):
    id: str
    provider_id: str
    plan_fingerprint: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    result: ResultGraph | None = None
    artifact_id: str | None = None
    error: str | None = None


class ExecutionProvider(Protocol):
    descriptor: ProviderDescriptor

    def validate(self, plan: ResolvedExecutionPlan) -> ValidationReport: ...
    def estimate(self, plan: ResolvedExecutionPlan) -> ResourceEstimate: ...
    def submit(self, plan: ResolvedExecutionPlan) -> JobHandle: ...
    def cancel(self, job_id: str) -> None: ...
    def capabilities(self) -> CapabilitySet: ...


class InProcessNumpyProvider:
    descriptor = ProviderDescriptor(id="in_process_numpy", execution_profile="tier1", device="cpu", asynchronous=False)

    def validate(self, plan: ResolvedExecutionPlan) -> ValidationReport:
        from .kernel import validate_experiment
        try:
            graph = ExperimentGraph.model_validate(dict(plan.experiment_snapshot))
        except Exception as exc:
            return ValidationReport(valid=False, errors=({"code": "invalid_snapshot", "message": str(exc)},))
        return validate_experiment(graph)

    def estimate(self, plan: ResolvedExecutionPlan) -> ResourceEstimate:
        return ResourceEstimate(work_units=plan.cost_estimate, memory_bytes=max(1, int(plan.cost_estimate)) * 16)

    def submit(self, plan: ResolvedExecutionPlan) -> JobHandle:
        job_id = str(uuid4())
        try:
            graph = ExperimentGraph.model_validate(dict(plan.experiment_snapshot))
            result = build_result_graph(run_experiment(graph))
            return JobHandle(id=job_id, provider_id=self.descriptor.id, plan_fingerprint=plan.fingerprint, status="succeeded", result=result)
        except Exception as exc:
            return JobHandle(id=job_id, provider_id=self.descriptor.id, plan_fingerprint=plan.fingerprint, status="failed", error=f"ExperimentGraph execution failed: {exc}")

    def cancel(self, job_id: str) -> None:
        raise ValueError("in-process synchronous jobs cannot be cancelled")

    def capabilities(self) -> CapabilitySet:
        return CapabilitySet(features=frozenset({"cpu.numpy", "sync.experiment"}))
```

- [ ] **Step 4: Export provider names and run compatibility tests**

```python
# packages/mrqlab_experiment/mrqlab_experiment/__init__.py additions
from .execution_provider import (
    CapabilitySet, ExecutionProvider, InProcessNumpyProvider, JobHandle,
    ProviderDescriptor, ResourceEstimate,
)

# __all__ additions
"CapabilitySet", "ExecutionProvider", "InProcessNumpyProvider", "JobHandle",
"ProviderDescriptor", "ResourceEstimate",
```

Then run:

Run: `uv run --python 3.11 pytest tests/experiment/test_execution_provider.py tests/experiment/test_execution_plan.py tests/test_api.py -q`

Expected: PASS; HTTP synchronous routes still call the existing application service and do not route through jobs.

- [ ] **Step 5: Perform the ablation pass and commit**

`InProcessNumpyProvider` is the one compatibility adapter proving the provider interface; it does not replace or wrap the HTTP synchronous routes.

```bash
git add packages/mrqlab_experiment/mrqlab_experiment/execution_provider.py packages/mrqlab_experiment/mrqlab_experiment/__init__.py tests/experiment/test_execution_provider.py
git commit -m "feat(compute): add execution provider contract"
```

### Task 12: Add the Tier 2 CPU Job Store and Worker

**Files:**
- Create: `services/local_agent/mrqlab_agent/__init__.py`
- Create: `services/local_agent/mrqlab_agent/models.py`
- Create: `services/local_agent/mrqlab_agent/store.py`
- Create: `services/local_agent/mrqlab_agent/providers.py`
- Create: `tests/local_agent/test_cpu_jobs.py`

**Interfaces:**
- Consumes: `ResolvedExecutionPlan`, `ExecutionProvider`, `run_experiment`, and `build_result_graph`.
- Produces: append-only `JobStore`, content-addressed artifacts, and asynchronous `CpuExecutionProvider`.

- [ ] **Step 1: Write failing CPU lifecycle tests**

```python
# tests/local_agent/test_cpu_jobs.py
import time

from mrqlab_experiment import build_protocol_experiment, plan_experiment
from mrqlab_agent.providers import CpuExecutionProvider
from mrqlab_agent.store import JobStore


def _wait(store, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = store.get_job(job_id)
        if job.status in {"succeeded", "failed", "cancelled"}:
            return job
        time.sleep(.01)
    raise AssertionError("CPU job did not finish")


def test_cpu_worker_emits_events_and_content_addressed_result():
    store = JobStore()
    provider = CpuExecutionProvider(store, max_workers=1)
    plan = plan_experiment(build_protocol_experiment("brain_lesion_t2_tse"))
    handle = provider.submit(plan)
    job = _wait(store, handle.id)
    assert job.status == "succeeded"
    assert [event.kind for event in store.events(handle.id)] == ["queued", "running", "artifact", "succeeded"]
    artifact = store.get_artifact(job.artifact_id)
    assert artifact.media_type == "application/vnd.mrqlab.result+json"
    assert artifact.sha256 == job.artifact_id
    provider.shutdown()


def test_cancelled_queued_job_never_runs():
    store = JobStore()
    provider = CpuExecutionProvider(store, max_workers=0)
    plan = plan_experiment(build_protocol_experiment("brain_lesion_t2_tse"))
    handle = provider.submit(plan)
    provider.cancel(handle.id)
    assert store.get_job(handle.id).status == "cancelled"
```

- [ ] **Step 2: Run tests with the service path and verify modules are absent**

Run: `PYTHONPATH=services/local_agent uv run --python 3.11 pytest tests/local_agent/test_cpu_jobs.py -q`

Expected: FAIL during import because `mrqlab_agent` does not exist.

- [ ] **Step 3: Add complete local wire models**

```python
# services/local_agent/mrqlab_agent/models.py
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class JobRecord(AgentModel):
    id: str
    provider_id: str
    plan_fingerprint: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    artifact_id: str | None = None
    error: str | None = None


class JobEvent(AgentModel):
    sequence: int
    job_id: str
    kind: Literal["queued", "running", "artifact", "succeeded", "failed", "cancelled"]
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str = ""


class Artifact(AgentModel):
    sha256: str
    media_type: str
    content: bytes


class CapabilityResponse(AgentModel):
    runtime: Literal["local"] = "local"
    features: dict[str, bool]
    workers: tuple[dict[str, str], ...]
    license: dict[str, str | bool | None]
```

- [ ] **Step 4: Add the complete thread-safe store**

```python
# services/local_agent/mrqlab_agent/store.py
import hashlib
from threading import RLock

from .models import Artifact, JobEvent, JobRecord


class JobStore:
    def __init__(self):
        self._lock = RLock()
        self._jobs = {}
        self._events = {}
        self._artifacts = {}

    def create(self, job: JobRecord) -> None:
        with self._lock:
            if job.id in self._jobs:
                raise ValueError(f"duplicate job id {job.id}")
            self._jobs[job.id] = job
            self._events[job.id] = []
            self.append(job.id, "queued")

    def get_job(self, job_id: str) -> JobRecord:
        with self._lock:
            try:
                return self._jobs[job_id]
            except KeyError:
                raise KeyError(f"unknown job {job_id}") from None

    def transition(self, job_id: str, status: str, *, artifact_id=None, error=None) -> JobRecord:
        with self._lock:
            current = self.get_job(job_id)
            allowed = {
                "queued": {"running", "cancelled"},
                "running": {"succeeded", "failed", "cancelled"},
                "succeeded": set(), "failed": set(), "cancelled": set(),
            }
            if status not in allowed[current.status]:
                raise ValueError(f"invalid job transition {current.status} -> {status}")
            updated = current.model_copy(update={"status": status, "artifact_id": artifact_id, "error": error})
            self._jobs[job_id] = updated
            self.append(job_id, status, error or "")
            return updated

    def append(self, job_id: str, kind: str, message: str = "") -> JobEvent:
        events = self._events[job_id]
        event = JobEvent(sequence=len(events) + 1, job_id=job_id, kind=kind, message=message)
        events.append(event)
        return event

    def events(self, job_id: str) -> tuple[JobEvent, ...]:
        with self._lock:
            self.get_job(job_id)
            return tuple(self._events[job_id])

    def put_artifact(self, content: bytes, media_type: str) -> Artifact:
        digest = hashlib.sha256(content).hexdigest()
        artifact = Artifact(sha256=digest, media_type=media_type, content=content)
        with self._lock:
            self._artifacts[digest] = artifact
        return artifact

    def get_artifact(self, artifact_id: str) -> Artifact:
        with self._lock:
            try:
                return self._artifacts[artifact_id]
            except KeyError:
                raise KeyError(f"unknown artifact {artifact_id}") from None
```

- [ ] **Step 5: Add the complete CPU provider**

```python
# services/local_agent/mrqlab_agent/providers.py
import json
from concurrent.futures import Future, ThreadPoolExecutor
from uuid import uuid4

from mrqlab_experiment.execution_provider import (
    CapabilitySet, JobHandle, ProviderDescriptor, ResourceEstimate,
)
from mrqlab_experiment.kernel import ValidationReport, run_experiment, validate_experiment
from mrqlab_experiment.models import ExperimentGraph
from mrqlab_experiment.observations import build_result_graph

from .models import JobRecord
from .store import JobStore


class CpuExecutionProvider:
    descriptor = ProviderDescriptor(id="local_cpu_numpy", execution_profile="tier2", device="cpu", asynchronous=True)

    def __init__(self, store: JobStore, max_workers: int = 1):
        self.store = store
        self.executor = ThreadPoolExecutor(max_workers=max_workers) if max_workers > 0 else None
        self.futures: dict[str, Future] = {}

    def validate(self, plan) -> ValidationReport:
        return validate_experiment(ExperimentGraph.model_validate(dict(plan.experiment_snapshot)))

    def estimate(self, plan) -> ResourceEstimate:
        return ResourceEstimate(work_units=plan.cost_estimate, memory_bytes=max(1, int(plan.cost_estimate)) * 16)

    def capabilities(self) -> CapabilitySet:
        return CapabilitySet(features=frozenset({"cpu.numpy", "jobs", "cancel", "artifacts"}))

    def submit(self, plan) -> JobHandle:
        job_id = str(uuid4())
        self.store.create(JobRecord(id=job_id, provider_id=self.descriptor.id, plan_fingerprint=plan.fingerprint, status="queued"))
        if self.executor is not None:
            self.futures[job_id] = self.executor.submit(self._run, job_id, plan)
        return JobHandle(id=job_id, provider_id=self.descriptor.id, plan_fingerprint=plan.fingerprint, status="queued")

    def _run(self, job_id, plan):
        if self.store.get_job(job_id).status == "cancelled":
            return
        self.store.transition(job_id, "running")
        try:
            graph = ExperimentGraph.model_validate(dict(plan.experiment_snapshot))
            result = build_result_graph(run_experiment(graph))
            content = result.model_dump_json().encode()
            artifact = self.store.put_artifact(content, "application/vnd.mrqlab.result+json")
            self.store.append(job_id, "artifact", artifact.sha256)
            self.store.transition(job_id, "succeeded", artifact_id=artifact.sha256)
        except Exception as exc:
            self.store.transition(job_id, "failed", error=str(exc))

    def cancel(self, job_id: str) -> None:
        current = self.store.get_job(job_id)
        if current.status == "queued":
            self.store.transition(job_id, "cancelled")
            future = self.futures.get(job_id)
            if future is not None:
                future.cancel()
            return
        if current.status == "running":
            raise ValueError("running NumPy jobs are not preemptible; cooperative cancellation is a later provider capability")
        raise ValueError(f"cannot cancel job in state {current.status}")

    def shutdown(self):
        if self.executor is not None:
            self.executor.shutdown(wait=True)
```

Create an empty `services/local_agent/mrqlab_agent/__init__.py`.

- [ ] **Step 6: Run lifecycle tests**

Run: `PYTHONPATH=services/local_agent uv run --python 3.11 pytest tests/local_agent/test_cpu_jobs.py -q`

Expected: PASS; queued cancellation is deterministic and no claim of preemptive running-job cancellation is made.

- [ ] **Step 7: Perform the ablation pass and commit**

The in-memory store is the minimum local lifecycle needed before persistence; no queue framework, database, or process orchestration dependency is introduced.

```bash
git add services/local_agent tests/local_agent/test_cpu_jobs.py
git commit -m "feat(agent): add local CPU job lifecycle"
```

### Task 13: Expose Jobs and Add a Fail-Closed Optional GPU Provider Seam

**Files:**
- Modify: `services/local_agent/mrqlab_agent/models.py`
- Modify: `services/local_agent/mrqlab_agent/providers.py`
- Create: `services/local_agent/mrqlab_agent/main.py`
- Modify: `pyproject.toml`
- Create: `tests/local_agent/test_job_api.py`
- Create: `tests/local_agent/test_gpu_provider.py`

**Interfaces:**
- Consumes: Task 12 CPU provider and store.
- Produces: `POST /jobs`, job status/cancel/events/artifacts endpoints, provider registry, and an injected-backend GPU worker that remains unavailable until registered.

- [ ] **Step 1: Write failing API and GPU tests**

```python
# tests/local_agent/test_job_api.py
import time

from fastapi.testclient import TestClient
from mrqlab_experiment import build_protocol_experiment
from mrqlab_agent.main import app

client = TestClient(app)


def test_job_api_runs_cpu_and_serves_opaque_artifact():
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    created = client.post("/jobs", json={"provider_id": "local_cpu_numpy", "experiment": graph.model_dump(mode="json")})
    assert created.status_code == 202
    job_id = created.json()["id"]
    with client.stream("GET", f"/jobs/{job_id}/events") as response:
        assert response.status_code == 200
    status = client.get(f"/jobs/{job_id}").json()
    for _ in range(200):
        if status["status"] in {"succeeded", "failed"}:
            break
        time.sleep(.01)
        status = client.get(f"/jobs/{job_id}").json()
    assert status["status"] == "succeeded"
    artifact = client.get(f"/artifacts/{status['artifact_id']}")
    assert artifact.status_code == 200
    assert artifact.headers["content-type"].startswith("application/vnd.mrqlab.result+json")


def test_job_api_never_accepts_a_filesystem_path():
    response = client.post("/jobs", json={"provider_id": "local_cpu_numpy", "experiment_path": "/tmp/private.json"})
    assert response.status_code == 422
```

```python
# tests/local_agent/test_gpu_provider.py
import pytest
from mrqlab_experiment import build_protocol_experiment, build_result_graph, plan_experiment, run_experiment
from mrqlab_experiment.models import ExperimentGraph
from mrqlab_agent.providers import GpuExecutionProvider, ProviderRegistry
from mrqlab_agent.store import JobStore


def test_gpu_provider_fails_closed_until_an_optional_provider_is_registered():
    registry = ProviderRegistry()
    with pytest.raises(KeyError, match="provider 'local_gpu' is unavailable"):
        registry.get("local_gpu")


def test_registered_gpu_backend_runs_through_the_same_job_contract():
    class FakeGpuBackend:
        def execute(self, plan):
            graph = ExperimentGraph.model_validate(dict(plan.experiment_snapshot))
            return build_result_graph(run_experiment(graph))

    store = JobStore()
    provider = GpuExecutionProvider(store, FakeGpuBackend(), max_workers=1)
    registry = ProviderRegistry()
    registry.register(provider)
    plan = plan_experiment(build_protocol_experiment("brain_lesion_t2_tse"))
    handle = registry.get("local_gpu").submit(plan)
    provider.futures[handle.id].result(timeout=5)
    assert store.get_job(handle.id).status == "succeeded"
    assert "gpu.batch" in provider.capabilities().features
    provider.shutdown()
```

- [ ] **Step 2: Run tests and verify routes/registry are absent**

Run: `PYTHONPATH=services/local_agent uv run --python 3.11 pytest tests/local_agent/test_job_api.py tests/local_agent/test_gpu_provider.py -q`

Expected: FAIL because `main.py` and `ProviderRegistry` do not exist.

- [ ] **Step 3: Add request model and provider registry**

```python
# append to services/local_agent/mrqlab_agent/models.py
from mrqlab_experiment.models import ExperimentGraph


class JobSubmitRequest(AgentModel):
    provider_id: str
    experiment: ExperimentGraph
```

```python
# append to services/local_agent/mrqlab_agent/providers.py
from typing import Protocol


class GpuBackend(Protocol):
    def execute(self, plan): ...


class GpuExecutionProvider(CpuExecutionProvider):
    descriptor = ProviderDescriptor(id="local_gpu", execution_profile="tier2", device="gpu", asynchronous=True)

    def __init__(self, store: JobStore, backend: GpuBackend, max_workers: int = 1):
        super().__init__(store, max_workers=max_workers)
        self.backend = backend

    def capabilities(self) -> CapabilitySet:
        return CapabilitySet(features=frozenset({"gpu.batch", "jobs", "cancel", "artifacts"}))

    def _run(self, job_id, plan):
        if self.store.get_job(job_id).status == "cancelled":
            return
        self.store.transition(job_id, "running")
        try:
            result = self.backend.execute(plan)
            content = result.model_dump_json().encode()
            artifact = self.store.put_artifact(content, "application/vnd.mrqlab.result+json")
            self.store.append(job_id, "artifact", artifact.sha256)
            self.store.transition(job_id, "succeeded", artifact_id=artifact.sha256)
        except Exception as exc:
            self.store.transition(job_id, "failed", error=str(exc))


class ProviderRegistry:
    def __init__(self, providers=()):
        self._providers = {provider.descriptor.id: provider for provider in providers}

    def register(self, provider) -> None:
        provider_id = provider.descriptor.id
        if provider_id in self._providers:
            raise ValueError(f"duplicate provider {provider_id!r}")
        self._providers[provider_id] = provider

    def get(self, provider_id: str):
        try:
            return self._providers[provider_id]
        except KeyError:
            raise KeyError(f"provider {provider_id!r} is unavailable") from None

    def descriptors(self):
        return tuple(provider.descriptor for provider in self._providers.values())
```

- [ ] **Step 4: Add the complete local job API**

```python
# services/local_agent/mrqlab_agent/main.py
from fastapi import FastAPI, HTTPException, Response, status

from mrqlab_experiment import plan_experiment

from .models import JobSubmitRequest
from .providers import CpuExecutionProvider, ProviderRegistry
from .store import JobStore

app = FastAPI(title="MRQLab Local Agent")
store = JobStore()
cpu_provider = CpuExecutionProvider(store)
providers = ProviderRegistry((cpu_provider,))


@app.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
def create_job(request: JobSubmitRequest):
    try:
        provider = providers.get(request.provider_id)
        plan = plan_experiment(request.experiment)
        report = provider.validate(plan)
        if not report.valid:
            raise ValueError(report.errors[0].message)
        return provider.submit(plan)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    try:
        return store.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    try:
        job = store.get_job(job_id)
        providers.get(job.provider_id).cancel(job_id)
        return store.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/jobs/{job_id}/events")
def job_events(job_id: str):
    try:
        return {"events": store.events(job_id)}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str):
    try:
        artifact = store.get_artifact(artifact_id)
        return Response(content=artifact.content, media_type=artifact.media_type)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
```

- [ ] **Step 5: Add the service package path without a new dependency**

Update `pyproject.toml`:

```toml
[tool.setuptools.packages.find]
where = ["packages/sequence-ir", "packages/physics", "packages/recon", "packages/mrqlab_experiment", "services/api", "services/local_agent"]
include = ["mrqlab_sequence*", "mrqlab_physics*", "mrqlab_recon*", "mrqlab_experiment*", "mrqlab_api*", "mrqlab_agent*"]

[tool.pytest.ini_options]
pythonpath = ["packages/sequence-ir", "packages/physics", "packages/recon", "packages/mrqlab_experiment", "services/api", "services/local_agent"]
testpaths = ["tests"]
```

- [ ] **Step 6: Run API, provider, and synchronous-route regressions**

Run: `uv run --python 3.11 pytest tests/local_agent/test_cpu_jobs.py tests/local_agent/test_job_api.py tests/local_agent/test_gpu_provider.py tests/test_api.py -q`

Expected: PASS; `local_gpu` is absent and fails closed by default, an explicitly registered backend uses the same lifecycle, and `/experiments/run*` remain synchronous.

- [ ] **Step 7: Perform the ablation pass and commit**

The registry is required by both CPU selection and the optional GPU worker. `GpuExecutionProvider` owns lifecycle only; injected backend distributions own numerical GPU execution, so no CUDA/Torch dependency is added to the core package.

```bash
git add services/local_agent pyproject.toml tests/local_agent
git commit -m "feat(agent): expose local jobs and provider registry"
```

### Task 14: Verify Ed25519 Device Leases and Entitlements

**Files:**
- Modify: `pyproject.toml`
- Modify: `services/local_agent/mrqlab_agent/models.py`
- Create: `services/local_agent/mrqlab_agent/license.py`
- Create: `tests/local_agent/test_license.py`

**Interfaces:**
- Consumes: trusted Ed25519 public keys, local device id, wall/monotonic clocks, and a compact signed lease token.
- Produces: `DeviceIdentity`, `LeaseClaims`, `LeaseDecision`, `TrustedClock`, `LeaseVerifier`, and `require_entitlement`.

- [ ] **Step 1: Obtain explicit dependency approval before changing `pyproject.toml`**

The executor must present this exact reason to the human: `cryptography>=46,<47` supplies audited Ed25519 signature verification; implementing signature primitives inside MRQLab would create an unsafe security boundary. Do not continue this task until approval is recorded. This gate does not unlock any other dependency.

- [ ] **Step 2: Write failing lease and clock tests**

```python
# tests/local_agent/test_license.py
import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from mrqlab_agent.license import LeaseVerifier, TrustedClock, build_registration_request, require_entitlement
from mrqlab_agent.models import DeviceIdentity


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _token(key, claims, kid="test-key"):
    header = _b64(json.dumps({"alg": "EdDSA", "kid": kid}, separators=(",", ":")).encode())
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = _b64(key.sign(f"{header}.{payload}".encode()))
    return f"{header}.{payload}.{signature}"


def _claims(**updates):
    claims = {
        "iss": "mrqlab-license", "aud": "mrqlab-local-runtime", "lease_id": "lease-1",
        "organization_id": "org-1", "device_id": "device-1", "device_public_key_hash": "pkh",
        "fingerprint_hash": "fph", "issued_at": 1000, "not_before": 1000,
        "expires_at": 2000, "offline_grace_until": 2300, "product": "mrqlab-pro",
        "features": ["compute.cpu", "jobs.cancel"], "limits": {"max_concurrent_jobs": 2},
        "software": {"min_version": "1.0.0", "max_major": 1}, "key_id": "test-key",
    }
    claims.update(updates)
    return claims


def test_valid_device_lease_and_entitlement():
    private = Ed25519PrivateKey.generate()
    device = DeviceIdentity(device_id="device-1", device_public_key_hash="pkh", fingerprint_hash="fph")
    verifier = LeaseVerifier({"test-key": private.public_key()}, device)
    decision = verifier.verify(_token(private, _claims()), wall_time=1500, monotonic_time=10)
    assert decision.state == "active"
    require_entitlement(decision, "compute.cpu")


def test_wrong_device_expired_and_unentitled_fail_closed():
    private = Ed25519PrivateKey.generate()
    device = DeviceIdentity(device_id="device-1", device_public_key_hash="pkh", fingerprint_hash="fph")
    verifier = LeaseVerifier({"test-key": private.public_key()}, device)
    with pytest.raises(ValueError, match="wrong device"):
        verifier.verify(_token(private, _claims(device_id="device-2")), wall_time=1500, monotonic_time=10)
    with pytest.raises(ValueError, match="expired beyond offline grace"):
        verifier.verify(_token(private, _claims()), wall_time=2400, monotonic_time=20)
    decision = verifier.verify(_token(private, _claims()), wall_time=2100, monotonic_time=20)
    assert decision.state == "offline_grace"
    with pytest.raises(PermissionError, match="gpu"):
        require_entitlement(decision, "compute.gpu")


def test_trusted_clock_detects_material_wall_clock_rollback():
    clock = TrustedClock(max_rollback_s=5)
    clock.observe(wall_time=1500, monotonic_time=10)
    with pytest.raises(ValueError, match="clock rollback"):
        clock.now(wall_time=1400, monotonic_time=20)


def test_device_registration_exports_public_material_and_canonical_fingerprint_only():
    private = Ed25519PrivateKey.generate()
    request = build_registration_request(
        "device-1", private.public_key(), {"machine_id": "m1", "gpu_uuid": "g1"}
    )
    assert request.device_id == "device-1"
    assert request.device_public_key_b64
    assert request.fingerprint_hash
    assert "private" not in request.model_dump_json().lower()
```

- [ ] **Step 3: Run tests and verify lease code is absent**

Run: `PYTHONPATH=services/local_agent uv run --python 3.11 pytest tests/local_agent/test_license.py -q`

Expected: FAIL during import because `license.py` does not exist.

- [ ] **Step 4: Add the approved dependency and complete lease models**

Add exactly one production dependency in `pyproject.toml`:

```toml
dependencies = ["fastapi>=0.110", "uvicorn>=0.27", "pydantic>=2", "numpy>=1.26", "cryptography>=46,<47"]
```

Append to `services/local_agent/mrqlab_agent/models.py`:

```python
class DeviceIdentity(AgentModel):
    device_id: str
    device_public_key_hash: str
    fingerprint_hash: str


class DeviceRegistrationRequest(AgentModel):
    device_id: str
    device_public_key_b64: str
    device_public_key_hash: str
    fingerprint_hash: str


class LeaseClaims(AgentModel):
    iss: str
    aud: str
    lease_id: str
    organization_id: str
    device_id: str
    device_public_key_hash: str
    fingerprint_hash: str
    issued_at: float
    not_before: float
    expires_at: float
    offline_grace_until: float
    product: str
    features: frozenset[str]
    limits: dict[str, int]
    software: dict[str, str | int]
    key_id: str


class LeaseDecision(AgentModel):
    state: Literal["active", "offline_grace"]
    claims: LeaseClaims
```

- [ ] **Step 5: Add the complete Ed25519 verifier and trusted clock**

```python
# services/local_agent/mrqlab_agent/license.py
from __future__ import annotations

import base64
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from .models import DeviceIdentity, DeviceRegistrationRequest, LeaseClaims, LeaseDecision


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


class TrustedClock:
    def __init__(self, max_rollback_s: float = 300):
        self.max_rollback_s = max_rollback_s
        self._wall = None
        self._monotonic = None

    def observe(self, *, wall_time: float, monotonic_time: float) -> None:
        self._wall = wall_time
        self._monotonic = monotonic_time

    def now(self, *, wall_time: float, monotonic_time: float) -> float:
        if self._wall is None:
            self.observe(wall_time=wall_time, monotonic_time=monotonic_time)
            return wall_time
        expected = self._wall + max(0, monotonic_time - self._monotonic)
        if wall_time < expected - self.max_rollback_s:
            raise ValueError("wall clock rollback exceeds trusted-time tolerance")
        current = max(wall_time, expected)
        self.observe(wall_time=current, monotonic_time=monotonic_time)
        return current


class LeaseVerifier:
    def __init__(self, trusted_keys: dict[str, Ed25519PublicKey], device: DeviceIdentity, clock: TrustedClock | None = None):
        self.trusted_keys = dict(trusted_keys)
        self.device = device
        self.clock = clock or TrustedClock()

    def verify(self, token: str, *, wall_time: float, monotonic_time: float) -> LeaseDecision:
        try:
            encoded_header, encoded_payload, encoded_signature = token.split(".")
            header = json.loads(_decode(encoded_header))
            payload = json.loads(_decode(encoded_payload))
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError("malformed lease token") from exc
        if header.get("alg") != "EdDSA":
            raise ValueError("lease algorithm must be EdDSA")
        kid = header.get("kid")
        try:
            key = self.trusted_keys[kid]
        except KeyError:
            raise ValueError(f"untrusted lease key id {kid!r}") from None
        try:
            key.verify(_decode(encoded_signature), f"{encoded_header}.{encoded_payload}".encode())
        except InvalidSignature as exc:
            raise ValueError("invalid lease signature") from exc
        claims = LeaseClaims.model_validate(payload)
        if claims.key_id != kid:
            raise ValueError("lease key id mismatch")
        if claims.iss != "mrqlab-license" or claims.aud != "mrqlab-local-runtime":
            raise ValueError("lease issuer or audience mismatch")
        if claims.device_id != self.device.device_id:
            raise ValueError("lease is bound to the wrong device")
        if claims.device_public_key_hash != self.device.device_public_key_hash:
            raise ValueError("lease public-key binding does not match this device")
        if claims.fingerprint_hash != self.device.fingerprint_hash:
            raise ValueError("lease hardware fingerprint does not match this device")
        now = self.clock.now(wall_time=wall_time, monotonic_time=monotonic_time)
        if now < claims.not_before:
            raise ValueError("lease is not yet valid")
        if now <= claims.expires_at:
            return LeaseDecision(state="active", claims=claims)
        if now <= claims.offline_grace_until:
            return LeaseDecision(state="offline_grace", claims=claims)
        raise ValueError("lease expired beyond offline grace")


def require_entitlement(decision: LeaseDecision, feature: str) -> None:
    if feature not in decision.claims.features:
        raise PermissionError(f"lease does not entitle feature {feature!r}")


def build_registration_request(
    device_id: str,
    public_key: Ed25519PublicKey,
    fingerprint_components: dict[str, str],
) -> DeviceRegistrationRequest:
    if not fingerprint_components or any(not key or not value for key, value in fingerprint_components.items()):
        raise ValueError("device fingerprint components must be non-empty")
    public_bytes = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    canonical = json.dumps(fingerprint_components, sort_keys=True, separators=(",", ":")).encode()
    return DeviceRegistrationRequest(
        device_id=device_id,
        device_public_key_b64=base64.urlsafe_b64encode(public_bytes).rstrip(b"=").decode(),
        device_public_key_hash=hashlib.sha256(public_bytes).hexdigest(),
        fingerprint_hash=hashlib.sha256(canonical).hexdigest(),
    )
```

- [ ] **Step 6: Run lease tests and the no-license-in-physics gate**

Run: `uv run --python 3.11 pytest tests/local_agent/test_license.py -q && rg -n "LeaseVerifier|require_entitlement|cryptography" packages/physics`

Expected: lease tests PASS; the search returns no matches.

- [ ] **Step 7: Perform the ablation pass and commit**

The crypto library supplies only signature verification primitives. Lease policy, trusted time, and entitlement remain explicit local-gateway code; no JWT framework or cloud client is added.

```bash
git add pyproject.toml services/local_agent/mrqlab_agent/models.py services/local_agent/mrqlab_agent/license.py tests/local_agent/test_license.py
git commit -m "feat(agent): verify signed device leases"
```

### Task 15: Enforce Pairing, Origin, CSRF, Lease, and Safe Capability Discovery

**Files:**
- Create: `services/local_agent/mrqlab_agent/security.py`
- Modify: `services/local_agent/mrqlab_agent/main.py`
- Modify: `tests/local_agent/test_job_api.py`
- Create: `tests/local_agent/test_security.py`

**Interfaces:**
- Consumes: pairing secret, strict origin allowlist, `LeaseVerifier`, and provider registry.
- Produces: request security dependency, execution entitlement dependency, and `GET /v1/capabilities` without secret material.

- [ ] **Step 1: Write failing security tests**

```python
# tests/local_agent/test_security.py
from fastapi.testclient import TestClient

from mrqlab_agent.main import app, local_security

client = TestClient(app)


def _headers(**updates):
    headers = {
        "origin": "https://app.mrqlab.local",
        "x-mrqlab-pairing": local_security.pairing_secret,
        "x-mrqlab-csrf": local_security.csrf_token,
    }
    headers.update(updates)
    return headers


def test_capabilities_require_pairing_and_return_no_secrets():
    assert client.get("/v1/capabilities", headers={"origin": "https://app.mrqlab.local"}).status_code == 401
    response = client.get("/v1/capabilities", headers=_headers())
    assert response.status_code == 200
    text = response.text.lower()
    assert "pairing_secret" not in text
    assert "private" not in text
    assert "token" not in text


def test_wrong_origin_and_missing_csrf_fail_before_mutation():
    assert client.post("/jobs", json={}, headers=_headers(origin="https://evil.example")).status_code == 403
    headers = _headers()
    headers.pop("x-mrqlab-csrf")
    assert client.post("/jobs", json={}, headers=headers).status_code == 403
```

- [ ] **Step 2: Run tests and verify the security dependency is absent**

Run: `uv run --python 3.11 pytest tests/local_agent/test_security.py -q`

Expected: FAIL because `security.py`, `local_security`, and `/v1/capabilities` do not exist.

- [ ] **Step 3: Add the complete local request-security module**

```python
# services/local_agent/mrqlab_agent/security.py
import hashlib
import hmac
import secrets

from fastapi import HTTPException, Request


class LocalSecurity:
    def __init__(self, allowed_origins: frozenset[str], pairing_secret: str | None = None):
        self.allowed_origins = allowed_origins
        self.pairing_secret = pairing_secret or secrets.token_urlsafe(32)
        self.csrf_token = hmac.new(self.pairing_secret.encode(), b"mrqlab-csrf", hashlib.sha256).hexdigest()

    def verify(self, request: Request) -> None:
        host = request.client.host if request.client else ""
        if host not in {"127.0.0.1", "::1", "testclient"}:
            raise HTTPException(403, "local agent accepts loopback clients only")
        origin = request.headers.get("origin")
        if origin is not None and origin not in self.allowed_origins:
            raise HTTPException(403, "origin is not allowed")
        supplied = request.headers.get("x-mrqlab-pairing", "")
        if not hmac.compare_digest(supplied, self.pairing_secret):
            raise HTTPException(401, "local pairing is required")
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            csrf = request.headers.get("x-mrqlab-csrf", "")
            if not hmac.compare_digest(csrf, self.csrf_token):
                raise HTTPException(403, "valid CSRF token is required")
```

- [ ] **Step 4: Replace the local API with this complete secured version**

```python
# services/local_agent/mrqlab_agent/main.py
import time
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status

from mrqlab_experiment import plan_experiment

from .license import LeaseVerifier, require_entitlement
from .models import CapabilityResponse, JobSubmitRequest
from .providers import CpuExecutionProvider, ProviderRegistry
from .security import LocalSecurity
from .store import JobStore

app = FastAPI(title="MRQLab Local Agent")
store = JobStore()
cpu_provider = CpuExecutionProvider(store)
providers = ProviderRegistry((cpu_provider,))
local_security = LocalSecurity(frozenset({"https://app.mrqlab.local", "http://127.0.0.1:3000"}))
lease_verifier: LeaseVerifier | None = None


def require_local_security(request: Request):
    local_security.verify(request)


def require_compute_entitlement(authorization: str = Header(default="")):
    if lease_verifier is None:
        raise HTTPException(503, "lease verifier is not configured")
    if not authorization.startswith("Lease "):
        raise HTTPException(401, "signed device lease is required")
    try:
        decision = lease_verifier.verify(
            authorization.removeprefix("Lease "),
            wall_time=time.time(), monotonic_time=time.monotonic(),
        )
        require_entitlement(decision, "compute.cpu")
        return decision
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc


@app.post(
    "/jobs",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_local_security), Depends(require_compute_entitlement)],
)
def create_job(request: JobSubmitRequest):
    try:
        provider = providers.get(request.provider_id)
        plan = plan_experiment(request.experiment)
        report = provider.validate(plan)
        if not report.valid:
            raise ValueError(report.errors[0].message)
        return provider.submit(plan)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/jobs/{job_id}", dependencies=[Depends(require_local_security)])
def get_job(job_id: str):
    try:
        return store.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post(
    "/jobs/{job_id}/cancel",
    dependencies=[Depends(require_local_security), Depends(require_compute_entitlement)],
)
def cancel_job(job_id: str):
    try:
        job = store.get_job(job_id)
        providers.get(job.provider_id).cancel(job_id)
        return store.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/jobs/{job_id}/events", dependencies=[Depends(require_local_security)])
def job_events(job_id: str):
    try:
        return {"events": store.events(job_id)}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/artifacts/{artifact_id}", dependencies=[Depends(require_local_security)])
def get_artifact(artifact_id: str):
    try:
        artifact = store.get_artifact(artifact_id)
        return Response(content=artifact.content, media_type=artifact.media_type)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/v1/capabilities", dependencies=[Depends(require_local_security)])
def capabilities():
    descriptors = providers.descriptors()
    return CapabilityResponse(
        features={feature: True for provider in (cpu_provider,) for feature in provider.capabilities().features},
        workers=tuple({"id": item.id, "device": item.device, "status": "ready"} for item in descriptors),
        license={"state": "configured" if lease_verifier is not None else "unconfigured", "offline": False, "expires_at": None},
    )
```

- [ ] **Step 5: Replace the job API test with this secured version**

```python
# tests/local_agent/test_job_api.py
import time

import pytest
from fastapi.testclient import TestClient

from mrqlab_experiment import build_protocol_experiment
from mrqlab_agent.main import app, local_security, require_compute_entitlement

HEADERS = {
    "origin": "https://app.mrqlab.local",
    "x-mrqlab-pairing": local_security.pairing_secret,
    "x-mrqlab-csrf": local_security.csrf_token,
}
client = TestClient(app)


@pytest.fixture(autouse=True)
def entitled_request():
    app.dependency_overrides[require_compute_entitlement] = lambda: object()
    yield
    app.dependency_overrides.clear()


def test_job_api_runs_cpu_and_serves_opaque_artifact():
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    created = client.post(
        "/jobs",
        json={"provider_id": "local_cpu_numpy", "experiment": graph.model_dump(mode="json")},
        headers=HEADERS,
    )
    assert created.status_code == 202
    job_id = created.json()["id"]
    assert client.get(f"/jobs/{job_id}/events", headers=HEADERS).status_code == 200
    status_body = client.get(f"/jobs/{job_id}", headers=HEADERS).json()
    for _ in range(200):
        if status_body["status"] in {"succeeded", "failed"}:
            break
        time.sleep(.01)
        status_body = client.get(f"/jobs/{job_id}", headers=HEADERS).json()
    assert status_body["status"] == "succeeded"
    artifact = client.get(f"/artifacts/{status_body['artifact_id']}", headers=HEADERS)
    assert artifact.status_code == 200
    assert artifact.headers["content-type"].startswith("application/vnd.mrqlab.result+json")


def test_job_api_never_accepts_a_filesystem_path():
    response = client.post(
        "/jobs",
        json={"provider_id": "local_cpu_numpy", "experiment_path": "/tmp/private.json"},
        headers=HEADERS,
    )
    assert response.status_code == 422
```

- [ ] **Step 6: Run security, lease, job, and no-secret gates**

Run: `uv run --python 3.11 pytest tests/local_agent/test_security.py tests/local_agent/test_license.py tests/local_agent/test_job_api.py -q && rg -n "pairing_secret|private_key|authorization" apps/web`

Expected: tests PASS; the web search returns no embedded secret or private-key code.

- [ ] **Step 7: Perform the ablation pass and commit**

`LocalSecurity` owns only local transport checks; `LeaseVerifier` owns signed claims; provider capability remains separate. No middleware duplicates these checks.

```bash
git add services/local_agent/mrqlab_agent tests/local_agent
git commit -m "feat(agent): secure local execution gateway"
```

### Task 16: Close Milestone C Documentation and Runtime Boundaries

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/ROADMAP.md`
- Create: `tests/local_agent/test_architecture_boundaries.py`

**Interfaces:**
- Consumes: Tasks 11–15.
- Produces: documented provider/job/lease boundary and static enforcement that physics and browser code contain no licensing secrets.

- [ ] **Step 1: Write failing boundary tests**

```python
# tests/local_agent/test_architecture_boundaries.py
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_license_code_lives_only_at_the_execution_gateway():
    physics = "\n".join(path.read_text() for path in (ROOT / "packages/physics").rglob("*.py"))
    assert "LeaseVerifier" not in physics
    assert "require_entitlement" not in physics


def test_browser_has_no_lease_or_device_private_keys():
    web = "\n".join(path.read_text() for path in (ROOT / "apps/web").rglob("*.ts*"))
    assert "Ed25519PrivateKey" not in web
    assert "device_private_key" not in web
    assert "lease_signing_key" not in web


def test_architecture_documents_capability_entitlement_and_sync_boundary():
    text = (ROOT / "docs/ARCHITECTURE.md").read_text()
    assert "Capability is not entitlement" in text
    assert "POST /experiments/run remains synchronous" in text
    assert "POST /jobs" in text
    assert "Ed25519" in text
    assert "loopback" in text
```

- [ ] **Step 2: Run the test and verify documentation is incomplete**

Run: `uv run --python 3.11 pytest tests/local_agent/test_architecture_boundaries.py -q`

Expected: FAIL only on the new documentation assertions.

- [ ] **Step 3: Add the exact local-compute architecture section**

Append to `docs/ARCHITECTURE.md`:

```markdown
## Licensed local compute boundary

`POST /experiments/run` remains synchronous Tier 1 NumPy execution. Tier 2 is a separate loopback local gateway exposing `POST /jobs`, status, cancel, events, artifacts, and read-only capability discovery. CPU workers ship first; GPU remains an optional provider that fails closed until registered.

Capability is not entitlement. Provider capability answers whether work can execute; an Ed25519-signed device lease answers whether it may execute. The execution gateway verifies audience, device binding, time, offline grace, feature entitlement, and limits before provider submission. Physics operators do not import licensing code.

The gateway binds loopback, enforces a strict browser-origin allowlist, local pairing, CSRF checks, and opaque artifact ids. The browser receives capability and lease-state summaries only; it never receives private keys, signing keys, or long-lived API keys.
```

Update the Milestone C roadmap block with completed contract names while retaining the RUO and hardware-review boundaries.

- [ ] **Step 4: Run C and full static gates**

Run:

```bash
uv run --python 3.11 pytest tests/local_agent tests/experiment/test_execution_provider.py -q
rg -n "LeaseVerifier|require_entitlement|cryptography" packages/physics
rg -n "Ed25519PrivateKey|device_private_key|lease_signing_key" apps/web
git diff --check
```

Expected: tests PASS; both searches return no matches; `git diff --check` is silent.

- [ ] **Step 5: Perform the Milestone C ablation pass and commit**

Confirm there is one local gateway, one provider registry, one lease verifier, one request-security object, no cloud control-plane payload handling, no GPU framework dependency, and no license code in physics.

```bash
git add docs/ARCHITECTURE.md docs/ROADMAP.md tests/local_agent/test_architecture_boundaries.py
git commit -m "docs(agent): lock local compute security boundary"
```

### Task 17: Run Full Platform Acceptance

**Files:**
- Test only; no file changes.

**Interfaces:**
- Consumes: all completed tasks.
- Produces: pass/fail evidence in the executing-plans checkpoint; no generated or hand-edited evidence file.

- [ ] **Step 1: Record the reproducibility environment in the execution checkpoint**

Run:

```bash
git rev-parse HEAD
.venv/bin/python --version
node --version
npm --version
uname -a
system_profiler SPHardwareDataType
```

Expected: every command exits zero. Copy the exact output into the executing-plans checkpoint without estimating hardware or version values.

- [ ] **Step 2: Run the complete Python gate**

Run:

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/python -m pytest -q
```

Expected: PASS. Record the actual test count and duration; do not estimate or round them.

- [ ] **Step 3: Run the complete web gate**

Run: `cd apps/web && npm ci && npm test && npm run typecheck && npm run build`

Expected: PASS. Record the actual Vitest file/test counts and build result.

- [ ] **Step 4: Run architecture, security, and scope checks**

Run:

```bash
rg -n "LeaseVerifier|require_entitlement|cryptography" packages/physics
rg -n "Ed25519PrivateKey|device_private_key|lease_signing_key" apps/web
rg -n "pulseq" apps/web packages/mrqlab_experiment/mrqlab_experiment
rg -n "diagnostic use|clinical-ready|scanner-ready" README.md docs packages apps services
git diff --check
```

Expected: first two searches have no matches; Pulseq appears only in boundary documentation/tests and no adapter; prohibited product claims have no affirmative matches; `git diff --check` is silent.

- [ ] **Step 5: Perform the final ablation pass**

Check item by item:

- Delete functions, classes, parameters, and configuration items without callers.
- Delete one-use wrappers that do not enforce a boundary.
- Delete interfaces, layers, and configuration reserved only for an unspecified future.
- Keep `ExecutionProvider` because Tier 1 and Tier 2 both implement it.
- Keep three IR contracts because lowering changes representation and validation evidence at each boundary.
- Keep lease/security separation because capability and entitlement have different trust inputs.
- Confirm no behavior refactor was mixed into an unrelated structural commit.

- [ ] **Step 6: Verify the worktree contains no acceptance-only edits**

Run: `git status --porcelain`

Expected: no new files or modifications were created by Task 17; any listed paths belong to Tasks 1–16 and their commits.

## Immediate Honesty — Documented, Not Implemented on the Plan Branch

- PR #52 `e43f19c` is chrome v0.76.15 Lego RUN fail-closed. Cloud verdict is land; merge is the human's call. Pages remains v0.76.14 until merge and deployment.
- After merge: Pages-first.
- Optional next honesty seam: silent diffusion off for empty tissue ADC versus composed `fov_m + epg`.
- That seam is not a v0.76.16 nit pack.
- Stop 0.76.x slider/caption nits.

## Out of Scope / Do-Not List

No monorepo rewrite; no license in kernel; no GPU-ize `/experiments/run`; no SequenceIR = scanner-executable; no clinical-ready claim; no simultaneous MRS+DCE+CEST-imaging+full PDG+GPU+Pulseq+licensing; do not delete safety disclaimers; no lease keys in the browser; no FLAIR/MOLLI/MESE engines; no restack Compare/Optimize/click-to-place; no Pi product landing.

- No monorepo rewrite.
- No license in kernel.
- No GPU-ize `/experiments/run`.
- No SequenceIR = scanner-executable.
- No clinical-ready claim.
- No simultaneous MRS+DCE+CEST-imaging+full PDG+GPU+Pulseq+licensing.
- Do not delete safety disclaimers.
- No lease keys in the browser.
- No FLAIR/MOLLI/MESE engines.
- No restack Compare/Optimize/click-to-place.
- No Pi product landing.
- Do not start License Server, GPU worker, Pulseq, shaped-RF designer, Hybrid restacking, N-pool, MRS, or CEST imaging in Milestone A.

## Self-Review Against the Locked Specification

### Spec coverage

| Requirement | Owning task |
|---|---|
| Exactly two A verticals | Task 2 |
| All named clinical models | Task 1 |
| Extend ExperimentGraph/kernel rather than replace it | Tasks 3–5 |
| Immutable fingerprint, explicit units/defaults/provenance | Task 4 |
| Shared Observation provenance | Task 5 |
| Honest unwired controls | Task 6 |
| ssEPG/PDG docs drift without breaking required literals | Task 7 |
| Logical → Executable → Export IR | Tasks 8–10 |
| Exact export states and no Pulseq frontend | Task 10 |
| ExecutionProvider and synchronous route preservation | Task 11 |
| CPU then optional GPU fail-closed | Tasks 12–13 |
| Jobs, cancel, events, artifacts | Tasks 12–13 |
| Device registration contract, Ed25519 lease, offline grace, entitlement | Task 14 |
| Loopback, CORS/origin, CSRF, pairing | Task 15 |
| No licensing in physics and no browser keys | Tasks 14–16 |
| Reproducible test evidence and ablation | Task 17 |

Coverage result: every locked requirement maps to a test-owning task. Parked capabilities are bounded by explicit wave gates rather than hidden implementation steps.

### Placeholder scan

The plan contains concrete paths, signatures, assertions, commands, expected failures, complete new-file bodies, and exact existing-file edits. Deferred product areas are explicitly excluded or wave-gated; no implementation step asks an executor to infer missing behavior.

### Type consistency

- Task 1 defines every clinical type consumed by Tasks 2–10.
- `ClinicalProtocolRecipe.experiment_recipe_id` is the only compatibility bridge to existing recipe ids.
- `ResolvedExecutionPlan.experiment_snapshot` is deeply frozen and reconstructs `ExperimentGraph` for providers.
- `ExecutionPlan` remains a compatibility alias; current callers keep `.engine`, `.representation`, `.options`, `.physics_status`, and `.stale_dependencies`.
- `ParameterState` uses the exact seven locked states in Python and TypeScript.
- `ExecutionProvider.submit` consumes only `ResolvedExecutionPlan` in Tier 1 and Tier 2.
- `JobHandle`, `JobRecord`, and API status literals use the same five lifecycle values.
- Export-state strings match the five locked names exactly.
- Lease features are checked at the gateway before provider submission; provider capabilities remain independent.

### Review-focus closure

- Task 1 exercises non-finite/unitless values and tissue reference failures.
- Task 4 exercises canonical hashing, deep immutability, and caller detachment.
- Task 9 exercises timing quantization and RF/ADC safety-boundary failures.
- Task 14 exercises device, expiry, offline grace, entitlement, and rollback failures.
- Task 15 exercises loopback/origin, pairing, CSRF, and no-secret capability responses.

## Execution Handoff — Human Gate

Plan implementation begins at Task 1 only after the human says `开工`. The executor must use `superpowers:executing-plans` (or the explicitly chosen subagent-driven method) and must stop at each wave gate. Do not invoke or simulate `collab: Wait`; return control to the human at the Milestone A, B, and dependency-approval gates.

**executing-plans starts at Task 1 only after human says 开工; anti-`collab: Wait`.**
