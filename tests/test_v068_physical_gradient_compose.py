from fastapi.testclient import TestClient

from mrqlab_api.main import app


client = TestClient(app)


def block(identifier, kind, t0_s, params):
    return {"id": identifier, "kind": kind, "t0_s": t0_s, "params": params}


def test_compose_trap_writes_physical_mt_m_and_opts_in_gradient_units():
    response = client.post("/sequences/compose", json={"name": "lesson", "blocks": [
        block("rf1", "excite_sinc", 0, {"duration_s": .001, "time_bandwidth": 4, "flip_angle_deg": 90, "phase_deg": 0}),
        block("g1", "trap_gx", .001, {"amplitude_mt_m": 20, "duration_s": .001, "ramp_time_s": .0002, "unit": "mT_m"}),
        block("a1", "adc_gate", .002, {"duration_s": .001}),
    ]})
    assert response.status_code == 200, response.text
    ir = response.json()
    gx = next(channel for channel in ir["channels"] if channel["name"] == "gx")
    assert gx["events"][0]["value"] == 20
    assert gx["events"][0]["value"] != 1
    assert ir["metadata"]["gradient_units"] == "mt_m"
    overlay = ir["metadata"]["event_overlays"]["gx:0"]
    assert overlay["amplitude_mt_m"] == 20
    assert overlay["unit"] == "mT_m"


def test_compose_without_trap_does_not_claim_physical_gradient_units():
    response = client.post("/sequences/compose", json={"name": "rf-only", "blocks": [
        block("rf1", "excite_sinc", 0, {"duration_s": .001, "time_bandwidth": 4, "flip_angle_deg": 90, "phase_deg": 0}),
    ]})
    assert response.status_code == 200, response.text
    ir = response.json()
    assert ir["metadata"].get("gradient_units", "teaching") == "teaching"
