from fastapi.testclient import TestClient

from mrqlab_api.main import app
from mrqlab_physics import EngineOptions
from mrqlab_physics.kernel.scheduler import schedule
from mrqlab_physics.ops.types import GradInterval
from mrqlab_sequence import SequenceIR


client = TestClient(app)


def block(identifier, kind, t0_s, params):
    return {"id": identifier, "kind": kind, "t0_s": t0_s, "params": params}


def _compose(trap_duration_s, *, sequence_duration_s, ramp_time_s):
    response = client.post("/sequences/compose", json={
        "name": "lesson",
        "duration_s": sequence_duration_s,
        "blocks": [
            block("rf1", "excite_sinc", 0, {
                "duration_s": .001, "time_bandwidth": 4, "flip_angle_deg": 90, "phase_deg": 0,
            }),
            block("g1", "trap_gx", .001, {
                "amplitude_mt_m": 20, "duration_s": trap_duration_s,
                "ramp_time_s": ramp_time_s, "unit": "mT_m",
            }),
            block("a1", "adc_gate", .001 + trap_duration_s, {"duration_s": .001}),
        ],
    })
    assert response.status_code == 200, response.text
    return SequenceIR.model_validate(response.json())


def _gx_moment(ir):
    operators = schedule(ir, EngineOptions(dwell_time=1e-4))
    return sum(op.dt * op.gradient[0] for op in operators if isinstance(op, GradInterval))


def _patch_duration(ir, duration_s, *, ramp_time_s):
    response = client.post("/sequences/patch", json={
        "ir": ir.model_dump(mode="json"),
        "event": {"channel": "gx", "index": 0},
        "patch": {
            "amplitude_mt_m": 20,
            "duration_s": duration_s,
            "ramp_time_s": ramp_time_s,
            "unit": "mT_m",
        },
    })
    assert response.status_code == 200, response.text
    return SequenceIR.model_validate(response.json())


def test_physical_g_patch_moves_compose_end_zero():
    ir = _compose(.001, sequence_duration_s=.006, ramp_time_s=.0002)
    patched = _patch_duration(ir, .004, ramp_time_s=.0004)
    gx = next(channel for channel in patched.channels if channel.name == "gx")
    assert gx.events[0].time == .001
    assert gx.events[0].value == 20
    assert any(event.time == .005 and event.value == 0 for event in gx.events)
    assert not any(event.time == .002 and event.value == 0 for event in gx.events)
    overlay = patched.metadata["event_overlays"]["gx:0"]
    assert overlay["duration_s"] == .004
    assert patched.metadata["gradient_units"] == "mt_m"


def test_physical_g_patch_duration_changes_scheduled_gradient_moment():
    ir = _compose(.001, sequence_duration_s=.006, ramp_time_s=.0002)
    short = ir
    long = _patch_duration(ir, .004, ramp_time_s=.0004)
    assert short.duration == long.duration == .006
    m_short = _gx_moment(short)
    m_long = _gx_moment(long)
    assert m_long > m_short
    assert m_long != m_short
