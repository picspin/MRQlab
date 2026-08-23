from fastapi.testclient import TestClient

from mrqlab_api.main import app
from mrqlab_sequence import build_sequence


client = TestClient(app)


def _tse():
    return build_sequence("TSE", {"te": 0.08, "tr": 2.0, "echoes": 4})


def test_patch_rf_event_returns_new_ir_with_overlay():
    ir = _tse()
    response = client.post("/sequences/patch", json={
        "ir": ir.model_dump(mode="json"),
        "event": {"channel": "rf_amp", "index": 0},
        "patch": {"duration_s": 0.003, "time_bandwidth": 4, "flip_angle_deg": 75, "phase_deg": 10},
    })
    assert response.status_code == 200
    result = response.json()
    assert result["metadata"]["event_overlays"]["rf_amp:0"]["flip_angle_deg"] == 75
    assert result["channels"][0]["events"][0]["value"] == 75
    assert all(
        all(a["time"] <= b["time"] for a, b in zip(channel["events"], channel["events"][1:]))
        for channel in result["channels"]
    )
    assert all(event["time"] <= result["duration"] for channel in result["channels"] for event in channel["events"])


def test_illegal_gradient_patch_is_422_and_input_ir_is_unchanged():
    ir = _tse()
    before = ir.model_dump()
    response = client.post("/sequences/patch", json={
        "ir": ir.model_dump(mode="json"),
        "event": {"channel": "gx", "index": 0},
        "patch": {"amplitude_mt_m": 99, "duration_s": 0.001, "ramp_time_s": 0.0001, "unit": "mT_m"},
    })
    assert response.status_code == 422
    assert ir.model_dump() == before


def test_unknown_event_is_422():
    ir = _tse()
    response = client.post("/sequences/patch", json={
        "ir": ir.model_dump(mode="json"), "event": {"channel": "gy", "index": 99},
        "patch": {"amplitude_mt_m": 1, "duration_s": 0.001, "ramp_time_s": 0.001, "unit": "mT_m"},
    })
    assert response.status_code == 422


def test_adc_patch_is_refused():
    ir = _tse()
    response = client.post("/sequences/patch", json={
        "ir": ir.model_dump(mode="json"), "event": {"channel": "adc_gate", "index": 0}, "patch": {},
    })
    assert response.status_code == 422
