from fastapi.testclient import TestClient

from mrqlab_api.main import app
from mrqlab_experiment.compare import CompareRequest, ProtocolSpec, compute_compare, evaluate_protocol

client = TestClient(app)


def test_higher_fa_increases_relative_sar():
    lo = evaluate_protocol(ProtocolSpec(flip_angle_deg=120.0, te_eff_ms=100.0, b0_t=3.0))
    hi = evaluate_protocol(ProtocolSpec(flip_angle_deg=180.0, te_eff_ms=100.0, b0_t=3.0))
    assert hi.relative_sar > lo.relative_sar


def test_higher_b0_increases_cnr_and_sar():
    at_15 = evaluate_protocol(ProtocolSpec(flip_angle_deg=150.0, te_eff_ms=100.0, b0_t=1.5))
    at_30 = evaluate_protocol(ProtocolSpec(flip_angle_deg=150.0, te_eff_ms=100.0, b0_t=3.0))
    assert at_30.cnr_proxy > at_15.cnr_proxy
    assert at_30.relative_sar > at_15.relative_sar


def test_echo_train_length_and_monotonic_decay():
    proto = evaluate_protocol(ProtocolSpec(echo_train_length=16, echo_spacing_ms=12.5))
    assert len(proto.echo_train) == 16
    assert proto.echo_train[0] > proto.echo_train[-1]


def test_compare_delta_signs_when_b_is_cooler_lower_fa():
    analysis = compute_compare(
        CompareRequest(
            protocol_a=ProtocolSpec(id="A", name="Hot", flip_angle_deg=180.0, te_eff_ms=100.0),
            protocol_b=ProtocolSpec(id="B", name="Cool", flip_angle_deg=120.0, te_eff_ms=100.0),
        )
    )
    assert analysis.delta.sar_delta < 0


def test_compare_endpoint():
    res = client.post(
        "/compare/protocols",
        json={
            "protocol_a": {"id": "A", "name": "A", "flip_angle_deg": 150, "te_eff_ms": 100, "b0_t": 3.0},
            "protocol_b": {"id": "B", "name": "B", "flip_angle_deg": 120, "te_eff_ms": 80, "b0_t": 3.0},
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "protocol_a" in body and "protocol_b" in body and "delta" in body
    assert len(body["protocol_a"]["echo_train"]) == 16
    assert body["protocol_a"]["flip_angle_deg"] == 150
    assert body["protocol_b"]["flip_angle_deg"] == 120
