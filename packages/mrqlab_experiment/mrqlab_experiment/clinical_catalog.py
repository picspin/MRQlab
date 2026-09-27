from .clinical import (
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


RESEARCH_3T = ScannerProfile(
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


BRAIN_LESION_T2_TSE = ClinicalProtocolRecipe(
    id="brain_lesion_t2_tse",
    version="1.0.0",
    vertical="brain_lesion_t2_tse",
    question=ClinicalQuestion(
        anatomy="brain",
        research_question="Maximize lesion-to-white-matter T2 contrast without treating CSF brightness as lesion evidence",
        target_finding="T2-hyperintense lesion",
        contrast_mechanism="T2-weighted turbo spin echo",
    ),
    tissue_priors=TissuePriorSet(
        id="brain-lesion-t2-priors",
        version="1.0.0",
        tissues=(
            TissuePrior(
                id="lesion",
                label="T2-hyperintense lesion",
                role="target",
                t1=1.4,
                t2=.12,
                proton_density=.95,
            ),
            TissuePrior(
                id="white_matter",
                label="White matter",
                role="reference",
                t1=.9,
                t2=.08,
                proton_density=.75,
            ),
            TissuePrior(
                id="gray_matter",
                label="Gray matter",
                role="background",
                t1=1.3,
                t2=.10,
                proton_density=.85,
            ),
            TissuePrior(
                id="csf",
                label="CSF",
                role="background",
                t1=4.0,
                t2=2.0,
                proton_density=1.0,
            ),
        ),
        targets=(Target(tissue_id="lesion", rationale="research contrast target"),),
        references=(
            Reference(tissue_id="white_matter", rationale="normal-appearing reference"),
        ),
        confounders=(
            Confounder(tissue_id="gray_matter", rationale="intermediate T2 parenchyma"),
            Confounder(tissue_id="csf", rationale="long-T2 fluid"),
        ),
    ),
    objective=ObjectiveVector(
        terms=(
            ContrastMetric(
                id="lesion-vs-wm",
                target_tissue_id="lesion",
                reference_tissue_id="white_matter",
                metric="normalized_cnr_proxy",
                direction="maximize",
                weight=1.0,
            ),
        )
    ),
    robustness=(
        RobustnessScenario(
            id="routine-3t",
            delta_b0_hz=(-50, 50),
            b1_scale=(.85, 1.15),
            motion_mm=(0, 1),
            t1_scale=(.9, 1.1),
            t2_scale=(.9, 1.1),
        ),
    ),
    constraints=(
        AcquisitionConstraint(
            id="scan-time",
            metric="scan_time_s",
            operator="le",
            value=300,
            unit="s",
            severity="hard",
        ),
        AcquisitionConstraint(
            id="resolution",
            metric="resolution_mm",
            operator="le",
            value=1.0,
            unit="mm",
            severity="soft",
        ),
    ),
    scanner_profile=RESEARCH_3T,
    experiment_recipe_id="brain_t2_tse",
)


KNEE_CARTILAGE_MENISCUS_PD_T2_TSE = ClinicalProtocolRecipe(
    id="knee_cartilage_meniscus_pd_t2_tse",
    version="1.0.0",
    vertical="knee_cartilage_meniscus_pd_t2_tse",
    question=ClinicalQuestion(
        anatomy="knee",
        research_question="Separate cartilage and meniscal pathology from normal fibrocartilage while tracking fluid and fat confounders",
        target_finding="cartilage fissure or meniscal tear",
        contrast_mechanism="proton-density/T2 turbo spin echo",
    ),
    tissue_priors=TissuePriorSet(
        id="knee-pd-t2-priors",
        version="1.0.0",
        tissues=(
            TissuePrior(
                id="cartilage",
                label="Hyaline cartilage",
                role="target",
                t1=1.2,
                t2=.04,
                proton_density=.80,
            ),
            TissuePrior(
                id="meniscal_tear",
                label="Meniscal tear",
                role="target",
                t1=1.5,
                t2=.09,
                proton_density=.95,
            ),
            TissuePrior(
                id="meniscus",
                label="Fibrocartilage meniscus",
                role="reference",
                t1=.9,
                t2=.015,
                proton_density=.50,
            ),
            TissuePrior(
                id="joint_fluid",
                label="Joint fluid",
                role="background",
                t1=3.8,
                t2=1.5,
                proton_density=1.0,
            ),
            TissuePrior(
                id="marrow_fat",
                label="Marrow fat",
                role="background",
                t1=.3,
                t2=.06,
                proton_density=.85,
            ),
        ),
        targets=(
            Target(tissue_id="cartilage", rationale="cartilage-surface target"),
            Target(tissue_id="meniscal_tear", rationale="fluid-sensitive tear target"),
        ),
        references=(
            Reference(tissue_id="meniscus", rationale="normal low-T2 fibrocartilage"),
        ),
        confounders=(
            Confounder(tissue_id="joint_fluid", rationale="bright fluid"),
            Confounder(tissue_id="marrow_fat", rationale="fat signal"),
        ),
    ),
    objective=ObjectiveVector(
        terms=(
            ContrastMetric(
                id="tear-vs-meniscus",
                target_tissue_id="meniscal_tear",
                reference_tissue_id="meniscus",
                metric="normalized_cnr_proxy",
                direction="maximize",
                weight=1.0,
            ),
            ContrastMetric(
                id="cartilage-vs-meniscus",
                target_tissue_id="cartilage",
                reference_tissue_id="meniscus",
                metric="absolute_signal_difference",
                direction="maximize",
                weight=.5,
            ),
        )
    ),
    robustness=(
        RobustnessScenario(
            id="routine-knee-3t",
            delta_b0_hz=(-75, 75),
            b1_scale=(.8, 1.2),
            motion_mm=(0, 2),
            t1_scale=(.9, 1.1),
            t2_scale=(.85, 1.15),
        ),
    ),
    constraints=(
        AcquisitionConstraint(
            id="scan-time",
            metric="scan_time_s",
            operator="le",
            value=240,
            unit="s",
            severity="hard",
        ),
        AcquisitionConstraint(
            id="resolution",
            metric="resolution_mm",
            operator="le",
            value=.6,
            unit="mm",
            severity="soft",
        ),
    ),
    scanner_profile=RESEARCH_3T,
    experiment_recipe_id="msk_knee_tse",
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
