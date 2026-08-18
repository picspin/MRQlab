from dataclasses import dataclass
from typing import Any, Literal, Protocol
import math
import numpy as np
from pydantic import BaseModel, Field

from mrqlab_physics.ops.rf import rotate_cartesian, epg_rf_matrix


PulseKind = Literal["hard", "shaped_sinc", "gaussian", "rect", "custom"]
PropagationMethod = Literal["hard", "small_tip", "spatial_bloch", "epg_transition"]


class PulseDefinition(BaseModel):
    kind: PulseKind = "hard"
    flip_angle_deg: float = Field(default=90.0)
    phase_deg: float = Field(default=0.0)
    duration_s: float = Field(default=0.001, gt=0)
    time_bandwidth: float = Field(default=4.0, gt=0)
    slice_thickness_m: float = Field(default=0.005, gt=0)
    samples: tuple[complex, ...] = ()


@dataclass(frozen=True, slots=True)
class PulseResponse:
    flip_angle_deg: float
    phase_deg: float
    duration_s: float
    slice_thickness_m: float
    frequency_response: np.ndarray | None = None
    slice_profile: np.ndarray | None = None
    b0_sensitivity: float = 1.0
    b1_sensitivity: float = 1.0


class PulsePropagator(Protocol):
    def propagate(self, m_initial: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True, slots=True)
class HardPulsePropagator:
    alpha_rad: float
    phi_rad: float

    def propagate(self, m_initial: np.ndarray) -> np.ndarray:
        m = np.asarray(m_initial, dtype=np.float64)
        if m.ndim == 1:
            m = m[None, :]
            res = rotate_cartesian(m, self.alpha_rad, self.phi_rad)
            return res[0]
        return rotate_cartesian(m, self.alpha_rad, self.phi_rad)


@dataclass(frozen=True, slots=True)
class SmallTipPropagator:
    pulse: PulseDefinition

    def frequency_response(self, freqs_hz: np.ndarray) -> np.ndarray:
        freqs = np.asarray(freqs_hz, dtype=np.float64)
        t_dur = self.pulse.duration_s
        alpha_rad = math.radians(self.pulse.flip_angle_deg)
        bw = self.pulse.time_bandwidth / t_dur
        response = np.sinc(freqs / bw) * math.sin(alpha_rad)
        return response.astype(np.complex128)

    def propagate(self, m_initial: np.ndarray) -> np.ndarray:
        alpha_rad = math.radians(self.pulse.flip_angle_deg)
        phi_rad = math.radians(self.pulse.phase_deg)
        return HardPulsePropagator(alpha_rad, phi_rad).propagate(m_initial)


@dataclass(frozen=True, slots=True)
class SpatialBlochPropagator:
    pulse: PulseDefinition

    def slice_profile(
        self,
        z_positions_m: np.ndarray,
        t1: float = 1.0,
        t2: float = 0.1,
        gradient_g_m: float = 0.02,
    ) -> np.ndarray:
        z = np.asarray(z_positions_m, dtype=np.float64)
        gamma = 42.577e6  # Hz/T
        # Calculate actual excitation bandwidth from slice thickness and gradient
        # delta_f = gamma * G * z
        delta_f = gamma * gradient_g_m * z
        bw = gamma * gradient_g_m * self.pulse.slice_thickness_m
        alpha_rad = math.radians(self.pulse.flip_angle_deg)
        
        excitation = np.sinc(delta_f / max(1e-6, bw)) * math.sin(alpha_rad)
        excitation = np.clip(excitation, -1.0, 1.0)
        
        m_out = np.zeros((len(z), 3), dtype=np.float64)
        phi = math.radians(self.pulse.phase_deg)
        for i, exc in enumerate(excitation):
            theta = math.asin(np.clip(exc, -1.0, 1.0))
            rot = HardPulsePropagator(theta, phi)
            m_out[i] = rot.propagate(np.array([0.0, 0.0, 1.0]))
        return m_out

    def propagate(self, m_initial: np.ndarray) -> np.ndarray:
        alpha_rad = math.radians(self.pulse.flip_angle_deg)
        phi_rad = math.radians(self.pulse.phase_deg)
        return HardPulsePropagator(alpha_rad, phi_rad).propagate(m_initial)


@dataclass(frozen=True, slots=True)
class EpgTransitionPropagator:
    alpha_rad: float
    phi_rad: float

    def transition_matrix(self) -> np.ndarray:
        return epg_rf_matrix(self.alpha_rad, self.phi_rad)

    def propagate(self, m_initial: np.ndarray) -> np.ndarray:
        # Standard EPG state transformation on (F+, F-, Z)
        state = np.asarray(m_initial, dtype=np.complex128)
        mat = self.transition_matrix()
        if state.ndim == 1 and len(state) == 3:
            return mat @ state
        return state


class PulseCompiler:
    @staticmethod
    def analyze(pulse: PulseDefinition) -> PulseResponse:
        alpha_rad = math.radians(pulse.flip_angle_deg)
        t_dur = pulse.duration_s
        bw = pulse.time_bandwidth / t_dur
        freqs = np.linspace(-bw * 1.5, bw * 1.5, 51)
        freq_resp = np.sinc(freqs / bw) * math.sin(alpha_rad)
        
        z = np.linspace(-pulse.slice_thickness_m * 2, pulse.slice_thickness_m * 2, 51)
        spatial_prop = SpatialBlochPropagator(pulse=pulse)
        slice_prof = spatial_prop.slice_profile(z, gradient_g_m=0.02)

        return PulseResponse(
            flip_angle_deg=pulse.flip_angle_deg,
            phase_deg=pulse.phase_deg,
            duration_s=pulse.duration_s,
            slice_thickness_m=pulse.slice_thickness_m,
            frequency_response=freq_resp,
            slice_profile=slice_prof,
            b0_sensitivity=1.0,
            b1_sensitivity=1.0,
        )

    @staticmethod
    def compile(
        pulse: PulseDefinition,
        method: PropagationMethod = "hard",
    ) -> PulsePropagator:
        if method == "hard" or pulse.kind == "hard":
            alpha_rad = math.radians(pulse.flip_angle_deg)
            phi_rad = math.radians(pulse.phase_deg)
            return HardPulsePropagator(alpha_rad=alpha_rad, phi_rad=phi_rad)
        elif method == "small_tip":
            return SmallTipPropagator(pulse=pulse)
        elif method == "spatial_bloch":
            return SpatialBlochPropagator(pulse=pulse)
        elif method == "epg_transition":
            alpha_rad = math.radians(pulse.flip_angle_deg)
            phi_rad = math.radians(pulse.phase_deg)
            return EpgTransitionPropagator(alpha_rad=alpha_rad, phi_rad=phi_rad)
        else:
            raise ValueError(f"Unsupported pulse propagation method: {method}")


def compile_pulse(
    pulse: PulseDefinition,
    method: PropagationMethod = "hard",
) -> PulsePropagator:
    return PulseCompiler.compile(pulse, method=method)
