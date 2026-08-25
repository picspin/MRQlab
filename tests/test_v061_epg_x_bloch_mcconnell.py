import numpy as np
import pytest

from mrqlab_experiment import TissueModel, build_preset, plan_experiment, run_experiment, validate_experiment
from mrqlab_experiment.capabilities import CapabilityMismatch
from mrqlab_physics import BlochMcConnellPools, MagnetizationTransferPools, list_engines
from mrqlab_physics.backends.epg_x import apply_bloch_mcconnell, apply_magnetization_transfer


def _pools(k=2.0):
    return BlochMcConnellPools(1e12, .1, .5, 1e12, .2, .5, k, k)


def _exchange_graph():
    graph = build_preset("dark-blood-tse")
    graph.tissue = (
        TissueModel(id="a", t1=1, t2=.1, proton_density=.6, pool_fraction=.5, exchange_rate_hz=2),
        TissueModel(id="b", t1=1.5, t2=.2, proton_density=.4, pool_fraction=.5),
    )
    graph.engine.preferred = "epg-x"
    return graph


def test_default_tse_remains_classic_epg():
    run = run_experiment(build_preset("dark-blood-tse"))
    assert run.plan.engine == "epg"
    assert "bloch_mcconnell_exchange_applied" not in run.sim_result.meta["assumptions"]


def test_single_exchange_tissue_fails_closed():
    graph = build_preset("dark-blood-tse")
    graph.tissue = TissueModel(exchange_rate_hz=1)
    assert not validate_experiment(graph).valid


def test_two_pool_exchange_runs_on_dedicated_engine():
    graph = _exchange_graph()
    plan = plan_experiment(graph)
    assert plan.engine == plan.representation == "epg-x"
    run = run_experiment(graph)
    assert run.sim_result.meta["engine"] == "epg-x"
    assert "bloch_mcconnell_exchange_applied" in run.sim_result.meta["assumptions"]


def test_forced_non_epgx_exchange_fails_closed():
    graph = _exchange_graph()
    graph.engine.preferred = "bloch"
    with pytest.raises(CapabilityMismatch, match="cannot satisfy exchange"):
        plan_experiment(graph)
    assert not validate_experiment(graph).valid


def test_independent_relaxation_without_exchange():
    state = np.zeros((6, 1), complex)
    state[:, 0] = (1, 1, 0, 1, 1, 0)
    pools = BlochMcConnellPools(1, .1, 1, 2, .2, .5, 0, 0)
    apply_bloch_mcconnell(state, .1, pools)
    assert state[0, 0] == pytest.approx(np.exp(-1))
    assert state[3, 0] == pytest.approx(np.exp(-.5))
    assert state[2, 0] == pytest.approx(1 - np.exp(-.1))
    assert state[5, 0] == pytest.approx(.5 * (1 - np.exp(-.05)))


def test_exchange_mixes_and_conserves_longitudinal_label():
    state = np.zeros((6, 1), complex)
    state[2, 0] = 1
    apply_bloch_mcconnell(state, .1, _pools())
    assert 0 < state[5, 0].real < 1
    assert (state[2, 0] + state[5, 0]).real == pytest.approx(1, abs=1e-10)


def test_mt_operator_and_registry_are_open():
    state = np.zeros((4, 1), complex)
    state[2, 0] = 1
    apply_magnetization_transfer(
        state, .1, MagnetizationTransferPools(1e12, .1, .5, 1e12, .5, 2, 2)
    )
    assert state[3, 0] > 0
    descriptor = next(item for item in list_engines() if item["name"] == "epg-x")
    assert descriptor["available"] is True
    assert descriptor["source"] == "built-in"
