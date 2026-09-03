from fastapi.testclient import TestClient

from mrqlab_api.main import app


client = TestClient(app)


def block(identifier, kind, t0_s, params):
    return {"id": identifier, "kind": kind, "t0_s": t0_s, "params": params}


def gradient_params(amplitude, duration, ramp):
    return {
        "amplitude_mt_m": amplitude,
        "duration_s": duration,
        "ramp_time_s": ramp,
        "unit": "mT_m",
    }


def patch_gx(ir, index, *, amplitude, duration, ramp):
    return client.post("/sequences/patch", json={
        "ir": ir,
        "event": {"channel": "gx", "index": index},
        "patch": gradient_params(amplitude, duration, ramp),
    })


def test_physical_g_patch_writes_channel_end_zero_overlay_and_block_params():
    original = gradient_params(20, 0.001, 0.0002)
    response = client.post("/sequences/compose", json={
        "name": "lesson",
        "duration_s": 0.01,
        "blocks": [block("g1", "trap_gx", 0.002, original)],
    })
    assert response.status_code == 200, response.text

    patched_response = patch_gx(response.json(), 0, amplitude=12, duration=0.003, ramp=0.0004)
    assert patched_response.status_code == 200, patched_response.text
    patched = patched_response.json()
    gx = next(channel for channel in patched["channels"] if channel["name"] == "gx")
    assert gx["events"][0] == {"time": 0.002, "value": 12.0}
    assert gx["events"][1] == {"time": 0.005, "value": 0.0}
    assert patched["metadata"]["event_overlays"]["gx:0"] == gradient_params(12, 0.003, 0.0004)
    block0 = patched["metadata"]["blocks"][0]
    assert block0["kind"] == "trap_gx"
    assert block0["params"] == gradient_params(12, 0.003, 0.0004)


def test_physical_g_patch_updates_only_time_ordered_later_trap_block():
    early = gradient_params(8, 0.001, 0.0002)
    late = gradient_params(20, 0.001, 0.0002)
    response = client.post("/sequences/compose", json={
        "name": "two traps",
        "duration_s": 0.012,
        "blocks": [
            block("late", "trap_gx", 0.006, late),
            block("early", "trap_gx", 0.001, early),
        ],
    })
    assert response.status_code == 200, response.text

    patched_response = patch_gx(response.json(), 1, amplitude=14, duration=0.002, ramp=0.0003)
    assert patched_response.status_code == 200, patched_response.text
    blocks = {item["id"]: item for item in patched_response.json()["metadata"]["blocks"]}
    assert blocks["early"]["params"] == early
    assert blocks["late"]["params"] == gradient_params(14, 0.002, 0.0003)


def test_teaching_g_patch_without_blocks_stays_overlay_only():
    teaching = {
        "name": "teaching",
        "duration": 0.01,
        "channels": [
            {"name": "rf_amp", "events": []},
            {"name": "gx", "events": [{"time": 0.001, "value": 1}]},
            {"name": "gy", "events": []},
            {"name": "gz", "events": []},
            {"name": "adc_gate", "events": []},
        ],
        "metadata": {},
    }
    response = patch_gx(teaching, 0, amplitude=12, duration=0.002, ramp=0.0004)
    assert response.status_code == 200, response.text
    patched = response.json()
    gx = next(channel for channel in patched["channels"] if channel["name"] == "gx")
    assert gx["events"][0]["value"] == 1
    assert "blocks" not in patched["metadata"]
    assert patched["metadata"]["event_overlays"]["gx:0"] == gradient_params(12, 0.002, 0.0004)
