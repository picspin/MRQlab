import hashlib
import json
from typing import Any, Literal, get_args

import numpy as np
from pydantic import BaseModel, Field

from mrqlab_recon import fft_reconstruct

from .objectives import evaluate_objective

ObservationKind = Literal[
    "signal",
    "k_trajectory",
    "image",
    "magnetization",
    "configurations",
    "echo_train",
    "sar",
    "objective_score",
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
    if product in {"image", "objective_score", "configurations", "echo_train"} and "signal" in emitted:
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
    }
    observations: list[Observation] = []
    edges: list[ResultEdge] = []
    emitted: set[str] = set()
    for product in products:
        observation = builders[product](frozenset(emitted))
        observations.append(observation)
        emitted.add(observation.id)
        if product in {"signal", "magnetization", "configurations", "k_trajectory"}:
            edges.append(ResultEdge(source=engine_name, target=observation.id, kind="engine"))
        for source in observation.derived_from:
            edge_kind = "recon" if product == "image" and source == "signal" else "derived_from"
            edges.append(ResultEdge(source=source, target=observation.id, kind=edge_kind))
    return ResultGraph(
        experiment_id=run.experiment.id,
        observations=tuple(observations),
        edges=tuple(edges),
    )
