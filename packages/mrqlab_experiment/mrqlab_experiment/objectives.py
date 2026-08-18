from typing import Any, Literal
import numpy as np
from pydantic import BaseModel, Field

from mrqlab_physics import EngineOptions, Isochromat, Phantom, ScannerModel, get_engine
from mrqlab_sequence import SequenceIR


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
    kind: Literal["null", "contrast_target", "clinical_cnr"] = "null"
    terms: tuple[ObjectiveTerm, ...] = ()
    cnr_term: ClinicalCNRTerm | None = None
    constraints: tuple[ObjectiveConstraint, ...] = ()


def evaluate_multi_tissue_contrast(graph) -> dict[str, Any]:
    from .compiler import compile_sequence
    from .kernel import plan_experiment

    plan = plan_experiment(graph)
    sequence = compile_sequence(graph)
    options = EngineOptions(**plan.options)
    engine = get_engine(plan.engine)
    scanner = graph.effective_scanner

    signals = []
    tissue_info = []
    if graph.tissue is not None:
        tissues = graph.tissue if isinstance(graph.tissue, tuple) else (graph.tissue,)
        for t in tissues:
            tissue_info.append({"id": t.id, "label": t.label, "role": t.role})
            phantom = Phantom(
                t1=t.t1,
                t2=t.t2,
                proton_density=t.proton_density,
                off_resonance_hz=graph.sample.off_resonance_hz,
            )
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

    # Compute contrast between first two tissues
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

    return {
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
