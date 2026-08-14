from typing import Protocol

from mrqlab_sequence import SequenceIR

from ..base import SimulationEngine
from ..models import EngineOptions, Phantom, ScannerModel, SimResult


class PDGProvider(Protocol):
    def simulate(
        self,
        sequence: SequenceIR,
        phantom: Phantom,
        scanner: ScannerModel,
        options: EngineOptions,
    ) -> SimResult: ...


class PDGProviderUnavailable(RuntimeError):
    pass


class PDGAdapter(SimulationEngine):
    name = "pdg"
    description = "External phase-distribution-graph provider adapter"

    def __init__(self, provider: PDGProvider | None = None):
        self.provider = provider
        self.available = provider is not None

    def simulate(self, sequence, phantom, scanner, options) -> SimResult:
        if self.provider is None:
            raise PDGProviderUnavailable(
                "PDG is optional; install and pass a PDGProvider implementation"
            )
        result = self.provider.simulate(sequence, phantom, scanner, options)
        result.meta = {**result.meta, "engine": self.name}
        return result
