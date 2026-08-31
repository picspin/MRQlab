import pytest
from fastapi.testclient import TestClient

from mrqlab_api.main import app
from mrqlab_experiment import TissueModel, build_preset, run_experiment, validate_experiment
from mrqlab_sequence import SequenceIR


client = TestClient(app)


def block(identifier, kind, t0_s, params):
    return {"id": identifier, "kind": kind, "t0_s": t0_s, "params": params}


def _compose(blocks):
    response = client.post("/sequences/compose", json={"name": "lesson", "blocks": blocks})
    assert response.status_code == 200, response.text
    return SequenceIR.model_validate(response.json())


def test_compose_trap_declares_fov_m_with_physical_units():
    ir = _compose([
        block("rf1", "excite_sinc", 0, {"duration_s": .001, "time_bandwidth": 4, "flip_angle_deg": 90, "phase_deg": 0}),
        block("g1", "trap_gx", .001, {"amplitude_mt_m": 20, "duration_s": .001, "ramp_time_s": .0002, "unit": "mT_m"}),
        block("a1", "adc_gate", .002, {"duration_s": .001}),
    ])
    assert ir.metadata["gradient_units"] == "mt_m"
    assert ir.metadata["fov_m"] == 0.22
    assert ir.metadata["preferred_engine"] == "epg"


def test_composed_physical_ir_runs_epg_diffusion():
    ir = _compose([
        block("rf1", "excite_sinc", 0, {"duration_s": .001, "time_bandwidth": 4, "flip_angle_deg": 90, "phase_deg": 0}),
        block("g1", "trap_gx", .001, {"amplitude_mt_m": 20, "duration_s": .004, "ramp_time_s": .0004, "unit": "mT_m"}),
        block("a1", "adc_gate", .005, {"duration_s": .001}),
    ])
    graph = build_preset("dark-blood-tse")
    graph.sequence = ir
    graph.tissue = TissueModel(diffusion_adc_mm2_s=0.8e-3)
    assert validate_experiment(graph).valid
    run = run_experiment(graph)
    assert run.plan.engine == "epg"
    assert "isotropic_diffusion_applied" in run.sim_result.meta["assumptions"]
    quiet = graph.model_copy(deep=True)
    quiet.tissue = TissueModel(diffusion_adc_mm2_s=0.0)
    quiet_run = run_experiment(quiet)
    assert "isotropic_diffusion_applied" not in quiet_run.sim_result.meta["assumptions"]


def test_compose_without_trap_still_rejects_diffusion():
    ir = _compose([
        block("rf1", "excite_sinc", 0, {"duration_s": .001, "time_bandwidth": 4, "flip_angle_deg": 90, "phase_deg": 0}),
    ])
    graph = build_preset("dark-blood-tse")
    graph.sequence = ir
    graph.tissue = TissueModel(diffusion_adc_mm2_s=0.8e-3)
    assert not validate_experiment(graph).valid
    with pytest.raises(ValueError, match="gradient_units='mt_m'"):
        run_experiment(graph)
