from fastapi.testclient import TestClient

from mrqlab_api.main import app


client = TestClient(app)


def rf_block(identifier, kind, t0_s, duration_s, flip_angle_deg):
    return {
        "id": identifier,
        "kind": kind,
        "t0_s": t0_s,
        "params": {
            "duration_s": duration_s,
            "time_bandwidth": 4,
            "flip_angle_deg": flip_angle_deg,
            "phase_deg": 30,
        },
    }


def compose(blocks, *, duration_s=None):
    payload = {"name": "rf-end-zero", "blocks": blocks}
    if duration_s is not None:
        payload["duration_s"] = duration_s
    return client.post("/sequences/compose", json=payload)


def patch_duration(ir, duration_s):
    return client.post(
        "/sequences/patch",
        json={
            "ir": ir,
            "event": {"channel": "rf_amp", "index": 0},
            "patch": {
                "duration_s": duration_s,
                "time_bandwidth": 6,
                "flip_angle_deg": 75,
                "phase_deg": 45,
            },
        },
    )


def channel(ir, name):
    return next(item for item in ir["channels"] if item["name"] == name)


def test_compose_rf_emits_amp_end_zero_but_no_phase_end_zero():
    response = compose([rf_block("rf1", "excite_sinc", 0.001, 0.002, 90)])
    assert response.status_code == 200, response.text

    body = response.json()
    assert channel(body, "rf_amp")["events"] == [
        {"time": 0.001, "value": 90.0},
        {"time": 0.003, "value": 0.0},
    ]
    assert channel(body, "rf_phase")["events"] == [{"time": 0.001, "value": 30.0}]


def test_overlapping_rf_blocks_remain_fail_closed():
    response = compose([
        rf_block("rf1", "excite_sinc", 0, 0.002, 90),
        rf_block("rf2", "refocus_sinc", 0.001, 0.002, 180),
    ])
    assert response.status_code in (400, 422)
    assert "overlap" in response.text.lower()


def test_rf_duration_patch_moves_composed_end_zero():
    response = compose(
        [rf_block("rf1", "excite_sinc", 0.001, 0.002, 90)],
        duration_s=0.008,
    )
    assert response.status_code == 200, response.text

    patched = patch_duration(response.json(), 0.004)
    assert patched.status_code == 200, patched.text
    events = channel(patched.json(), "rf_amp")["events"]
    assert {"time": 0.005, "value": 0.0} in events
    assert {"time": 0.003, "value": 0.0} not in events


def test_rf_patch_does_not_add_end_zero_to_teaching_ir():
    teaching_ir = {
        "name": "teaching-overlay",
        "duration": 0.008,
        "channels": [
            {"name": "rf_amp", "events": [{"time": 0.001, "value": 90}]},
            {"name": "rf_phase", "events": [{"time": 0.001, "value": 0}]},
        ],
        "metadata": {"event_overlays": {}},
    }
    patched = patch_duration(teaching_ir, 0.004)
    assert patched.status_code == 200, patched.text
    assert channel(patched.json(), "rf_amp")["events"] == [{"time": 0.001, "value": 75.0}]
