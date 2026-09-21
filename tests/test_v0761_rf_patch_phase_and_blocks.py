from fastapi.testclient import TestClient

from mrqlab_api.main import app


client = TestClient(app)


def block(identifier, kind, t0_s, params):
    return {"id": identifier, "kind": kind, "t0_s": t0_s, "params": params}


def _compose_excite():
    response = client.post("/sequences/compose", json={"name": "lesson", "duration_s": 0.01, "blocks": [
        block("rf1", "excite_sinc", 0, {
            "duration_s": 0.001,
            "time_bandwidth": 4,
            "flip_angle_deg": 90,
            "phase_deg": 0,
        }),
    ]})
    assert response.status_code == 200, response.text
    return response.json()


def test_rf_patch_writes_rf_phase_and_metadata_blocks():
    ir = _compose_excite()
    response = client.post("/sequences/patch", json={
        "ir": ir,
        "event": {"channel": "rf_amp", "index": 0},
        "patch": {
            "duration_s": 0.003,
            "time_bandwidth": 6,
            "flip_angle_deg": 75,
            "phase_deg": 30,
        },
    })
    assert response.status_code == 200, response.text
    patched = response.json()
    rf = next(channel for channel in patched["channels"] if channel["name"] == "rf_amp")
    phase = next(channel for channel in patched["channels"] if channel["name"] == "rf_phase")
    assert rf["events"][0]["value"] == 75
    assert phase["events"][0]["time"] == rf["events"][0]["time"]
    assert phase["events"][0]["value"] == 30
    overlay = patched["metadata"]["event_overlays"]["rf_amp:0"]
    assert overlay["flip_angle_deg"] == 75
    assert overlay["phase_deg"] == 30
    assert overlay["duration_s"] == 0.003
    assert overlay["time_bandwidth"] == 6
    block0 = patched["metadata"]["blocks"][0]
    assert block0["kind"] == "excite_sinc"
    assert block0["params"]["flip_angle_deg"] == 75
    assert block0["params"]["phase_deg"] == 30
    assert block0["params"]["duration_s"] == 0.003
    assert block0["params"]["time_bandwidth"] == 6


def test_rf_patch_updates_time_ordered_block_not_request_order():
    response = client.post("/sequences/compose", json={"name": "se", "duration_s": 0.01, "blocks": [
        block("rf2", "refocus_sinc", 0.004, {
            "duration_s": 0.002,
            "time_bandwidth": 4,
            "flip_angle_deg": 180,
            "phase_deg": 90,
        }),
        block("rf1", "excite_sinc", 0, {
            "duration_s": 0.001,
            "time_bandwidth": 8,
            "flip_angle_deg": 90,
            "phase_deg": 0,
        }),
    ]})
    assert response.status_code == 200, response.text
    ir = response.json()
    patched = client.post("/sequences/patch", json={
        "ir": ir,
        "event": {"channel": "rf_amp", "index": 1},
        "patch": {
            "duration_s": 0.0025,
            "time_bandwidth": 5,
            "flip_angle_deg": 160,
            "phase_deg": 45,
        },
    })
    assert patched.status_code == 200, patched.text
    body = patched.json()
    phase = next(channel for channel in body["channels"] if channel["name"] == "rf_phase")
    assert phase["events"][1]["value"] == 45
    blocks = body["metadata"]["blocks"]
    refocus = next(block for block in blocks if block["id"] == "rf2")
    excite = next(block for block in blocks if block["id"] == "rf1")
    assert refocus["params"]["flip_angle_deg"] == 160
    assert refocus["params"]["phase_deg"] == 45
    assert excite["params"]["flip_angle_deg"] == 90
    assert excite["params"]["phase_deg"] == 0
