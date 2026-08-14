from ..base import SimulationEngine


class EPGEngine(SimulationEngine):
    name = "epg"
    description = "Classic extended phase graph"
    available = False

    def simulate(self, sequence, phantom, scanner, options):
        raise NotImplementedError("epg engine requires the classic EPG backend; future work")
