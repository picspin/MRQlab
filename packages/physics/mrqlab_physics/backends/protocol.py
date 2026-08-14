from typing import Protocol

import numpy as np

from ..ops.types import AdcSample, Operator


class StateBackend(Protocol):
    def apply(self, op: Operator) -> None: ...

    def observe(self, op: AdcSample) -> complex: ...

    def snapshot(self) -> np.ndarray: ...
