from typing import Literal

import numpy as np
from pydantic import BaseModel, Field


class ObjectiveTerm(BaseModel):
    observation: Literal["signal", "echo_train"]
    metric: Literal["peak_magnitude", "mean_magnitude"]
    target: float
    weight: float = Field(default=1.0, gt=0)


class ObjectiveConstraint(BaseModel):
    metric: Literal["scan_time_s", "sar_relative"]
    upper_bound: float = Field(gt=0)
    penalty: float = Field(default=1.0, gt=0)


class ObjectiveFunction(BaseModel):
    kind: Literal["null", "contrast_target"] = "null"
    terms: tuple[ObjectiveTerm, ...] = ()
    constraints: tuple[ObjectiveConstraint, ...] = ()


def evaluate_objective(objective: ObjectiveFunction, products: dict[str, object]) -> float:
    if objective.kind == "null":
        return 0.0
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
