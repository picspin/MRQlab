from fastapi.testclient import TestClient

from mrqlab_api.main import app


client = TestClient(app)


def block(identifier, kind, t0_s, duration_s, flip_angle_deg):
    return {
        "id": identifier,
        "kind": kind,
        "t0_s": t0_s,
        "params": {
            "duration_s": duration_s,
            "time_bandwidth": 4,
            "flip_angle_deg": flip_angle_deg,
            "phase_deg": 0,
        },
    }


def patch(ir, duration_s):
    return client.post(
        "/sequences/patch",
        json={
            "ir": ir,
            "event": {"channel": "rf_amp", "index": 0},
            "patch": {
                "duration_s": duration_s,
                "time_bandwidth": 6,
                "flip_angle_deg": 75,
                "phase_deg": 30,
            },
        },
    )


def test_rf_patch_rejects_duration_overlapping_next_rf_block():
    response = client.post(
        "/sequences/compose",
        json={
            "name": "two-pulse",
            "blocks": [
                block("rf1", "excite_sinc", 0, 0.001, 90),
                block("rf2", "refocus_sinc", 0.004, 0.002, 180),
            ],
        },
    )
    assert response.status_code == 200, response.text

    patched = patch(response.json(), 0.005)

    assert patched.status_code in (400, 422)
    assert "overlap" in patched.text.lower() or "duration" in patched.text.lower()


def test_rf_patch_rejects_duration_beyond_sequence_duration():
    response = client.post(
        "/sequences/compose",
        json={
            "name": "one-pulse",
            "blocks": [block("rf1", "excite_sinc", 0, 0.001, 90)],
        },
    )
    assert response.status_code == 200, response.text
    ir = response.json()

    patched = patch(ir, ir["duration"] + 0.001)

    assert patched.status_code in (400, 422)
    assert "duration" in patched.text.lower() or "beyond" in patched.text.lower()


def test_legal_rf_patch_preserves_overlay_phase_and_block_writeback():
    response = client.post(
        "/sequences/compose",
        json={
            "name": "two-pulse",
            "blocks": [
                block("rf1", "excite_sinc", 0, 0.001, 90),
                block("rf2", "refocus_sinc", 0.004, 0.002, 180),
            ],
        },
    )
    assert response.status_code == 200, response.text

    patched = patch(response.json(), 0.003)

    assert patched.status_code == 200, patched.text
    body = patched.json()
    overlay = body["metadata"]["event_overlays"]["rf_amp:0"]
    assert overlay["duration_s"] == 0.003
    phase = next(channel for channel in body["channels"] if channel["name"] == "rf_phase")
    assert phase["events"][0]["value"] == 30
    rf1 = next(block for block in body["metadata"]["blocks"] if block["id"] == "rf1")
    assert rf1["params"]["duration_s"] == 0.003
    assert rf1["params"]["flip_angle_deg"] == 75
    assert rf1["params"]["phase_deg"] == 30
    assert rf1["params"]["time_bandwidth"] == 6
