import numpy as np

from ..models import Isochromat, ScannerModel
from ..ops.relax import relaxation_factors
from ..ops.rf import rotate_cartesian
from ..ops.types import GradInterval, Operator, Relax, RfOp, Shift
from ..kernel.units import gradient_hz_per_m


class BlochBackend:
    def __init__(self, spins: tuple[Isochromat, ...], scanner: ScannerModel, gradient_units="teaching"):
        self.spins = spins
        self.scanner = scanner
        self.gradient_units = gradient_units
        self.state = np.zeros((len(spins), 3), dtype=float)
        self.state[:, 2] = [spin.proton_density for spin in spins]
        self.weights = np.asarray([spin.weight for spin in spins], dtype=float)
        self.positions = np.asarray([spin.position_m for spin in spins], dtype=float)

    def apply(self, op: Operator) -> None:
        if isinstance(op, RfOp):
            self.state = rotate_cartesian(self.state, op.alpha_rad, op.phase_rad)
        elif isinstance(op, Relax):
            for index, spin in enumerate(self.spins):
                e1, e2 = relaxation_factors(op.dt, spin.t1, spin.t2)
                transverse = self.state[index, 0] + 1j * self.state[index, 1]
                transverse *= e2 * np.exp(2j * np.pi * spin.off_resonance_hz * op.dt)
                self.state[index, 0:2] = (transverse.real, transverse.imag)
                self.state[index, 2] = spin.proton_density - (
                    spin.proton_density - self.state[index, 2]
                ) * e1
        elif isinstance(op, GradInterval):
            gradient = gradient_hz_per_m(op.gradient, self.scanner, self.gradient_units)
            phase = 2.0 * np.pi * (self.positions @ gradient) * op.dt
            transverse = (self.state[:, 0] + 1j * self.state[:, 1]) * np.exp(1j * phase)
            self.state[:, 0] = transverse.real
            self.state[:, 1] = transverse.imag
        elif isinstance(op, Shift):
            return

    def observe(self) -> complex:
        transverse = self.state[:, 0] + 1j * self.state[:, 1]
        total_weight = self.weights.sum()
        return 0j if total_weight == 0 else complex(np.sum(self.weights * transverse) / total_weight)

    def snapshot(self) -> np.ndarray:
        return self.state.copy()
