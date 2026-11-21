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


def _software_verifier(private, runtime_version, software):
    device = DeviceIdentity(device_id="device-1", device_public_key_hash="pkh", fingerprint_hash="fph")
    verifier = LeaseVerifier({"test-key": private.public_key()}, device, runtime_version=runtime_version)
    return verifier.verify(_token(private, _claims(software=software)), wall_time=1500, monotonic_time=10)


def test_lease_software_claim_is_enforced_not_advisory():
    private = Ed25519PrivateKey.generate()
    # A runtime older than the issuer's minimum must fail closed; the same
    # signed lease is accepted once the runtime meets the minimum.
    with pytest.raises(ValueError, match="older than the lease minimum"):
        _software_verifier(private, "1.0.0", {"min_version": "2.0.0", "max_major": 3})
    decision = _software_verifier(private, "2.4.0", {"min_version": "2.0.0", "max_major": 3})
    assert decision.state == "active"


def test_lease_software_claim_accepts_the_minimum_boundary_exactly():
    private = Ed25519PrivateKey.generate()
    # Equality at the minimum is inside the window, and a shorter minimum such
    # as "1.0" must compare equal to runtime "1.0.0", not older.
    assert _software_verifier(private, "2.0.0", {"min_version": "2.0.0"}).state == "active"
    assert _software_verifier(private, "1.0.0", {"min_version": "1.0"}).state == "active"


def test_lease_software_claim_rejects_a_runtime_major_above_the_cap():
    private = Ed25519PrivateKey.generate()
    with pytest.raises(ValueError, match="exceeds the lease maximum"):
        _software_verifier(private, "3.0.0", {"min_version": "1.0.0", "max_major": 2})
    # The cap boundary itself is allowed.
    assert _software_verifier(private, "2.9.9", {"min_version": "1.0.0", "max_major": 2}).state == "active"


@pytest.mark.parametrize(
    "software",
    [
        {"min_version": "1.x.0"},
        {"min_version": ""},
    ],
)
def test_lease_software_claim_fails_closed_on_malformed_values(software):
    private = Ed25519PrivateKey.generate()
    with pytest.raises(ValueError, match="malformed lease software claim"):
        _software_verifier(private, "1.0.0", software)


@pytest.mark.parametrize("software", [{"max_major": True}, {"max_major": "2"}])
def test_lease_software_claim_rejects_non_strict_version_bounds(software):
    # A boolean or string bound must be rejected at claim parsing rather than
    # coercing (bool is an int subtype) into a numeric version window.
    private = Ed25519PrivateKey.generate()
    with pytest.raises(ValueError):
        _software_verifier(private, "1.0.0", {"min_version": "1.0.0", **software})


def test_lease_software_claim_absent_leaves_the_runtime_unconstrained():
    private = Ed25519PrivateKey.generate()
    device = DeviceIdentity(device_id="device-1", device_public_key_hash="pkh", fingerprint_hash="fph")
    verifier = LeaseVerifier({"test-key": private.public_key()}, device, runtime_version="1.0.0")
    claims = _claims()
    del claims["software"]
    # Backwards compatibility: a lease with no software claim stays valid, as
    # the existing entitlement/expiry tests rely on.
    assert verifier.verify(_token(private, claims), wall_time=1500, monotonic_time=10).state == "active"
    # A permissive window is likewise accepted.
    assert _software_verifier(private, "1.0.0", {"min_version": "0.1", "max_major": 9}).state == "active"
