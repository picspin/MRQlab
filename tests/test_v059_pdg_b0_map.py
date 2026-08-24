import numpy as np
import pytest

from mrqlab_experiment import build_preset, plan_experiment, run_experiment, validate_experiment
from mrqlab_experiment.capabilities import CapabilityMismatch, REPRESENTATIONS
from mrqlab_experiment.disturbances import Disturbance, DisturbanceStack
from mrqlab_experiment.observations import build_result_graph
from mrqlab_physics import EngineOptions, Phantom, ScannerModel, list_engines
from mrqlab_physics.backends.pdg import PDGAdapter, PDGProviderUnavailable


def _graph(peak_hz=20.0):
    graph = build_preset("dark-blood-tse")
    graph.disturbances = DisturbanceStack(items=(Disturbance(
        id="b0", kind="b0_map", domain="field", parameters={"peak_hz": peak_hz, "bins": 32},
    ),))
    return graph


def test_b0_map_runs_on_builtin_pdg_and_emits_backend_distribution():
    graph = _graph()
    assert validate_experiment(graph).valid
    run = run_experiment(graph)
    assert run.plan.engine == run.plan.representation == "pdg"
    observation = next(item for item in build_result_graph(run).observations if item.kind == "phase_distribution")
    assert observation.provenance.engine == observation.provenance.representation == "pdg"
    assert len(observation.data["x_m"]) >= 16

    flat = run_experiment(_graph(0.0)).sim_result.phase_distribution
    ramp = run.sim_result.phase_distribution
    assert not np.allclose(ramp["configurations"], flat["configurations"])


def test_default_tse_and_other_dedicated_routes_remain_owned():
    assert plan_experiment(build_preset("dark-blood-tse")).representation == "epg"
    assert all("phase_distribution" not in REPRESENTATIONS[name].supports for name in ("bloch", "epg", "hybrid", "ssepg"))
    graph = _graph()
    graph.engine.preferred = "bloch"
    with pytest.raises(CapabilityMismatch):
        plan_experiment(graph)

    graph = build_preset("dark-blood-tse")
    graph.disturbances = DisturbanceStack(items=(Disturbance(id="slice", kind="slice_profile", domain="sequence"),))
    assert plan_experiment(graph).representation == "ssepg"


def test_builtin_pdg_does_not_replace_optional_provider_seam():
    pdg = next(item for item in list_engines() if item["name"] == "pdg")
    assert pdg["available"] is True
    assert pdg["source"] == "built-in"
    with pytest.raises(PDGProviderUnavailable):
        PDGAdapter().simulate(None, Phantom(), ScannerModel(), EngineOptions())
