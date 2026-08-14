from ..base import SimulationEngine


class SpectralEngine(SimulationEngine):
    name = "spectral"
    description = "Independent chemical-shift pools"
    available = False

    def simulate(self, sequence, phantom, scanner, options):
        raise NotImplementedError("spectral engine requires spectral pools; future work")
