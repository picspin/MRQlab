import numpy as np
import pytest

from mrqlab_experiment import build_preset, plan_experiment, run_experiment, validate_experiment
from mrqlab_experiment.capabilities import CapabilityMismatch, REPRESENTATIONS
from mrqlab_experiment.disturbances import Disturbance, DisturbanceStack
from mrqlab_experiment.observations import build_result_graph


def _graph(**parameters):
    graph = build_preset("dark-blood-tse")
    graph.disturbances = DisturbanceStack(
        items=(Disturbance(id="slice", kind="slice_profile", domain="sequence", parameters={"samples": 48, **parameters}),)
    )
    return graph


def _profile(graph):
    result = build_result_graph(run_experiment(graph))
    observation = next(item for item in result.observations if item.kind == "slice_profile")
    return observation, np.asarray(observation.data["mz"]), np.asarray(observation.data["mxy"])


def test_slice_profile_validates_runs_on_ssepg_and_is_spatially_nonflat():
    graph = _graph()
    assert validate_experiment(graph).valid
    observation, mz, mxy = _profile(graph)
    assert observation.provenance.engine == observation.provenance.representation == "ssepg"
    assert len(observation.data["z_m"]) >= 16
    assert np.ptp(mz) > 1e-3 or np.ptp(mxy) > 1e-3


def test_off_resonance_and_b1_change_backend_profile():
    _, default_mz, default_mxy = _profile(_graph())
    _, varied_mz, varied_mxy = _profile(_graph(off_resonance_hz=250.0, b1_linear_ramp=0.25))
    assert not np.allclose(default_mz, varied_mz)
    assert not np.allclose(default_mxy, varied_mxy)


def test_default_tse_remains_epg_and_hybrid_cannot_claim_slice_selective():
    assert plan_experiment(build_preset("dark-blood-tse")).representation == "epg"
    assert "slice_selective" not in REPRESENTATIONS["hybrid"].supports
    graph = _graph()
    graph.engine.preferred = "hybrid"
    with pytest.raises(CapabilityMismatch):
        plan_experiment(graph)
