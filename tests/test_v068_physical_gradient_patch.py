from fastapi.testclient import TestClient

from mrqlab_api.main import app
from mrqlab_sequence import Channel, Event, SequenceIR


client = TestClient(app)


def _physical_ir():
    return SequenceIR(
        name="physical-g",
        duration=0.02,
        channels=[
            Channel(name="rf_amp", events=[Event(time=0.0, value=90)]),
            Channel(name="gx", events=[Event(time=0.004, value=20)]),
            Channel(name="gy", events=[]),
            Channel(name="gz", events=[]),
            Channel(name="adc_gate", events=[]),
        ],
        metadata={"gradient_units": "mt_m"},
    )


def _teaching_ir():
    return SequenceIR(
        name="teaching-g",
        duration=0.02,
        channels=[
            Channel(name="rf_amp", events=[Event(time=0.0, value=90)]),
            Channel(name="gx", events=[Event(time=0.004, value=1)]),
            Channel(name="gy", events=[]),
            Channel(name="gz", events=[]),
            Channel(name="adc_gate", events=[]),
        ],
    )


def test_physical_g_patch_writes_channel_mt_m():
    ir = _physical_ir()
    response = client.post("/sequences/patch", json={
        "ir": ir.model_dump(mode="json"),
        "event": {"channel": "gx", "index": 0},
        "patch": {"amplitude_mt_m": 12, "duration_s": 0.002, "ramp_time_s": 0.0004, "unit": "mT_m"},
    })
    assert response.status_code == 200, response.text
    result = response.json()
    gx = next(channel for channel in result["channels"] if channel["name"] == "gx")
    assert gx["events"][0]["value"] == 12
    overlay = result["metadata"]["event_overlays"]["gx:0"]
    assert overlay["amplitude_mt_m"] == 12
    assert result["metadata"]["gradient_units"] == "mt_m"


def test_teaching_g_patch_keeps_normalized_channel_value():
    ir = _teaching_ir()
    response = client.post("/sequences/patch", json={
        "ir": ir.model_dump(mode="json"),
        "event": {"channel": "gx", "index": 0},
        "patch": {"amplitude_mt_m": 12, "duration_s": 0.002, "ramp_time_s": 0.0004, "unit": "mT_m"},
    })
    assert response.status_code == 200, response.text
    result = response.json()
    gx = next(channel for channel in result["channels"] if channel["name"] == "gx")
    assert gx["events"][0]["value"] == 1
    overlay = result["metadata"]["event_overlays"]["gx:0"]
    assert overlay["amplitude_mt_m"] == 12
    assert result["metadata"].get("gradient_units", "teaching") == "teaching"
