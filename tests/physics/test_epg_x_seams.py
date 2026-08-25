import numpy as np

from mrqlab_physics.backends.epg_x import (
    EpgXLayout,
    apply_bloch_mcconnell,
    apply_magnetization_transfer,
    epg_x_zeros,
)
from mrqlab_physics import BlochMcConnellPools, MagnetizationTransferPools
from mrqlab_physics.ops.diffuse import diffusion_attenuation


def test_configuration_diffusion_attenuation_is_bounded_and_monotone():
    weights = [
        diffusion_attenuation(order, 100.0, 0.8e-9, 0.01)
        for order in range(4)
    ]
    assert weights[0] == 1.0
    assert all(0.0 < value <= 1.0 for value in weights)
    assert weights == sorted(weights, reverse=True)


def test_bm_and_mt_layout_shapes_are_stable():
    assert epg_x_zeros(EpgXLayout.BLOCH_MCCONNELL, kmax=2).shape == (6, 5)
    assert epg_x_zeros(EpgXLayout.MAGNETIZATION_TRANSFER, kmax=2).shape == (4, 5)


def test_bm_and_mt_evolve_at_their_named_seams():
    state = np.zeros((6, 5), dtype=np.complex128)
    state[2, 2] = 1
    pools = BlochMcConnellPools(1e12, 1, 1, 1e12, 1, 1, 2, 2)
    apply_bloch_mcconnell(state, dt=0.01, pools=pools)
    assert state[2, 2] < 1
    assert state[5, 2] > 0
    mt_state = np.zeros((4, 5), dtype=np.complex128)
    mt_state[2, 2] = 1
    mt_pools = MagnetizationTransferPools(1e12, 1, 1, 1e12, 1, 2, 2)
    apply_magnetization_transfer(mt_state, dt=0.01, pools=mt_pools)
    assert mt_state[2, 2] < 1
    assert mt_state[3, 2] > 0
