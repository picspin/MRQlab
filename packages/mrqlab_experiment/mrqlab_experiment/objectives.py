from typing import Any, Literal
import numpy as np
from pydantic import BaseModel, Field

from mrqlab_physics import EngineOptions, Isochromat, Phantom, ScannerModel, get_engine
from mrqlab_sequence import SequenceIR
from .clinical import ObjectiveVector


class ObjectiveTerm(BaseModel):
    observation: Literal["signal", "echo_train"]
    metric: Literal["peak_magnitude", "mean_magnitude"]
    target: float
    weight: float = Field(default=1.0, gt=0)


class ClinicalCNRTerm(BaseModel):
    tissue_a_index: int = 0
    tissue_b_index: int = 1
    target_tissue_id: str | None = None
    reference_tissue_id: str | None = None
    metric: Literal["contrast_difference", "signal_ratio", "normalized_cnr_proxy", "difference", "ratio", "cnr"] = "contrast_difference"
    target: float = 0.0
    weight: float = Field(default=1.0, gt=0)


class ObjectiveConstraint(BaseModel):
    metric: Literal["scan_time_s", "sar_relative"]
    upper_bound: float = Field(gt=0)
    penalty: float = Field(default=1.0, gt=0)


class ObjectiveFunction(BaseModel):
    kind: Literal["null", "contrast_target", "clinical_cnr", "clinical_vector"] = "null"
    terms: tuple[ObjectiveTerm, ...] = ()
    clinical_vector: ObjectiveVector | None = None
    cnr_term: ClinicalCNRTerm | None = None
    constraints: tuple[ObjectiveConstraint, ...] = ()


def evaluate_multi_tissue_contrast(graph) -> dict[str, Any]:
    from .contrast_relaxation import effective_tissue
    from .compiler import compile_sequence
    from .kernel import plan_experiment

    plan = plan_experiment(graph)
    sequence = compile_sequence(graph)
    options = EngineOptions(**dict(plan.options))
    engine = get_engine(plan.engine)
    scanner = graph.effective_scanner

    signals = []
    tissue_info = []
    if graph.tissue is not None:
        tissues = graph.tissue if isinstance(graph.tissue, tuple) else (graph.tissue,)
        for t in tissues:
            t=effective_tissue(t,scanner.b0_t)
            tissue_info.append({"id": t.id, "label": t.label, "role": t.role})
            phantom = Phantom(
                t1=t.t1,
                t2=t.t2,
                proton_density=t.proton_density,
                off_resonance_hz=graph.sample.off_resonance_hz,
            )
            if sequence.metadata.get("research_family"):
                from .family_execution import simulate_family
                from dataclasses import replace
                compartment = sequence.model_copy(deep=True)
                compartment.metadata["blood_compartment"] = t.id == "blood"
                phantom = replace(phantom, diffusion_adc_mm2_s=t.diffusion_adc_mm2_s)
                sim_res = simulate_family(compartment, phantom, scanner, options)
            else:
                sim_res = engine.simulate(sequence, phantom, scanner, options)
            signals.append(sim_res.signal)
    else:
        # Fallback to single sample
        tissue_info.append({"id": "sample", "label": "Sample", "role": "target"})
        phantom = Phantom(
            t1=graph.sample.t1,
            t2=graph.sample.t2,
            proton_density=graph.sample.proton_density,
            off_resonance_hz=graph.sample.off_resonance_hz,
        )
        sim_res = engine.simulate(sequence, phantom, scanner, options)
        signals.append(sim_res.signal)

    pairs = []
    ids = [t["id"] for t in tissue_info]
    if graph.clinical_recipe is not None:
        for term in graph.clinical_recipe.objective.terms:
            # Defense in depth: recipe validation checks declared priors, while runtime tissues may differ.
            missing = [tissue_id for tissue_id in (term.target_tissue_id, term.reference_tissue_id) if tissue_id not in ids]
            if missing:
                raise ValueError(f"clinical recipe objective references unavailable tissue id(s): {', '.join(dict.fromkeys(missing))}")
            a = float(np.mean(np.abs(signals[ids.index(term.target_tissue_id)])))
            b = float(np.mean(np.abs(signals[ids.index(term.reference_tissue_id)])))
            difference = abs(a - b)
            metrics = {"absolute_signal_difference": difference, "signal_ratio": a / max(1e-6, b), "normalized_cnr_proxy": difference / 0.05}
            pairs.append({"id": term.id, "target_tissue_id": term.target_tissue_id,
                          "reference_tissue_id": term.reference_tissue_id, **metrics,
                          "metric": term.metric, "value": metrics[term.metric]})

    # Legacy scalar keys follow the first declared named pair when available.
    if len(signals) >= 2:
        sig_a = np.mean(np.abs(signals[0]))
        sig_b = np.mean(np.abs(signals[1]))
        diff = float(np.abs(sig_a - sig_b))
        noise_floor = 0.05
        cnr = diff / noise_floor
        ratio = float(sig_a / max(1e-6, sig_b))
    elif len(signals) == 1:
        diff = float(np.mean(np.abs(signals[0])))
        cnr = diff / 0.05
        ratio = 1.0
    else:
        diff = 0.0
        cnr = 0.0
        ratio = 0.0

    if pairs:
        diff = pairs[0]["absolute_signal_difference"]
        ratio = pairs[0]["signal_ratio"]
        cnr = pairs[0]["normalized_cnr_proxy"]
    return {
        "pairs": pairs,
        "tissues": tissue_info,
        "tissue_signals": [s.tolist() for s in signals],
        "contrast_difference": diff,
        "signal_ratio": ratio,
        "normalized_cnr_proxy": cnr,
        # backward compat keys
        "difference": diff,
        "ratio": ratio,
        "cnr": cnr,
    }


def evaluate_objective(objective: ObjectiveFunction, products: dict[str, object]) -> float:
    if objective.kind == "clinical_vector":
        if objective.clinical_vector is None:
            raise ValueError("clinical_vector requires named terms")
        data = products["multi_tissue_contrast"]
        means = {t["id"]: float(np.mean(np.abs(s))) for t, s in zip(data["tissues"], data["tissue_signals"])}
        total = 0.0
        for term in objective.clinical_vector.terms:
            # Defense in depth: validate against the tissue rows actually evaluated for this run.
            missing = [tissue_id for tissue_id in (term.target_tissue_id, term.reference_tissue_id) if tissue_id not in means]
            if missing:
                raise ValueError(f"clinical objective references unavailable tissue id(s): {', '.join(dict.fromkeys(missing))}")
            a, b = means[term.target_tissue_id], means[term.reference_tissue_id]
            measured = {"absolute_signal_difference": abs(a-b), "signal_ratio": a/max(1e-6,b), "normalized_cnr_proxy": abs(a-b)/0.05}[term.metric]
            if term.direction == "target":
                if term.target_value is None:
                    raise ValueError("target direction requires target_value")
                loss = (measured-term.target_value)**2
            else:
                loss = -measured if term.direction == "maximize" else measured
            total += term.weight * loss
        return float(total)
    if objective.kind == "null":
        return 0.0
    elif objective.kind == "contrast_target":
        total = 0.0
        for term in objective.terms:
            values = np.asarray(products[term.observation], dtype=np.complex128)
            measured = (
                float(np.max(np.abs(values)))
                if term.metric == "peak_magnitude"
                else float(np.mean(np.abs(values)))
            )
            total += term.weight * (measured - term.target) ** 2
        return total
    elif objective.kind == "clinical_cnr" and objective.cnr_term is not None:
        term = objective.cnr_term
        contrast_data = products.get("multi_tissue_contrast")
        if term.target_tissue_id is not None or term.reference_tissue_id is not None:
            # Defense in depth: a named CN-R term must bind to this run's tissue rows, not fallback indices.
            if not isinstance(contrast_data, dict):
                raise ValueError("named clinical_cnr tissue ids require multi_tissue_contrast tissue metadata")
            tissues = contrast_data.get("tissues", [])
            tissue_ids = [t.get("id") for t in tissues if isinstance(t, dict)]
            missing = [tissue_id for tissue_id in (term.target_tissue_id, term.reference_tissue_id)
                       if tissue_id is not None and tissue_id not in tissue_ids]
            if missing:
                raise ValueError(f"clinical_cnr objective references unavailable tissue id(s): {', '.join(dict.fromkeys(missing))}")
        if contrast_data is not None and isinstance(contrast_data, dict):
            tissues = contrast_data.get("tissues", [])
            signals = [np.asarray(s) for s in contrast_data.get("tissue_signals", [])]
            idx_a = term.tissue_a_index
            idx_b = term.tissue_b_index
            if term.target_tissue_id is not None:
                for idx, t in enumerate(tissues):
                    if t.get("id") == term.target_tissue_id:
                        idx_a = idx
                        break
            if term.reference_tissue_id is not None:
                for idx, t in enumerate(tissues):
                    if t.get("id") == term.reference_tissue_id:
                        idx_b = idx
                        break
            if len(signals) > max(idx_a, idx_b):
                s_a = np.mean(np.abs(signals[idx_a]))
                s_b = np.mean(np.abs(signals[idx_b]))
                if term.metric in {"contrast_difference", "difference"}:
                    measured = float(np.abs(s_a - s_b))
                elif term.metric in {"signal_ratio", "ratio"}:
                    measured = float(s_a / max(1e-6, s_b))
                else:
                    measured = float(np.abs(s_a - s_b)) / 0.05
                return float(term.weight * (measured - term.target) ** 2)

        signals = products.get("tissue_signals", [])
        if len(signals) > max(term.tissue_a_index, term.tissue_b_index):
            s_a = np.mean(np.abs(signals[term.tissue_a_index]))
            s_b = np.mean(np.abs(signals[term.tissue_b_index]))
            if term.metric in {"contrast_difference", "difference"}:
                measured = float(np.abs(s_a - s_b))
            elif term.metric in {"signal_ratio", "ratio"}:
                measured = float(s_a / max(1e-6, s_b))
            else:
                measured = float(np.abs(s_a - s_b)) / 0.05
            return float(term.weight * (measured - term.target) ** 2)
        return 0.0
    return 0.0
