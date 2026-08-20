import numpy as np
from fastapi.testclient import TestClient

from mrqlab_api.main import app
from mrqlab_recon import fft_reconstruct, nufft_reconstruct
from mrqlab_recon.trajectories import (
    TrajectorySpec,
    generate_trajectory,
    undersampled_recon_demo,
)

client = TestClient(app)


def test_cartesian_and_noncartesian_trajectories():
    cart = generate_trajectory(TrajectorySpec(trajectory_type="cartesian", matrix_size=32, acceleration_factor=2))
    assert cart["total_points"] == 32 * (32 // 2)
    assert cart["density_compensation_available"] is False

    radial = generate_trajectory(
        TrajectorySpec(trajectory_type="radial", matrix_size=32, num_spokes_or_interleaves=16, points_per_arm=32)
    )
    assert radial["total_points"] == 16 * 32
    assert radial["density_compensation_available"] is True
    assert max(abs(x) for x in radial["kx"]) <= 1.0001

    spiral = generate_trajectory(
        TrajectorySpec(trajectory_type="spiral", num_spokes_or_interleaves=4, points_per_arm=64)
    )
    assert spiral["total_points"] == 4 * 64

    sos = generate_trajectory(
        TrajectorySpec(
            trajectory_type="stack_of_stars",
            num_spokes_or_interleaves=8,
            points_per_arm=16,
            num_slices=4,
        )
    )
    assert sos["total_points"] == 8 * 16 * 4
    assert len(set(round(z, 6) for z in sos["kz"])) == 4


def test_cartesian_undersampling_increases_nrmse():
    full = undersampled_recon_demo(
        TrajectorySpec(trajectory_type="cartesian", matrix_size=32, acceleration_factor=1)
    )
    acc = undersampled_recon_demo(
        TrajectorySpec(trajectory_type="cartesian", matrix_size=32, acceleration_factor=4)
    )
    assert full["nrmse"] < 0.15
    assert acc["nrmse"] > full["nrmse"]
    assert acc["matrix"] == 32
    assert np.array(acc["recon"]).shape == (32, 32)


def test_nufft_adapter_grids_radial_to_image():
    spec = TrajectorySpec(trajectory_type="radial", matrix_size=32, num_spokes_or_interleaves=24, points_per_arm=32)
    traj = generate_trajectory(spec)
    kx = np.array(traj["kx"])
    ky = np.array(traj["ky"])
    kdata = np.exp(-4.0 * (kx ** 2 + ky ** 2)).astype(np.complex128)
    img = nufft_reconstruct(kx, ky, kdata, grid_size=32)
    assert img.shape == (32, 32)
    assert float(np.max(img)) > 0.0


def test_fft_reconstruct_roundtrip_impulse():
    data = np.zeros((16, 16), dtype=np.complex128)
    data[8, 8] = 1.0
    img = np.abs(fft_reconstruct(data, dimensions=2))
    assert img.shape == (16, 16)
    assert img[0, 0] == np.max(img)


def test_trajectory_and_recon_demo_endpoints():
    traj_res = client.post(
        "/trajectories/generate",
        json={"trajectory_type": "spiral", "matrix_size": 32, "num_spokes_or_interleaves": 3, "points_per_arm": 48},
    )
    assert traj_res.status_code == 200
    body = traj_res.json()
    assert body["trajectory_type"] == "spiral"
    assert body["total_points"] == 3 * 48
    assert "kx" in body and "ky" in body

    demo_res = client.post(
        "/recon/demo",
        json={"trajectory_type": "cartesian", "matrix_size": 32, "acceleration_factor": 2},
    )
    assert demo_res.status_code == 200
    demo = demo_res.json()
    assert demo["acceleration_factor"] == 2
    assert "nrmse" in demo
    assert "preview" in demo
    assert len(demo["recon"]) == demo["matrix"]
