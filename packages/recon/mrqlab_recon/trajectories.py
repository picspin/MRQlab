from typing import Any, Literal
import numpy as np
from pydantic import BaseModel, Field


TrajectoryType = Literal["cartesian", "radial", "spiral", "stack_of_stars"]
FillOrder = Literal["sequential_ky", "centric_ky", "echo_train_centric", "epi"]


class TrajectorySpec(BaseModel):
    trajectory_type: TrajectoryType = "cartesian"
    matrix_size: int = Field(default=128, ge=16)
    num_spokes_or_interleaves: int = Field(default=32, ge=1)
    points_per_arm: int = Field(default=128, ge=16)
    num_slices: int = Field(default=1, ge=1)
    acceleration_factor: int = Field(default=1, ge=1)
    fill_order: FillOrder = "sequential_ky"


def generate_trajectory(spec: TrajectorySpec) -> dict[str, Any]:
    """Generate 2D/3D k-space trajectory coordinates (kx, ky, kz)."""
    kx_list = []
    ky_list = []
    kz_list = []

    if spec.trajectory_type == "cartesian":
        n = spec.matrix_size
        pe_indices = list(range(0, n, spec.acceleration_factor))
        center = n / 2.0
        if spec.fill_order in {"centric_ky", "echo_train_centric"}:
            pe_indices = sorted(pe_indices, key=lambda pe: (abs(pe - center), pe))
        for slice_idx in range(spec.num_slices):
            kz = (slice_idx - (spec.num_slices - 1) / 2.0) if spec.num_slices > 1 else 0.0
            for line_i, pe in enumerate(pe_indices):
                ky = (pe - center) / center
                kx_line = np.linspace(-1.0, 1.0, n)
                if spec.fill_order == "epi" and line_i % 2 == 1:
                    kx_line = kx_line[::-1]
                for kx in kx_line:
                    kx_list.append(float(kx))
                    ky_list.append(float(ky))
                    kz_list.append(float(kz))

    elif spec.trajectory_type == "radial":
        # Golden-angle or uniform radial spokes
        golden_angle = np.pi * (3.0 - np.sqrt(5.0))  # ~111.246 deg
        for slice_idx in range(spec.num_slices):
            kz = (slice_idx - (spec.num_slices - 1) / 2.0) if spec.num_slices > 1 else 0.0
            for spoke in range(spec.num_spokes_or_interleaves):
                theta = spoke * golden_angle
                r = np.linspace(-1.0, 1.0, spec.points_per_arm)
                for rad in r:
                    kx_list.append(float(rad * np.cos(theta)))
                    ky_list.append(float(rad * np.sin(theta)))
                    kz_list.append(float(kz))

    elif spec.trajectory_type == "spiral":
        # Archimedean multi-shot spiral
        num_arms = spec.num_spokes_or_interleaves
        for arm in range(num_arms):
            arm_offset = (2.0 * np.pi / num_arms) * arm
            t = np.linspace(0, 1.0, spec.points_per_arm)
            r = t
            theta = 6.0 * 2.0 * np.pi * t + arm_offset
            for rad, th in zip(r, theta):
                kx_list.append(float(rad * np.cos(th)))
                ky_list.append(float(rad * np.sin(th)))
                kz_list.append(0.0)

    elif spec.trajectory_type == "stack_of_stars":
        # Radial in (kx, ky), Cartesian phase encoding in kz
        golden_angle = np.pi * (3.0 - np.sqrt(5.0))
        for slice_idx in range(spec.num_slices):
            kz = (slice_idx - (spec.num_slices - 1) / 2.0) / max(1.0, spec.num_slices / 2.0)
            for spoke in range(spec.num_spokes_or_interleaves):
                theta = spoke * golden_angle
                r = np.linspace(-1.0, 1.0, spec.points_per_arm)
                for rad in r:
                    kx_list.append(float(rad * np.cos(theta)))
                    ky_list.append(float(rad * np.sin(theta)))
                    kz_list.append(float(kz))

    cartesian = spec.trajectory_type == "cartesian"
    return {
        "trajectory_type": spec.trajectory_type,
        "total_points": len(kx_list),
        "kx": kx_list,
        "ky": ky_list,
        "kz": kz_list,
        "density_compensation_available": not cartesian,
        "fill_order": spec.fill_order if cartesian else None,
        "declared_approximate": not cartesian,
        "honesty": (
            f"cartesian {spec.fill_order}"
            if cartesian
            else "geometric demo — not commercial sampling"
        ),
    }


def gridding_recon_2d(kx: np.ndarray, ky: np.ndarray, kdata: np.ndarray, grid_size: int = 128) -> np.ndarray:
    """
    Gridding reconstruction for non-Cartesian k-space data into Cartesian image space.
    Uses nearest-neighbor / triangular kernel gridding followed by 2D inverse FFT.
    """
    grid = np.zeros((grid_size, grid_size), dtype=np.complex128)
    weights = np.zeros((grid_size, grid_size), dtype=np.float64)

    # Scale kx, ky from [-1, 1] to [0, grid_size - 1]
    gx = ((kx + 1.0) / 2.0 * (grid_size - 1)).astype(np.int32)
    gy = ((ky + 1.0) / 2.0 * (grid_size - 1)).astype(np.int32)

    valid = (gx >= 0) & (gx < grid_size) & (gy >= 0) & (gy < grid_size)
    gx = gx[valid]
    gy = gy[valid]
    val = kdata[valid] if kdata.size else np.ones(np.sum(valid), dtype=np.complex128)

    for x, y, v in zip(gx, gy, val):
        grid[y, x] += v
        weights[y, x] += 1.0

    # Density normalization
    mask = weights > 0
    grid[mask] /= weights[mask]

    # Inverse FFT to image domain
    img = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(grid)))
    return np.abs(img)


def _make_nema_like_phantom(n: int) -> np.ndarray:
    """Single-slice geometric phantom (Physics lens only — not clinical anatomy)."""
    yy, xx = np.mgrid[-1.0:1.0:n * 1j, -1.0:1.0:n * 1j]
    disk = ((xx ** 2 + yy ** 2) < 0.72 ** 2).astype(np.float64) * 0.35
    v1 = (((xx - 0.22) ** 2 + (yy + 0.08) ** 2) < 0.16 ** 2).astype(np.float64) * 0.85
    v2 = (((xx + 0.28) ** 2 + (yy - 0.18) ** 2) < 0.11 ** 2).astype(np.float64) * 1.0
    v3 = (((xx + 0.05) ** 2 + (yy + 0.32) ** 2) < 0.08 ** 2).astype(np.float64) * 0.55
    return disk + v1 + v2 + v3


def undersampled_recon_demo(spec: TrajectorySpec) -> dict[str, Any]:
    """
    Backend-owned recon demo: sample a phantom along the requested trajectory
    and reconstruct. Cartesian R>1 produces PE aliasing; sparse radial/spiral
    produces streak / swirling artifacts. Frontend must only render this payload.
    """
    n = int(min(max(spec.matrix_size, 16), 64))
    phantom = _make_nema_like_phantom(n)
    kspace = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(phantom)))

    if spec.trajectory_type == "cartesian":
        sampled = np.zeros_like(kspace)
        sampled[:: spec.acceleration_factor, :] = kspace[:: spec.acceleration_factor, :]
        recon = np.abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(sampled))))
        traj = generate_trajectory(
            TrajectorySpec(
                trajectory_type="cartesian",
                matrix_size=n,
                acceleration_factor=spec.acceleration_factor,
                fill_order=spec.fill_order,
            )
        )
    else:
        demo_spec = spec.model_copy(
            update={
                "matrix_size": n,
                "points_per_arm": n,
                "num_slices": 1 if spec.trajectory_type != "stack_of_stars" else min(spec.num_slices, 4),
            }
        )
        traj = generate_trajectory(demo_spec)
        kx = np.asarray(traj["kx"], dtype=np.float64)
        ky = np.asarray(traj["ky"], dtype=np.float64)
        gx = np.clip(((kx + 1.0) / 2.0 * (n - 1)).astype(np.int32), 0, n - 1)
        gy = np.clip(((ky + 1.0) / 2.0 * (n - 1)).astype(np.int32), 0, n - 1)
        kdata = kspace[gy, gx]
        recon = gridding_recon_2d(kx, ky, kdata, grid_size=n)

    p_norm = phantom / (float(np.max(phantom)) + 1e-12)
    r_norm = recon / (float(np.max(recon)) + 1e-12)
    nrmse = float(np.sqrt(np.mean((r_norm - p_norm) ** 2)))

    stride = max(1, traj["total_points"] // 1500)
    return {
        "matrix": n,
        "trajectory_type": spec.trajectory_type,
        "acceleration_factor": spec.acceleration_factor,
        "nrmse": nrmse,
        "phantom": np.round(phantom, 4).tolist(),
        "recon": np.round(recon, 4).tolist(),
        "preview": {
            "kx": traj["kx"][::stride],
            "ky": traj["ky"][::stride],
            "total_points": traj["total_points"],
            "preview_stride": stride,
        },
        "fill_order": traj.get("fill_order"),
        "declared_approximate": traj.get("declared_approximate", False),
        "honesty": traj.get("honesty", ""),
    }
