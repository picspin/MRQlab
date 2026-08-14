from abc import ABC, abstractmethod
from mrqlab_sequence import SequenceIR
from .models import EngineOptions, Phantom, ScannerModel, SimResult

class SimulationEngine(ABC):
    name: str
    description: str
    available: bool = True
    @abstractmethod
    def simulate(self, sequence: SequenceIR, phantom: Phantom, scanner: ScannerModel,
                 options: EngineOptions) -> SimResult: ...
