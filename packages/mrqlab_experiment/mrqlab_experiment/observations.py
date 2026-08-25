import hashlib
import json
from typing import Any, Literal, get_args

import numpy as np
from pydantic import BaseModel, Field

from mrqlab_recon import fft_reconstruct

from .objectives import evaluate_multi_tissue_contrast, evaluate_objective

ObservationKind = Literal[
    "signal",
    "k_trajectory",
    "image",
    "magnetization",
    "configurations",
    "echo_train",
    "sar",
    "tissue_contrast",
    "objective_score",
    "slice_profile",
    "phase_distribution",
    "z_spectrum",
    "mtr_asym",
]

_ALLOWED_PRODUCTS = frozenset(get_args(ObservationKind))


class ObservationProvenance(BaseModel):
    experiment_hash: str
    engine: str
    representation: str
    assumptions: tuple[str, ...]
    seed: int
    n_ops: int
    estimated_work: int


class Observation(BaseModel):
    id: str
    kind: ObservationKind
    schema_version: Literal["1.0"] = "1.0"
    data: Any
    axes: dict[str, list[float]] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    derived_from: tuple[str, ...] = ()
    provenance: ObservationProvenance


class ResultEdge(BaseModel):
    source: str
    target: str
    kind: Literal["derived_from", "engine", "recon"]


class ResultGraph(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    experiment_id: str
    observations: tuple[Observation, ...]
    edges: tuple[ResultEdge, ...]


def _complex(values: np.ndarray) -> list[dict[str, float]]:
    return [{"real": float(v.real), "imag": float(v.imag)} for v in values]


def _derived_from(product: str, emitted: frozenset[str]) -> tuple[str, ...]:
    if product in {"image", "objective_score", "configurations", "echo_train", "tissue_contrast"} and "signal" in emitted:
        return ("signal",)
    return ()


def build_result_graph(run) -> ResultGraph:
    raw = run.experiment.model_dump(mode="json")
    digest = hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    meta = run.sim_result.meta
    plan = getattr(run, "plan", None)
    representation = plan.representation if plan is not None else str(meta["engine"])
    engine_name = str(plan.engine if plan is not None else meta["engine"])
    provenance = ObservationProvenance(
        experiment_hash=digest,
        engine=engine_name,
        representation=representation,
        assumptions=tuple(meta.get("assumptions", ())),
        seed=run.experiment.provenance.seed,
        n_ops=int(meta.get("n_ops", 0)),
        estimated_work=int(meta.get("estimated_work", 0)),
    )
    products = run.experiment.readout.products
    if run.sim_result.slice_profile is not None and "slice_profile" not in products:
        products = (*products, "slice_profile")
    if run.sim_result.phase_distribution is not None and "phase_distribution" not in products:
        products = (*products, "phase_distribution")
    if "mtr_asym" in products and "z_spectrum" not in products:
        products = ("z_spectrum", *products)
    if run.sim_result.z_spectrum is not None and "z_spectrum" not in products:
        products = (*products, "z_spectrum")
    for product in products:
        if product not in _ALLOWED_PRODUCTS:
            raise ValueError(f"unknown_product: {product!r}")
        if product == "magnetization" and run.sim_result.magnetization is None:
            raise ValueError(
                f"snapshot product {product!r} is unavailable while snapshot collection is disabled"
            )
        if product == "configurations" and run.sim_result.configurations is None:
            raise ValueError(
                f"snapshot product {product!r} is unavailable while snapshot collection is disabled"
            )
        if product == "objective_score" and run.experiment.objective is None:
            raise ValueError("objective_score requested without an objective")
        if product in {"z_spectrum", "mtr_asym"} and run.sim_result.z_spectrum is None:
            raise ValueError(f"{product} requested but no CEST z_spectrum sweep ran")
        if product == "objective_score" and run.experiment.objective is not None:
            unsupported = sorted(
                {
                    term.observation
                    for term in run.experiment.objective.terms
                    if term.observation != "signal"
                }
            )
            if unsupported:
                raise ValueError(
                    f"objective observation {unsupported[0]!r} is reserved for a later wave"
                )

    builders = {
        "signal": lambda emitted: Observation(
            id="signal",
            kind="signal",
            data=_complex(run.sim_result.signal),
            units={"value": "a.u."},
            provenance=provenance,
        ),
        "k_trajectory": lambda emitted: Observation(
            id="k_trajectory",
            kind="k_trajectory",
            data=run.sim_result.k_trajectory.tolist(),
            units={"k": "teaching-gradient·s"},
            provenance=provenance,
        ),
        "image": lambda emitted: Observation(
            id="image",
            kind="image",
            data=(
                np.abs(fft_reconstruct(run.sim_result.signal)).tolist()
                if run.sim_result.signal.size
                else []
            ),
            units={"value": "a.u."},
            derived_from=_derived_from("image", emitted),
            provenance=provenance,
        ),
        "objective_score": lambda emitted: Observation(
            id="objective_score",
            kind="objective_score",
            data=evaluate_objective(
                run.experiment.objective,
                {"signal": run.sim_result.signal},
            ),
            units={"value": "score"},
            derived_from=_derived_from("objective_score", emitted),
            provenance=provenance,
        ),
        "magnetization": lambda emitted: Observation(
            id="magnetization",
            kind="magnetization",
            data=np.asarray(run.sim_result.magnetization).tolist(),
            derived_from=_derived_from("magnetization", emitted),
            provenance=provenance,
        ),
        "configurations": lambda emitted: Observation(
            id="configurations",
            kind="configurations",
            data=np.abs(run.sim_result.configurations).tolist(),
            derived_from=_derived_from("configurations", emitted),
            provenance=provenance,
        ),
        "echo_train": lambda emitted: Observation(
            id="echo_train",
            kind="echo_train",
            data=np.abs(run.sim_result.signal).tolist(),
            axes={"echo": list(range(1, int(run.sim_result.signal.size) + 1))},
            derived_from=_derived_from("echo_train", emitted),
            provenance=provenance,
        ),
        "tissue_contrast": lambda emitted: Observation(
            id="tissue_contrast",
            kind="tissue_contrast",
            data=evaluate_multi_tissue_contrast(run.experiment),
            units={"value": "contrast_metrics"},
            derived_from=_derived_from("tissue_contrast", emitted),
            provenance=provenance,
        ),
        "sar": lambda emitted: Observation(
            id="sar",
            kind="sar",
            data=(
                int(run.sequence.metadata.get("echoes", 1))
                * (float(run.sequence.metadata.get("refocusing_flip_angle", 180.0)) / 180.0) ** 2
            ),
            units={"value": "relative"},
            provenance=provenance,
        ),
        "slice_profile": lambda emitted: Observation(
            id="slice_profile",
            kind="slice_profile",
            data={
                key: np.asarray(value).tolist()
                for key, value in (run.sim_result.slice_profile or {}).items()
            },
            axes={"z_m": np.asarray((run.sim_result.slice_profile or {}).get("z_m", [])).tolist()},
            units={"z_m": "m", "magnetization": "a.u."},
            provenance=provenance,
        ),
        "phase_distribution": lambda emitted: Observation(
            id="phase_distribution",
            kind="phase_distribution",
            data={
                key: (np.abs(value) if np.iscomplexobj(value) else np.asarray(value)).tolist()
                for key, value in (run.sim_result.phase_distribution or {}).items()
            },
            axes={"x_m": np.asarray((run.sim_result.phase_distribution or {}).get("x_m", [])).tolist()},
            units={"x_m": "m", "off_hz": "Hz", "configurations": "a.u.", "image": "a.u."},
            provenance=provenance,
        ),
        "z_spectrum": lambda emitted: Observation(
            id="z_spectrum", kind="z_spectrum",
            data={
                "offset_ppm": np.asarray(run.sim_result.z_spectrum["offset_ppm"]).tolist(),
                "offset_hz": np.asarray(run.sim_result.z_spectrum["offset_hz"]).tolist(),
                "Z": np.asarray(run.sim_result.z_spectrum["Z"]).tolist(),
                "Mz_sat": np.asarray(run.sim_result.z_spectrum["Mz_sat"]).tolist(),
                "Mz_ref": float(np.asarray(run.sim_result.z_spectrum["Mz_ref"]).reshape(-1)[0]),
                "normalization": "unsaturated_control", "reference": "water",
            },
            axes={"offset_ppm": np.asarray(run.sim_result.z_spectrum["offset_ppm"]).tolist()},
            units={"offset": "ppm", "offset_hz": "Hz", "Z": "normalized"},
            provenance=provenance,
        ),
        "mtr_asym": lambda emitted: _build_mtr_asym(run.sim_result.z_spectrum, provenance),
    }
    observations: list[Observation] = []
    edges: list[ResultEdge] = []
    emitted: set[str] = set()
    for product in products:
        observation = builders[product](frozenset(emitted))
        observations.append(observation)
        emitted.add(observation.id)
        if product in {"signal", "magnetization", "configurations", "k_trajectory", "slice_profile", "phase_distribution", "z_spectrum"}:
            edges.append(ResultEdge(source=engine_name, target=observation.id, kind="engine"))
        for source in observation.derived_from:
            edge_kind = "recon" if product == "image" and source == "signal" else "derived_from"
            edges.append(ResultEdge(source=source, target=observation.id, kind=edge_kind))
    return ResultGraph(
        experiment_id=run.experiment.id,
        observations=tuple(observations),
        edges=tuple(edges),
    )


def _build_mtr_asym(spectrum, provenance):
    offsets = np.asarray(spectrum["offset_ppm"], dtype=float)
    z = np.asarray(spectrum["Z"], dtype=float)
    positive, values = [], []
    for index, offset in enumerate(offsets):
        if offset <= 0:
            continue
        match = np.flatnonzero(np.isclose(offsets, -offset, rtol=0, atol=1e-9))
        if match.size:
            positive.append(float(offset))
            values.append(float(z[match[0]] - z[index]))
    return Observation(
        id="mtr_asym", kind="mtr_asym", data={"offset_ppm": positive, "MTR_asym": values},
        axes={"offset_ppm": positive}, units={"offset": "ppm", "MTR_asym": "normalized"},
        derived_from=("z_spectrum",), provenance=provenance,
    )
