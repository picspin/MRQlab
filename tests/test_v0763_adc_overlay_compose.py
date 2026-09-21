from fastapi.testclient import TestClient

from mrqlab_api.main import app


client = TestClient(app)


def block(identifier, kind, t0_s, params):
    return {"id": identifier, "kind": kind, "t0_s": t0_s, "params": params}


def test_compose_adc_writes_duration_overlay_and_gate_edges():
    response = client.post("/sequences/compose", json={"name": "readout", "blocks": [
        block("adc1", "adc_gate", 0.01, {"duration_s": 0.004}),
    ]})
    assert response.status_code == 200, response.text
    ir = response.json()
    assert ir["metadata"]["event_overlays"]["adc_gate:0"]["duration_s"] == 0.004
    adc = next(channel for channel in ir["channels"] if channel["name"] == "adc_gate")
    assert adc["events"] == [{"time": 0.01, "value": 1.0}, {"time": 0.014, "value": 0.0}]


def test_compose_adc_overlays_are_indexed_in_time_order():
    response = client.post("/sequences/compose", json={"name": "two-readouts", "blocks": [
        block("adc-late", "adc_gate", 0.02, {"duration_s": 0.003}),
        block("adc-early", "adc_gate", 0.01, {"duration_s": 0.004}),
    ]})
    assert response.status_code == 200, response.text
    overlays = response.json()["metadata"]["event_overlays"]
    assert overlays["adc_gate:0"]["duration_s"] == 0.004
    assert overlays["adc_gate:1"]["duration_s"] == 0.003


def test_compose_rf_only_does_not_write_adc_overlay():
    response = client.post("/sequences/compose", json={"name": "rf-only", "blocks": [
        block("rf1", "excite_sinc", 0, {
            "duration_s": 0.003,
            "time_bandwidth": 4,
            "flip_angle_deg": 90,
            "phase_deg": 0,
        }),
    ]})
    assert response.status_code == 200, response.text
    overlays = response.json()["metadata"]["event_overlays"]
    assert not any(key.startswith("adc_gate:") for key in overlays)
