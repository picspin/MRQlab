from typing import Protocol

import numpy as np

from ..ops.types import Operator


class StateBackend(Protocol):
    def apply(self, op: Operator) -> None: ...

    def observe(self) -> complex: ...

    def snapshot(self) -> np.ndarray: ...
