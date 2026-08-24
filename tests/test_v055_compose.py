from fastapi.testclient import TestClient

from mrqlab_api.main import app


client = TestClient(app)


def block(identifier, kind, t0_s, params):
    return {"id": identifier, "kind": kind, "t0_s": t0_s, "params": params}


def test_compose_three_teaching_blocks():
    response = client.post("/sequences/compose", json={"name": "lesson", "blocks": [
        block("rf1", "excite_sinc", 0, {"duration_s": .001, "time_bandwidth": 4, "flip_angle_deg": 90, "phase_deg": 0}),
        block("g1", "trap_gx", .001, {"amplitude_mt_m": 20, "duration_s": .001, "ramp_time_s": .0002, "unit": "mT_m"}),
        block("a1", "adc_gate", .002, {"duration_s": .001}),
    ]})
    assert response.status_code == 200
    ir = response.json()
    channels = {channel["name"]: channel["events"] for channel in ir["channels"]}
    assert channels["rf_amp"] and channels["gx"] and channels["adc_gate"]
    assert len(ir["metadata"]["blocks"]) == 3
    assert all(events == sorted(events, key=lambda event: event["time"]) for events in channels.values())
    assert all(event["time"] <= ir["duration"] for events in channels.values() for event in events)


def test_illegal_slew_is_rejected():
    response = client.post("/sequences/compose", json={"name": "bad", "blocks": [
        block("g1", "trap_gx", 0, {"amplitude_mt_m": 99, "duration_s": .001, "ramp_time_s": .0001, "unit": "mT_m"})
    ]})
    assert response.status_code == 422


def test_overlapping_rf_is_rejected():
    params = {"duration_s": .002, "time_bandwidth": 4, "flip_angle_deg": 90, "phase_deg": 0}
    response = client.post("/sequences/compose", json={"name": "bad", "blocks": [
        block("rf1", "excite_sinc", 0, params), block("rf2", "excite_sinc", .001, params)
    ]})
    assert response.status_code == 422


def test_unknown_kind_is_rejected():
    response = client.post("/sequences/compose", json={"name": "bad", "blocks": [block("x", "vendor", 0, {})]})
    assert response.status_code == 422


def test_requested_duration_equal_to_last_block_end_is_legal():
    response = client.post("/sequences/compose", json={"name": "half-open", "duration_s": .001, "blocks": [
        block("a1", "adc_gate", 0, {"duration_s": .001}),
    ]})
    assert response.status_code == 200, response.text
    assert response.json()["duration"] == .001


def test_requested_duration_before_last_block_end_is_rejected():
    response = client.post("/sequences/compose", json={"name": "too-short", "duration_s": .0009, "blocks": [
        block("a1", "adc_gate", 0, {"duration_s": .001}),
    ]})
    assert response.status_code == 422
