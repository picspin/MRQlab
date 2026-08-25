import numpy as np
import pytest

from mrqlab_experiment import TissueModel, build_preset, plan_experiment, run_experiment, validate_experiment
from mrqlab_experiment.capabilities import CapabilityMismatch
from mrqlab_experiment.kernel import _phantom_from_sample
from mrqlab_physics import MagnetizationTransferPools, Phantom
from mrqlab_physics.backends.epg_x import EpgXBackend, apply_magnetization_transfer
from mrqlab_physics.ops.types import RfOp


def _graph(*, bound=True):
    graph = build_preset("dark-blood-tse")
    graph.tissue = (
        TissueModel(id="a", t1=1, t2=.1, proton_density=.8, pool_fraction=.8,
                    exchange_rate_hz=2),
        TissueModel(id="b", t1=1.5, t2=.001, proton_density=.2, pool_fraction=.2,
                    bound_pool=bound),
    )
    graph.engine.preferred = "epg-x"
    return graph


def _pools(k=0):
    return MagnetizationTransferPools(1, .1, 1, 2, .5, k, k)


def test_default_tse_remains_classic_epg_without_mt_assumption():
    run = run_experiment(build_preset("dark-blood-tse"))
    assert run.plan.engine == "epg"
    assert "magnetization_transfer_applied" not in run.sim_result.meta["assumptions"]


def test_two_liquid_bm_remains_six_row_epgx():
    run = run_experiment(_graph(bound=False))
    assert "bloch_mcconnell_exchange_applied" in run.sim_result.meta["assumptions"]
    assert "magnetization_transfer_applied" not in run.sim_result.meta["assumptions"]


def test_bound_pool_exchange_runs_four_row_mt_epgx():
    graph = _graph()
    run = run_experiment(graph)
    assert run.sim_result.meta["engine"] == "epg-x"
    assert "magnetization_transfer_applied" in run.sim_result.meta["assumptions"]
    backend = EpgXBackend(_phantom_from_sample(graph), 2)
    assert backend.snapshot().shape == (4, 5)


@pytest.mark.parametrize("mutation", ["a_bound", "bound_no_exchange", "single_exchange"])
def test_invalid_bound_pool_contracts_fail_closed(mutation):
    graph = _graph()
    if mutation == "a_bound":
        graph.tissue[0].bound_pool = True
    elif mutation == "bound_no_exchange":
        graph.tissue[0].exchange_rate_hz = 0
    else:
        graph.tissue = TissueModel(exchange_rate_hz=1)
    assert not validate_experiment(graph).valid


def test_forced_bloch_mt_cannot_satisfy_exchange():
    graph = _graph()
    graph.engine.preferred = "bloch"
    with pytest.raises(CapabilityMismatch, match="cannot satisfy exchange"):
        plan_experiment(graph)


def test_mt_independent_relaxation_without_exchange():
    state = np.array([[1], [1], [0], [0]], dtype=complex)
    apply_magnetization_transfer(state, .1, _pools())
    assert state[0, 0] == pytest.approx(np.exp(-1))
    assert state[2, 0] == pytest.approx(1 - np.exp(-.1))
    assert state[3, 0] == pytest.approx(.5 * (1 - np.exp(-.05)))


def test_mt_exchange_conserves_longitudinal_magnetization():
    state = np.zeros((4, 1), complex)
    state[2, 0] = 1
    pools = MagnetizationTransferPools(1e12, .1, .5, 1e12, .5, 2, 2)
    apply_magnetization_transfer(state, .1, pools)
    assert 0 < state[3, 0].real < 1
    assert (state[2, 0] + state[3, 0]).real == pytest.approx(1, abs=1e-10)


def test_hard_rf_rotates_free_pool_only_and_leaves_bound_z_untouched():
    backend = EpgXBackend(Phantom(magnetization_transfer=_pools()), 0)
    z_bound = backend.omega[3, 0]
    backend.apply(RfOp(0, np.pi / 2, 0))
    assert backend.omega[3, 0] == z_bound
    assert abs(backend.omega[0, 0]) > 0
