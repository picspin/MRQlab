import numpy as np


def epg_rf_matrix(alpha_rad: float, phase_rad: float) -> np.ndarray:
    c2 = np.cos(alpha_rad / 2.0) ** 2
    s2 = np.sin(alpha_rad / 2.0) ** 2
    sa = np.sin(alpha_rad)
    ca = np.cos(alpha_rad)
    p1 = np.exp(1j * phase_rad)
    p2 = np.exp(2j * phase_rad)
    return np.array(
        [
            [c2, p2 * s2, -1j * p1 * sa],
            [np.conj(p2) * s2, c2, 1j * np.conj(p1) * sa],
            [-0.5j * np.conj(p1) * sa, 0.5j * p1 * sa, ca],
        ],
        dtype=np.complex128,
    )


def rotate_cartesian(state: np.ndarray, alpha_rad: float, phase_rad: float) -> np.ndarray:
    axis = np.array([np.cos(phase_rad), np.sin(phase_rad), 0.0])
    cosine = np.cos(alpha_rad)
    sine = np.sin(alpha_rad)
    projection = state @ axis
    return (
        state * cosine
        + np.cross(np.broadcast_to(axis, state.shape), state) * sine
        + projection[:, None] * axis * (1.0 - cosine)
    )
