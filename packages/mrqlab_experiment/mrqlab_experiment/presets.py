from dataclasses import dataclass
from typing import Any, Literal
from pydantic import BaseModel, Field

from .models import (
    ExperimentEdge,
    ExperimentGraph,
    ExperimentNode,
    PhysiologyModel,
    ScannerModel,
    TemplateRef,
    TissueModel,
)

_PRESETS = {
    "spin-echo": ("SE", "Spin Echo", "teaching", ("RF", "RF", "READOUT")),
    "gradient-echo": ("GRE", "Gradient Echo", "teaching", ("RF", "GRADIENT", "READOUT")),
    "dark-blood-tse": ("TSE", "Dark Blood TSE", "clinical_contrast", ("RF", "LOOP", "READOUT")),
}


class ClinicalRecipeSpec(BaseModel):
    id: str
    name: str
    anatomy: str
    target: str
    task: str
    template: Literal["SE", "GRE", "TSE"]
    params: dict[str, float | int] = Field(default_factory=dict)
    tissues: tuple[TissueModel, ...] = ()
    physiology: PhysiologyModel = Field(default_factory=PhysiologyModel)
    scanner_model: ScannerModel = Field(default_factory=ScannerModel)


_CLINICAL_RECIPES: dict[str, ClinicalRecipeSpec] = {
    "dark_blood_vessel_wall_tse": ClinicalRecipeSpec(
        id="dark_blood_vessel_wall_tse",
        name="Dark Blood Vessel Wall TSE",
        anatomy="vascular",
        target="vessel_wall",
        task="wall_lumen_separation",
        template="TSE",
        params={"echo_count": 8, "te": 0.012, "tr": 1.5, "refocusing_flip_angle": 120.0},
        tissues=(
            TissueModel(t1=1.0, t2=0.06, proton_density=0.8),  # Vessel wall (fibrous)
            TissueModel(t1=1.4, t2=0.20, proton_density=1.0),  # Stagnant/slow lumen blood
        ),
        physiology=PhysiologyModel(
            cardiac_phase=0.7,  # Diastolic gating
            rr_interval_s=0.85,
            respiratory_phase=0.0,
        ),
        scanner_model=ScannerModel(
            b0_t=3.0,
            max_gradient_mt_m=80.0,
            max_slew_rate_t_m_s=200.0,
            adc_bandwidth_hz=62500.0,
        ),
    ),
    "cardiac_cine_gre": ClinicalRecipeSpec(
        id="cardiac_cine_gre",
        name="Cardiac Cine Gradient Echo",
        anatomy="cardiac",
        target="myocardium",
        task="ventricular_function",
        template="GRE",
        params={"te": 0.003, "tr": 0.02, "flip_angle": 20.0},
        tissues=(
            TissueModel(t1=1.2, t2=0.05, proton_density=0.85),  # Myocardium
            TissueModel(t1=1.6, t2=0.22, proton_density=1.0),   # Blood pool
        ),
        physiology=PhysiologyModel(
            cardiac_phase=0.2,
            rr_interval_s=0.8,
            respiratory_phase=0.0,
        ),
        scanner_model=ScannerModel(
            b0_t=1.5,
            max_gradient_mt_m=45.0,
            max_slew_rate_t_m_s=150.0,
            adc_bandwidth_hz=100000.0,
        ),
    ),
    "brain_t2_tse": ClinicalRecipeSpec(
        id="brain_t2_tse",
        name="Brain T2-Weighted TSE",
        anatomy="neuro",
        target="white_gray_matter",
        task="lesion_detection",
        template="TSE",
        params={"echo_count": 16, "te": 0.01, "tr": 3.0, "refocusing_flip_angle": 150.0},
        tissues=(
            TissueModel(t1=0.9, t2=0.08, proton_density=0.75),  # White matter
            TissueModel(t1=1.3, t2=0.10, proton_density=0.85),  # Gray matter
            TissueModel(t1=4.0, t2=2.00, proton_density=1.00),  # CSF
            TissueModel(t1=1.4, t2=0.12, proton_density=0.95),  # MS Plaque
        ),
        physiology=PhysiologyModel(),
        scanner_model=ScannerModel(
            b0_t=3.0,
            max_gradient_mt_m=80.0,
            max_slew_rate_t_m_s=200.0,
            adc_bandwidth_hz=62500.0,
        ),
    ),
    "msk_knee_tse": ClinicalRecipeSpec(
        id="msk_knee_tse",
        name="Knee Meniscal & Cartilage TSE",
        anatomy="msk",
        target="meniscus_cartilage",
        task="fissure_detection",
        template="TSE",
        params={"echo_count": 16, "te": 0.045, "tr": 2.5, "refocusing_flip_angle": 140.0},
        tissues=(
            TissueModel(t1=1.2, t2=0.04, proton_density=0.80),  # Hyaline Cartilage
            TissueModel(t1=0.9, t2=0.015, proton_density=0.50),  # Fibrocartilage Meniscus
            TissueModel(t1=1.5, t2=0.09, proton_density=0.95),  # Meniscal Tear / Joint Fluid
            TissueModel(t1=0.3, t2=0.06, proton_density=0.85),  # Bone Marrow Fat
        ),
        physiology=PhysiologyModel(),
        scanner_model=ScannerModel(
            b0_t=3.0,
            max_gradient_mt_m=80.0,
            max_slew_rate_t_m_s=200.0,
            adc_bandwidth_hz=62500.0,
        ),
    ),
    "abdomen_dixon_gre": ClinicalRecipeSpec(
        id="abdomen_dixon_gre",
        name="Abdominal Dixon Fat-Water GRE",
        anatomy="body",
        target="hepatic_steatosis",
        task="fat_fraction_quantification",
        template="GRE",
        params={"te": 0.0023, "tr": 0.15, "flip_angle": 12.0},
        tissues=(
            TissueModel(t1=0.8, t2=0.045, proton_density=0.70),  # Liver Parenchyma
            TissueModel(t1=0.45, t2=0.065, proton_density=0.85), # Focal Fatty Steatosis
            TissueModel(t1=1.1, t2=0.080, proton_density=0.85),  # Spleen
            TissueModel(t1=0.26, t2=0.070, proton_density=0.90), # Retroperitoneal Fat
        ),
        physiology=PhysiologyModel(respiratory_phase=0.0),
        scanner_model=ScannerModel(
            b0_t=3.0,
            max_gradient_mt_m=45.0,
            max_slew_rate_t_m_s=150.0,
            adc_bandwidth_hz=100000.0,
        ),
    ),
    "angio_tof_gre": ClinicalRecipeSpec(
        id="angio_tof_gre",
        name="Intracranial 3D TOF MRA",
        anatomy="vascular",
        target="circle_of_willis_aneurysm",
        task="vascular_inflow_stenosis",
        template="GRE",
        params={"te": 0.0035, "tr": 0.025, "flip_angle": 20.0},
        tissues=(
            TissueModel(t1=1.6, t2=0.18, proton_density=1.00),  # Inflow Arterial Blood
            TissueModel(t1=1.0, t2=0.08, proton_density=0.70),  # Saturated Brain Background
            TissueModel(t1=0.25, t2=0.06, proton_density=0.80), # Skull Base Fat
        ),
        physiology=PhysiologyModel(),
        scanner_model=ScannerModel(
            b0_t=3.0,
            max_gradient_mt_m=80.0,
            max_slew_rate_t_m_s=200.0,
            adc_bandwidth_hz=125000.0,
        ),
    ),
}


def list_clinical_recipes() -> list[str]:
    return list(_CLINICAL_RECIPES.keys())


def build_clinical_recipe(name: str) -> ExperimentGraph:
    try:
        recipe = _CLINICAL_RECIPES[name]
    except KeyError:
        raise ValueError(f"unknown clinical recipe {name!r}") from None

    kinds = ("RF", "LOOP", "READOUT") if recipe.template == "TSE" else ("RF", "GRADIENT", "READOUT")
    nodes = tuple(
        ExperimentNode(id=f"n{index}", kind=kind, label=f"{kind} {index}")
        for index, kind in enumerate(kinds)
    )
    edges = tuple(
        ExperimentEdge(source=nodes[index].id, target=nodes[index + 1].id)
        for index in range(len(nodes) - 1)
    )

    return ExperimentGraph(
        id=f"recipe:{recipe.id}",
        name=recipe.name,
        intent="clinical_contrast",
        nodes=nodes,
        edges=edges,
        sequence=TemplateRef(template=recipe.template, params=recipe.params),
        tissue=recipe.tissues,
        physiology=recipe.physiology,
        scanner_model=recipe.scanner_model,
    )


def build_preset(name: str, params: dict[str, float | int] | None = None) -> ExperimentGraph:
    try:
        template, title, intent, kinds = _PRESETS[name]
    except KeyError:
        raise ValueError(f"unknown experiment preset {name!r}") from None
    nodes = tuple(
        ExperimentNode(id=f"n{index}", kind=kind, label=f"{kind} {index}")
        for index, kind in enumerate(kinds)
    )
    edges = tuple(
        ExperimentEdge(source=nodes[index].id, target=nodes[index + 1].id)
        for index in range(len(nodes) - 1)
    )
    return ExperimentGraph(
        id=f"preset:{name}",
        name=title,
        intent=intent,
        nodes=nodes,
        edges=edges,
        sequence=TemplateRef(template=template, params=params or {}),
    )
