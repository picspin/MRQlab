import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from mrqlab_agent.license import LeaseVerifier, TrustedClock, build_registration_request, require_entitlement
from mrqlab_agent.models import DeviceIdentity, LeaseClaims


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _token(key, claims, kid="test-key"):
    return _token_with_payload(key, json.dumps(claims, separators=(",", ":")), kid)


def _token_with_payload(key, payload_json: str, kid="test-key"):
    """Sign raw JSON too, so parser-only spellings such as ``1e999`` are tested."""
    header = _b64(json.dumps({"alg": "EdDSA", "kid": kid}, separators=(",", ":")).encode())
    payload = _b64(payload_json.encode())
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
    # A boolean bound (bool is an int subtype) and a quoted-number bound are
    # both rejected at claim parsing by the strict sub-model, so neither can
    # coerce into a numeric version window.
    claims = _claims(software={"min_version": "1.0.0", **software})
    with pytest.raises(ValidationError):
        LeaseClaims.model_validate(claims)


def test_lease_software_claim_is_required_so_an_unbounded_lease_fails_closed():
    # `software` is signed control-plane data. Omitting it must fail claim
    # validation rather than verify active with no compatibility window.
    claims = _claims()
    del claims["software"]
    with pytest.raises(ValidationError):
        LeaseClaims.model_validate(claims)


def test_lease_software_claim_must_declare_at_least_one_bound():
    # An empty window `software={}` is the same 'verifies active with no window'
    # outcome as an omitted claim, reached through an empty object; it must fail
    # closed too, not merely be documented.
    claims = _claims(software={})
    with pytest.raises(ValidationError, match="at least one"):
        LeaseClaims.model_validate(claims)


def test_lease_software_claim_rejects_unknown_signed_keys():
    # Only the keys the verifier enforces may appear; an unenforced signed key
    # must not be silently accepted.
    claims = _claims(software={"min_version": "1.0.0", "exact_version": "9.9.9"})
    with pytest.raises(ValidationError):
        LeaseClaims.model_validate(claims)


def test_lease_software_version_claim_rejects_non_ascii_digits():
    # '١' (Arabic-Indic one) satisfies str.isdigit(); a signed version claim
    # must be ASCII decimal digits or fail closed.
    private = Ed25519PrivateKey.generate()
    with pytest.raises(ValueError, match="malformed lease software claim"):
        _software_verifier(private, "1.0.0", {"min_version": "١.0.0"})


def test_limits_reject_boolean_values_for_numeric_limits():
    # bool is an int subtype; a signed `true` must not become the concurrency
    # limit 1.
    claims = _claims(limits={"max_concurrent_jobs": True})
    with pytest.raises(ValidationError, match="limits"):
        LeaseClaims.model_validate(claims)


@pytest.mark.parametrize("field", ("issued_at", "not_before", "expires_at", "offline_grace_until"))
@pytest.mark.parametrize("value", (True, False, "1000"))
def test_lease_timestamps_reject_boolean_and_coerced_values(field, value):
    # R3 applies to signed lease time boundaries too: bool is an int subtype, so
    # lax float validation would silently turn true into 1.0. Quoted numbers are
    # likewise not signed JSON numbers and must fail closed.
    with pytest.raises(ValidationError, match=field):
        LeaseClaims.model_validate(_claims(**{field: value}))


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
def test_lease_timestamps_reject_non_finite_values(value):
    # A NaN expiry defeats `now > expires_at` (always false), and infinite
    # expiries can keep a signed lease active forever. The model must reject all
    # non-finite values before verifier time-window comparisons run.
    with pytest.raises(ValidationError, match="expires_at"):
        LeaseClaims.model_validate(_claims(expires_at=value))


@pytest.mark.parametrize("raw", ("NaN", "Infinity", "-Infinity", "1e999"))
def test_signed_raw_json_non_finite_timestamp_fails_closed(raw):
    private = Ed25519PrivateKey.generate()
    device = DeviceIdentity(device_id="device-1", device_public_key_hash="pkh", fingerprint_hash="fph")
    verifier = LeaseVerifier({"test-key": private.public_key()}, device)
    payload = json.dumps(_claims(), separators=(",", ":")).replace('"expires_at":2000', f'"expires_at":{raw}')
    with pytest.raises(ValueError, match="malformed lease claims"):
        verifier.verify(_token_with_payload(private, payload), wall_time=10**10, monotonic_time=10)


@pytest.mark.parametrize(
    "updates",
    (
        {"issued_at": 1001, "not_before": 1000},
        {"not_before": 2001, "expires_at": 2000},
        {"expires_at": 2301, "offline_grace_until": 2300},
    ),
)
def test_lease_timestamps_must_form_a_chronological_window(updates):
    with pytest.raises(ValidationError, match="lease window"):
        LeaseClaims.model_validate(_claims(**updates))


def test_non_string_token_key_id_fails_closed_as_a_lease_error():
    # A JSON array/object is unhashable. It must map to a normal malformed-lease
    # denial rather than escaping the trusted-key lookup as TypeError (HTTP 500
    # at the gateway).
    private = Ed25519PrivateKey.generate()
    device = DeviceIdentity(device_id="device-1", device_public_key_hash="pkh", fingerprint_hash="fph")
    verifier = LeaseVerifier({"test-key": private.public_key()}, device)
    token = _token(private, _claims(), kid=[])
    with pytest.raises(ValueError, match="untrusted lease key id"):
        verifier.verify(token, wall_time=1500, monotonic_time=10)


def test_runtime_version_tracks_the_package_single_source_of_truth():
    # The enforced compatibility axis must not drift from the shipped package:
    # RUNTIME_VERSION derives from mrqlab_agent.__version__.
    import mrqlab_agent
    from mrqlab_agent.license import RUNTIME_VERSION

    assert RUNTIME_VERSION == mrqlab_agent.__version__


def test_expired_incompatible_lease_reports_the_time_window_not_the_software_window():
    # The time window is the validity gate; an expired lease must report
    # expiry, not a software incompatibility, so the denial reason is accurate.
    private = Ed25519PrivateKey.generate()
    device = DeviceIdentity(device_id="device-1", device_public_key_hash="pkh", fingerprint_hash="fph")
    verifier = LeaseVerifier({"test-key": private.public_key()}, device, runtime_version="1.0.0")
    claims = _claims(expires_at=2000, offline_grace_until=2300, software={"min_version": "99.0.0"})
    with pytest.raises(ValueError, match="expired beyond offline grace"):
        verifier.verify(_token(private, claims), wall_time=2400, monotonic_time=20)
