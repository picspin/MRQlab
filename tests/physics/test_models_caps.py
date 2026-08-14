import numpy as np
import pytest

from mrqlab_physics import EngineOptions, Isochromat, Phantom
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
