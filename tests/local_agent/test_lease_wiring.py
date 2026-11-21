import base64
import json
import logging
import os
import subprocess
import sys

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from mrqlab_agent import main as agent_main
from mrqlab_agent.config import (
    DEVICE_ID_ENV,
    DEVICE_PUBLIC_KEY_HASH_ENV,
    FINGERPRINT_HASH_ENV,
    TRUSTED_KEYS_ENV,
    configure_lease_verifier,
    load_lease_verifier,
)
from mrqlab_agent.license import LeaseVerifier
from mrqlab_agent.main import app, local_security
from mrqlab_experiment import build_protocol_experiment


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _token(key, claims, kid="k1"):
    header = _b64(json.dumps({"alg": "EdDSA", "kid": kid}, separators=(",", ":")).encode())
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = _b64(key.sign(f"{header}.{payload}".encode()))
    return f"{header}.{payload}.{signature}"


def _claims(**updates):
    claims = {
        "iss": "mrqlab-license", "aud": "mrqlab-local-runtime", "lease_id": "l1",
        "organization_id": "o1", "device_id": "d1", "device_public_key_hash": "pkh",
        "fingerprint_hash": "fph", "issued_at": 0, "not_before": 0,
        "expires_at": 4102444800, "offline_grace_until": 4102444800, "product": "pro",
        "features": ["compute.cpu", "jobs.cancel"], "limits": {},
        "software": {"min_version": "1.0.0"}, "key_id": "k1",
    }
    claims.update(updates)
    return claims


def _environment(key, *, kid="k1", **updates):
    env = {
        TRUSTED_KEYS_ENV: json.dumps({kid: _b64(key.public_key().public_bytes_raw())}),
        DEVICE_ID_ENV: "d1",
        DEVICE_PUBLIC_KEY_HASH_ENV: "pkh",
        FINGERPRINT_HASH_ENV: "fph",
    }
    env.update(updates)
    return env


HEADERS = {
    "origin": "https://app.mrqlab.local",
    "x-mrqlab-pairing": local_security.pairing_secret,
    "x-mrqlab-csrf": local_security.csrf_token,
}


def test_unconfigured_environment_yields_no_verifier():
    # No lease setting at all: the gateway stays unconfigured (503), never open.
    assert load_lease_verifier({}) is None


def test_partial_configuration_raises_from_the_strict_loader():
    # The strict loader stays strict so the misconfiguration is testable and
    # cannot pass silently; the gateway wrapper (below) is what swallows it.
    key = Ed25519PrivateKey.generate()
    env = _environment(key)
    del env[FINGERPRINT_HASH_ENV]
    with pytest.raises(ValueError, match="incomplete lease configuration"):
        load_lease_verifier(env)


def test_configure_wrapper_starts_unconfigured_with_a_loud_log_on_partial_config(caplog):
    # The gateway must boot, not raise: a partial config yields no verifier and
    # logs the unconfigured state at WARNING so the operator can see it.
    key = Ed25519PrivateKey.generate()
    env = _environment(key)
    del env[FINGERPRINT_HASH_ENV]
    with caplog.at_level(logging.WARNING, logger="mrqlab_agent.config"):
        assert configure_lease_verifier(env) is None
    assert any("unconfigured" in record.message.lower() for record in caplog.records)
    assert any(record.levelno >= logging.WARNING for record in caplog.records)


def test_configure_wrapper_is_quiet_when_fully_configured(caplog):
    key = Ed25519PrivateKey.generate()
    with caplog.at_level(logging.WARNING, logger="mrqlab_agent.config"):
        verifier = configure_lease_verifier(_environment(key))
    assert isinstance(verifier, LeaseVerifier)
    assert not caplog.records


def test_configure_wrapper_never_raises_on_a_non_string_value(caplog):
    # A caller-supplied Mapping that violates the type hint (a non-str key blob)
    # makes json.loads raise TypeError; the boot wrapper must still not raise.
    env = {
        TRUSTED_KEYS_ENV: 5,
        DEVICE_ID_ENV: "d1",
        DEVICE_PUBLIC_KEY_HASH_ENV: "pkh",
        FINGERPRINT_HASH_ENV: "fph",
    }
    with caplog.at_level(logging.WARNING, logger="mrqlab_agent.config"):
        assert configure_lease_verifier(env) is None
    assert any("unconfigured" in record.message.lower() for record in caplog.records)


def test_configure_wrapper_logs_when_no_lease_variables_are_set(caplog):
    with caplog.at_level(logging.WARNING, logger="mrqlab_agent.config"):
        assert configure_lease_verifier({}) is None
    assert any("unconfigured" in record.message.lower() for record in caplog.records)


def test_partial_configuration_still_blocks_lease_routes_without_crashing(monkeypatch):
    # Starting unconfigured is fail-closed for requests: the lease-protected
    # route still returns 503 rather than running open.
    monkeypatch.setattr(agent_main, "lease_verifier", None)
    client = TestClient(app)
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    response = client.post(
        "/jobs",
        json={"provider_id": "local_cpu_numpy", "experiment": graph.model_dump(mode="json")},
        headers=HEADERS,
    )
    assert response.status_code == 503


def test_malformed_trusted_keys_fail_closed():
    key = Ed25519PrivateKey.generate()
    env = _environment(key, **{TRUSTED_KEYS_ENV: "not json"})
    with pytest.raises(ValueError, match="JSON object"):
        load_lease_verifier(env)
    env = _environment(key, **{TRUSTED_KEYS_ENV: json.dumps({"k1": "AAAA"})})
    with pytest.raises(ValueError, match="invalid Ed25519 public key"):
        load_lease_verifier(env)


def test_configured_verifier_accepts_a_lease_bound_to_its_device():
    key = Ed25519PrivateKey.generate()
    verifier = load_lease_verifier(_environment(key))
    assert isinstance(verifier, LeaseVerifier)
    decision = verifier.verify(_token(key, _claims()), wall_time=1500, monotonic_time=10)
    assert decision.state == "active"
    # An unknown key id is untrusted; a trusted kid with a bad signature fails
    # signature verification. Both reject.
    other = Ed25519PrivateKey.generate()
    with pytest.raises(ValueError, match="untrusted lease key id"):
        verifier.verify(_token(other, _claims(), kid="unknown"), wall_time=1500, monotonic_time=10)
    with pytest.raises(ValueError, match="invalid lease signature"):
        verifier.verify(_token(other, _claims()), wall_time=1500, monotonic_time=10)
    # A lease bound to a different device is rejected by the wired identity.
    with pytest.raises(ValueError, match="wrong device"):
        verifier.verify(_token(key, _claims(device_id="other")), wall_time=1500, monotonic_time=10)


def test_unconfigured_gateway_returns_503_for_lease_protected_routes(monkeypatch):
    monkeypatch.setattr(agent_main, "lease_verifier", None)
    client = TestClient(app)
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    response = client.post(
        "/jobs",
        json={"provider_id": "local_cpu_numpy", "experiment": graph.model_dump(mode="json")},
        headers=HEADERS,
    )
    assert response.status_code == 503


def test_read_routes_are_not_lease_gated_and_report_unconfigured(monkeypatch):
    # Only job submission/cancel are lease-gated. Reads stay available on
    # loopback+pairing, and the capability view reports the gate state so an
    # operator can see the lease is unconfigured.
    monkeypatch.setattr(agent_main, "lease_verifier", None)
    client = TestClient(app)
    response = client.get("/v1/capabilities", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["license"]["state"] == "unconfigured"


def test_configured_gateway_accepts_a_signed_lease_and_rejects_bad_tokens(monkeypatch):
    key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(agent_main, "lease_verifier", load_lease_verifier(_environment(key)))
    client = TestClient(app)
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    body = {"provider_id": "local_cpu_numpy", "experiment": graph.model_dump(mode="json")}

    # A valid signed lease reaches the job endpoint (no 503, no 401).
    accepted = client.post(
        "/jobs", json=body, headers={**HEADERS, "authorization": f"Lease {_token(key, _claims())}"}
    )
    assert accepted.status_code == 202

    # A missing, malformed, or untrusted lease is rejected, not 503.
    assert client.post("/jobs", json=body, headers=HEADERS).status_code == 401
    assert client.post("/jobs", json=body, headers={**HEADERS, "authorization": "Lease nonsense"}).status_code == 401
    other = Ed25519PrivateKey.generate()
    forged = client.post(
        "/jobs", json=body, headers={**HEADERS, "authorization": f"Lease {_token(other, _claims())}"}
    )
    assert forged.status_code == 401


def _child_env(**updates):
    """A subprocess environment that resolves this worktree's packages.

    The venv's editable finder points ``mrqlab_agent`` at the main checkout, so
    the child must be handed this process's own ``sys.path`` explicitly; pytest's
    ``pythonpath`` ini edits only the parent and does not export the variable.
    """
    return {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path), **updates}


def test_app_wires_the_verifier_from_the_process_environment():
    # The shipped app must construct its verifier from the environment at import,
    # so a provisioned deployment enforces the lease without code changes.
    key = Ed25519PrivateKey.generate()
    script = (
        "import json, mrqlab_agent.main as m; "
        "print(json.dumps({'configured': m.lease_verifier is not None}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], env=_child_env(**_environment(key)),
        capture_output=True, text=True, check=True,
    )
    assert json.loads(result.stdout.strip()) == {"configured": True}
    # With no lease setting the app imports cleanly and stays unconfigured.
    clean = {k: v for k, v in os.environ.items() if k not in {
        TRUSTED_KEYS_ENV, DEVICE_ID_ENV, DEVICE_PUBLIC_KEY_HASH_ENV, FINGERPRINT_HASH_ENV,
    }}
    result = subprocess.run(
        [sys.executable, "-c", script], env=_child_env(**clean),
        capture_output=True, text=True, check=True,
    )
    assert json.loads(result.stdout.strip()) == {"configured": False}


def test_app_boots_unconfigured_under_a_partial_config_instead_of_crashing():
    # A partially provisioned box must start (exit 0) with the gate unconfigured
    # and a loud warning, not die at import.
    key = Ed25519PrivateKey.generate()
    script = (
        "import json, mrqlab_agent.main as m; "
        "print(json.dumps({'configured': m.lease_verifier is not None}))"
    )
    env = _child_env(**_environment(key))
    del env[FINGERPRINT_HASH_ENV]
    result = subprocess.run(
        [sys.executable, "-c", script], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) == {"configured": False}
    assert "unconfigured" in result.stderr.lower()
