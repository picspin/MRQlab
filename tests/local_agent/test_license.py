import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from mrqlab_agent.license import LeaseVerifier, TrustedClock, build_registration_request, require_entitlement
from mrqlab_agent.models import DeviceIdentity


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _token(key, claims, kid="test-key"):
    header = _b64(json.dumps({"alg": "EdDSA", "kid": kid}, separators=(",", ":")).encode())
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = _b64(key.sign(f"{header}.{payload}".encode()))
    return f"{header}.{payload}.{signature}"


def _claims(**updates):
    claims = {
        "iss": "mrqlab-license", "aud": "mrqlab-local-runtime", "lease_id": "lease-1",
        "organization_id": "org-1", "device_id": "device-1", "device_public_key_hash": "pkh",
        "fingerprint_hash": "fph", "issued_at": 1000, "not_before": 1000,
        "expires_at": 2000, "offline_grace_until": 2300, "product": "mrqlab-pro",
        "features": ["compute.cpu", "jobs.cancel"], "limits": {"max_concurrent_jobs": 2},
        "software": {"min_version": "1.0.0", "max_major": 1}, "key_id": "test-key",
    }
    claims.update(updates)
    return claims


def test_valid_device_lease_and_entitlement():
    private = Ed25519PrivateKey.generate()
    device = DeviceIdentity(device_id="device-1", device_public_key_hash="pkh", fingerprint_hash="fph")
    verifier = LeaseVerifier({"test-key": private.public_key()}, device)
    decision = verifier.verify(_token(private, _claims()), wall_time=1500, monotonic_time=10)
    assert decision.state == "active"
    require_entitlement(decision, "compute.cpu")


def test_wrong_device_expired_and_unentitled_fail_closed():
    private = Ed25519PrivateKey.generate()
    device = DeviceIdentity(device_id="device-1", device_public_key_hash="pkh", fingerprint_hash="fph")
    verifier = LeaseVerifier({"test-key": private.public_key()}, device)
    with pytest.raises(ValueError, match="wrong device"):
        verifier.verify(_token(private, _claims(device_id="device-2")), wall_time=1500, monotonic_time=10)
    with pytest.raises(ValueError, match="expired beyond offline grace"):
        verifier.verify(_token(private, _claims()), wall_time=2400, monotonic_time=20)
    # Use a fresh verifier so monotonic anchor isn't pegged to expired 2400
    verifier_grace = LeaseVerifier({"test-key": private.public_key()}, device)
    decision = verifier_grace.verify(_token(private, _claims()), wall_time=2100, monotonic_time=20)
    assert decision.state == "offline_grace"
    with pytest.raises(PermissionError, match="gpu"):
        require_entitlement(decision, "compute.gpu")


def test_trusted_clock_detects_material_wall_clock_rollback():
    clock = TrustedClock(max_rollback_s=5)
    clock.observe(wall_time=1500, monotonic_time=10)
    with pytest.raises(ValueError, match="clock rollback"):
        clock.now(wall_time=1400, monotonic_time=20)


def test_device_registration_exports_public_material_and_canonical_fingerprint_only():
    private = Ed25519PrivateKey.generate()
    request = build_registration_request(
        "device-1", private.public_key(), {"machine_id": "m1", "gpu_uuid": "g1"}
    )
    assert request.device_id == "device-1"
    assert request.device_public_key_b64
    assert request.fingerprint_hash
    assert "private" not in request.model_dump_json().lower()
