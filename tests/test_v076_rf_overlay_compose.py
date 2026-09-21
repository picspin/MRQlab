from fastapi.testclient import TestClient

from mrqlab_api.main import app


client = TestClient(app)


def block(identifier, kind, t0_s, params):
    return {"id": identifier, "kind": kind, "t0_s": t0_s, "params": params}


def test_compose_excite_writes_rf_overlay_not_just_channel_fa():
    response = client.post("/sequences/compose", json={"name": "lesson", "blocks": [
        block("rf1", "excite_sinc", 0, {
            "duration_s": 0.003,
            "time_bandwidth": 6,
            "flip_angle_deg": 75,
            "phase_deg": 30,
        }),
    ]})
    assert response.status_code == 200, response.text
    ir = response.json()
    rf = next(channel for channel in ir["channels"] if channel["name"] == "rf_amp")
    assert rf["events"][0]["value"] == 75
    overlay = ir["metadata"]["event_overlays"]["rf_amp:0"]
    assert overlay["duration_s"] == 0.003
    assert overlay["time_bandwidth"] == 6
    assert overlay["flip_angle_deg"] == 75
    assert overlay["phase_deg"] == 30
    assert "rf_amp:0" in ir["metadata"]["event_overlays"]
    assert "gx:0" not in ir["metadata"]["event_overlays"]


def test_compose_two_rf_blocks_index_overlays_in_time_order():
    response = client.post("/sequences/compose", json={"name": "se", "blocks": [
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
    overlays = response.json()["metadata"]["event_overlays"]
    assert overlays["rf_amp:0"]["flip_angle_deg"] == 90
    assert overlays["rf_amp:0"]["duration_s"] == 0.001
    assert overlays["rf_amp:0"]["time_bandwidth"] == 8
    assert overlays["rf_amp:1"]["flip_angle_deg"] == 180
    assert overlays["rf_amp:1"]["duration_s"] == 0.002
    assert overlays["rf_amp:1"]["phase_deg"] == 90
