"""Property-based tests for the lease software-compatibility window.

`test_license.py` pins the window with examples. This module asserts the
*invariants* the window must satisfy for **any** dotted version the schema
permits, so a regression that only shows up on an unsampled version (a large
component, a short form like "1", a many-component form) is still caught.

Hypothesis is an explicitly pinned dev dependency (see `pyproject.toml`
`[project.optional-dependencies].dev`), so clean development environments can
collect this module rather than relying on an accidental global install.
"""
import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from mrqlab_agent.license import LeaseVerifier, _version_at_least, _version_tuple
from mrqlab_agent.models import DeviceIdentity, LeaseClaims

# The ASCII dotted-numeric versions the lease schema permits (1-4 components of
# 1-4 digits). Larger digits exercise the "not a fixed-width string compare" case.
VERSION = st.from_regex(r"[0-9]{1,4}(\.[0-9]{1,4}){0,3}", fullmatch=True)

_SETTINGS = settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _token(key, claims, kid="k"):
    header = _b64(json.dumps({"alg": "EdDSA", "kid": kid}, separators=(",", ":")).encode())
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    return f"{header}.{payload}.{_b64(key.sign(f'{header}.{payload}'.encode()))}"


def _claims(**updates):
    claims = {
        "iss": "mrqlab-license", "aud": "mrqlab-local-runtime", "lease_id": "l1",
        "organization_id": "o1", "device_id": "d1", "device_public_key_hash": "pkh",
        "fingerprint_hash": "fph", "issued_at": 1000, "not_before": 1000,
        "expires_at": 2000, "offline_grace_until": 2300, "product": "pro",
        "features": ["compute.cpu"], "limits": {}, "software": {"min_version": "1.0.0"},
        "key_id": "k",
    }
    claims.update(updates)
    return claims


@_SETTINGS
@given(v=VERSION)
def test_version_comparison_is_reflexive(v):
    assert _version_at_least(v, v)


@_SETTINGS
@given(a=VERSION, b=VERSION)
def test_version_comparison_is_total(a, b):
    # No incomparable pair: one version is always >= the other.
    assert _version_at_least(a, b) or _version_at_least(b, a)


@_SETTINGS
@given(a=VERSION, b=VERSION, c=VERSION)
def test_version_comparison_is_transitive(a, b, c):
    if _version_at_least(a, b) and _version_at_least(b, c):
        assert _version_at_least(a, c)


@_SETTINGS
@given(v=VERSION)
def test_missing_components_compare_as_zero(v):
    # Padding with a trailing .0 must not move the ordering in either direction.
    assert _version_at_least(v + ".0", v)
    assert _version_at_least(v, v + ".0")


@_SETTINGS
@given(v=VERSION)
def test_parsing_matches_python_int_and_non_ascii_fails(v):
    assert _version_tuple(v) == tuple(int(part) for part in v.split("."))
    # A non-ASCII decimal digit (Arabic-Indic one) must fail closed, not parse.
    with pytest.raises(ValueError, match="malformed software version claim"):
        _version_tuple("١" + v)


@_SETTINGS
@given(runtime=VERSION, minimum=VERSION)
def test_enforcement_matches_the_reference_relation(runtime, minimum):
    """A lease whose window names `minimum` is accepted iff runtime >= minimum.

    This ties the *decision* to the same relation the invariant tests pin, so the
    enforcement path cannot drift from the comparison it claims to implement.
    """
    private = Ed25519PrivateKey.generate()
    device = DeviceIdentity(device_id="d1", device_public_key_hash="pkh", fingerprint_hash="fph")
    verifier = LeaseVerifier({"k": private.public_key()}, device, runtime_version=runtime)
    token = _token(private, _claims(software={"min_version": minimum}))
    if _version_at_least(runtime, minimum):
        assert verifier.verify(token, wall_time=1500, monotonic_time=10).state == "active"
    else:
        with pytest.raises(ValueError, match="older than the lease minimum"):
            verifier.verify(token, wall_time=1500, monotonic_time=10)


@_SETTINGS
@given(runtime=VERSION, cap=st.integers(min_value=0, max_value=9999))
def test_major_cap_matches_the_first_component(runtime, cap):
    """A `max_major` cap is exceeded iff the runtime's major component exceeds it."""
    private = Ed25519PrivateKey.generate()
    device = DeviceIdentity(device_id="d1", device_public_key_hash="pkh", fingerprint_hash="fph")
    verifier = LeaseVerifier({"k": private.public_key()}, device, runtime_version=runtime)
    token = _token(private, _claims(software={"max_major": cap}))
    major = _version_tuple(runtime)[0]
    if major > cap:
        with pytest.raises(ValueError, match="exceeds the lease maximum"):
            verifier.verify(token, wall_time=1500, monotonic_time=10)
    else:
        assert verifier.verify(token, wall_time=1500, monotonic_time=10).state == "active"
