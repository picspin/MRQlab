import numpy as np

from ..models import Phantom
from ..ops.relax import relaxation_factors
from ..ops.rf import epg_rf_matrix
from ..ops.diffuse import diffusion_attenuation
from ..ops.types import GradInterval, Operator, Relax, RfOp, Shift


def _translate(values: np.ndarray, delta: int) -> np.ndarray:
    output = np.zeros_like(values)
    if abs(delta) >= values.size:
        return output
    if delta > 0:
        output[delta:] = values[:-delta]
    elif delta < 0:
        output[:delta] = values[-delta:]
    else:
        output[:] = values
    return output


class EPGBackend:
    def __init__(self, phantom: Phantom, kmax: int, *, gradient_units="teaching", fov_m=0.22):
        self.phantom = phantom
        self.kmax = kmax
        self.zero = kmax
        self.gradient_units = gradient_units
        self.fov_m = fov_m
        self.diffusion_applied = False
        if phantom.diffusion_adc_mm2_s and gradient_units != "mt_m":
            raise ValueError("diffusion requires sequence gradient_units='mt_m'")
        self.omega = np.zeros((3, 2 * kmax + 1), dtype=np.complex128)
        self.omega[2, self.zero] = phantom.proton_density

    def apply(self, op: Operator) -> None:
        if isinstance(op, RfOp):
            self.omega = epg_rf_matrix(op.alpha_rad, op.phase_rad) @ self.omega
        elif isinstance(op, Relax):
            e1, e2 = relaxation_factors(op.dt, self.phantom.t1, self.phantom.t2)
            phase = np.exp(2j * np.pi * self.phantom.off_resonance_hz * op.dt)
            self.omega[0] *= e2 * phase
            self.omega[1] *= e2 * np.conj(phase)
            self.omega[2] *= e1
            self.omega[2, self.zero] += self.phantom.proton_density * (1.0 - e1)
            if self.phantom.diffusion_adc_mm2_s:
                diffusion_m2_s = self.phantom.diffusion_adc_mm2_s * 1e-6
                factors = np.asarray([
                    diffusion_attenuation(abs(index - self.zero), 1.0 / self.fov_m, diffusion_m2_s, op.dt)
                    for index in range(self.omega.shape[1])
                ])
                self.omega[0] *= factors
                self.omega[1] *= factors
                self.diffusion_applied = True
        elif isinstance(op, Shift):
            dk = op.dk[0]
            self.omega[0] = _translate(self.omega[0], dk)
            self.omega[1] = _translate(self.omega[1], -dk)
        elif isinstance(op, GradInterval):
            return

    def observe(self) -> complex:
        return complex(self.omega[0, self.zero])

    def snapshot(self) -> np.ndarray:
        return self.omega.copy()
