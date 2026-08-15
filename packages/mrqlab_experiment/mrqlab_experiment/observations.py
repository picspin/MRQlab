import hashlib
import json
from typing import Any, Literal

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


def build_result_graph(run) -> ResultGraph:
    raw = run.experiment.model_dump(mode="json")
    digest = hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    meta = run.sim_result.meta
    provenance = ObservationProvenance(
        experiment_hash=digest,
        engine=str(meta["engine"]),
        representation=str(meta["engine"]),
        assumptions=tuple(meta.get("assumptions", ())),
        seed=run.experiment.provenance.seed,
        n_ops=int(meta.get("n_ops", 0)),
        estimated_work=int(meta.get("estimated_work", 0)),
    )
    signal = Observation(
        id="signal",
        kind="signal",
        data=_complex(run.sim_result.signal),
        units={"value": "a.u."},
        provenance=provenance,
    )
    trajectory = Observation(
        id="k_trajectory",
        kind="k_trajectory",
        data=run.sim_result.k_trajectory.tolist(),
        units={"k": "teaching-gradient·s"},
        provenance=provenance,
    )
    image_data = (
        np.abs(fft_reconstruct(run.sim_result.signal)).tolist()
        if run.sim_result.signal.size
        else []
    )
    image = Observation(
        id="image",
        kind="image",
        data=image_data,
        units={"value": "a.u."},
        derived_from=(signal.id,),
        provenance=provenance,
    )
    observations: list[Observation] = [signal, trajectory, image]
    edges: list[ResultEdge] = [ResultEdge(source=signal.id, target=image.id, kind="recon")]
    if run.experiment.objective is not None:
        score = evaluate_objective(
            run.experiment.objective,
            {"signal": run.sim_result.signal},
        )
        score_obs = Observation(
            id="objective_score",
            kind="objective_score",
            data=score,
            units={"value": "score"},
            derived_from=(signal.id,),
            provenance=provenance,
        )
        observations.append(score_obs)
        edges.append(ResultEdge(source=signal.id, target=score_obs.id, kind="derived_from"))
    return ResultGraph(
        experiment_id=run.experiment.id,
        observations=tuple(observations),
        edges=tuple(edges),
    )
