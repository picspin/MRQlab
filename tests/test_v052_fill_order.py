from mrqlab_recon.trajectories import TrajectorySpec, generate_trajectory


def _unique_ky(traj: dict) -> list[float]:
    seen: list[float] = []
    last = None
    for ky in traj["ky"]:
        if last is None or abs(ky - last) > 1e-9:
            seen.append(ky)
            last = ky
    return seen


def test_cartesian_sequential_ky_is_monotonic():
    traj = generate_trajectory(
        TrajectorySpec(trajectory_type="cartesian", matrix_size=16, acceleration_factor=1, fill_order="sequential_ky")
    )
    kys = _unique_ky(traj)
    assert kys == sorted(kys)
    assert traj["fill_order"] == "sequential_ky"
    assert traj["declared_approximate"] is False


def test_cartesian_centric_ky_starts_near_kzero():
    traj = generate_trajectory(
        TrajectorySpec(trajectory_type="cartesian", matrix_size=16, acceleration_factor=1, fill_order="centric_ky")
    )
    kys = _unique_ky(traj)
    assert abs(kys[0]) <= abs(kys[-1])
    assert abs(kys[0]) < 0.2
    assert traj["fill_order"] == "centric_ky"


def test_epi_reverses_even_kx_lines():
    traj = generate_trajectory(
        TrajectorySpec(trajectory_type="cartesian", matrix_size=16, acceleration_factor=1, fill_order="epi")
    )
    n = 16
    first = traj["kx"][:n]
    second = traj["kx"][n : 2 * n]
    assert first[0] < first[-1]
    assert second[0] > second[-1]
    assert traj["fill_order"] == "epi"


def test_radial_spiral_are_declared_approximate():
    radial = generate_trajectory(TrajectorySpec(trajectory_type="radial", matrix_size=16, num_spokes_or_interleaves=8))
    spiral = generate_trajectory(TrajectorySpec(trajectory_type="spiral", num_spokes_or_interleaves=2, points_per_arm=32))
    assert radial["declared_approximate"] is True
    assert spiral["declared_approximate"] is True
    assert "geometric demo" in radial["honesty"]
