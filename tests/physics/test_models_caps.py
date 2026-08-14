import numpy as np
import pytest

from mrqlab_physics import (
    EngineOptions,
    Isochromat,
    Phantom,
    ScannerModel,
    SpectralPool,
)
from mrqlab_physics.kernel.caps import enforce_work_limit, estimate_work
from mrqlab_physics.kernel.units import deg_to_rad


def test_legacy_phantom_resolves_to_one_isochromat():
    spins = Phantom(
        t1=0.9, t2=0.08, proton_density=0.7, off_resonance_hz=12
    ).resolved_isochromats()
    assert spins == (
        Isochromat(t1=0.9, t2=0.08, proton_density=0.7, off_resonance_hz=12),
    )


def test_ir_degrees_convert_once_at_boundary():
    assert deg_to_rad(180.0) == pytest.approx(np.pi)


def test_engine_work_models_state_width():
    assert estimate_work("bloch", n_ops=10, n_isochromats=4, epg_kmax=8, n_pools=1) == 40
    assert estimate_work("epg", n_ops=10, n_isochromats=1, epg_kmax=8, n_pools=1) == 510
    assert estimate_work("spectral", n_ops=10, n_isochromats=3, epg_kmax=8, n_pools=2) == 60


def test_work_cap_rejects_before_backend_allocation():
    with pytest.raises(ValueError, match="estimated work 510 exceeds max_work 500"):
        enforce_work_limit("epg", 10, 1, EngineOptions(epg_kmax=8, max_work=500), 1)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: Isochromat(off_resonance_hz=np.nan),
        lambda: Isochromat(position_m=(0.0, np.inf, 0.0)),
        lambda: Phantom(t1=np.nan),
        lambda: SpectralPool("water", 1.0, np.inf, 1.0, 0.1),
        lambda: ScannerModel(gradient_scale=np.nan),
        lambda: EngineOptions(dwell_time=np.inf),
    ],
)
def test_public_physics_models_reject_non_finite_numbers(factory):
    with pytest.raises(ValueError, match="finite"):
        factory()


@pytest.mark.parametrize(
    "options",
    [
        {"epg_kmax": True},
        {"epg_kmax": 1.5},
        {"max_work": False},
        {"max_work": 10.0},
        {"return_magnetization": 1},
        {"return_configurations": 0},
    ],
)
def test_engine_options_reject_non_strict_integer_and_boolean_fields(options):
    with pytest.raises((TypeError, ValueError), match="strict"):
        EngineOptions(**options)
