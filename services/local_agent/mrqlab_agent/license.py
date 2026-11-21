from __future__ import annotations

import base64
import hashlib
import json
from threading import RLock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from .models import DeviceIdentity, DeviceRegistrationRequest, LeaseClaims, LeaseDecision
from . import __version__

# Lease-compatibility version of the local runtime, distinct from the product
# version. It is derived from the package's single ``__version__`` source so the
# enforced window cannot drift from the shipped runtime; a signed lease may
# constrain the runtime it is valid against via its `software` claim, checked
# here so a lease issued for an incompatible runtime fails closed.
RUNTIME_VERSION = __version__


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _version_tuple(value) -> tuple[int, ...]:
    """Parse a dotted ASCII-numeric version ("1", "1.0", "1.0.0") or fail closed.

    ``str.isdigit`` also accepts non-ASCII decimal digits (for example '١'), so
    an explicit ASCII check is used; otherwise a signed claim could name a
    version the runtime never compares against in ASCII terms.
    """
    if not isinstance(value, str) or not value:
        raise ValueError("malformed software version claim")
    parts = value.split(".")
    if any(not part.isascii() or not part.isdigit() for part in parts):
        raise ValueError("malformed software version claim")
    return tuple(int(part) for part in parts)


def _version_at_least(candidate: str, minimum: str) -> bool:
    """True when `candidate` is >= `minimum`, comparing missing components as 0."""
    left, right = _version_tuple(candidate), _version_tuple(minimum)
    width = max(len(left), len(right))
    left += (0,) * (width - len(left))
    right += (0,) * (width - len(right))
    return left >= right


class TrustedClock:
    def __init__(self, max_rollback_s: float = 300):
        self.max_rollback_s = max_rollback_s
        self._lock = RLock()
        self._wall = None
        self._monotonic = None

    def observe(self, *, wall_time: float, monotonic_time: float) -> None:
        with self._lock:
            self._wall = wall_time
            self._monotonic = monotonic_time

    def now(self, *, wall_time: float, monotonic_time: float) -> float:
        with self._lock:
            if self._wall is None:
                self._wall = wall_time
                self._monotonic = monotonic_time
                return wall_time
            expected = self._wall + max(0, monotonic_time - self._monotonic)
            if wall_time < expected - self.max_rollback_s:
                raise ValueError("wall clock rollback exceeds trusted-time tolerance")
            current = max(wall_time, expected)
            self._wall = current
            self._monotonic = monotonic_time
            return current


class LeaseVerifier:
    def __init__(self, trusted_keys: dict[str, Ed25519PublicKey], device: DeviceIdentity, clock: TrustedClock | None = None,
                 runtime_version: str = RUNTIME_VERSION):
        self.trusted_keys = dict(trusted_keys)
        self.device = device
        self.clock = clock or TrustedClock()
        self.runtime_version = runtime_version

    def verify(self, token: str, *, wall_time: float, monotonic_time: float) -> LeaseDecision:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("malformed lease token")
            encoded_header, encoded_payload, encoded_signature = parts
            header = json.loads(_decode(encoded_header))
            payload = json.loads(_decode(encoded_payload))
            if not isinstance(header, dict) or not isinstance(payload, dict):
                raise ValueError("malformed lease token payload")
        except Exception as exc:
            raise ValueError("malformed lease token") from exc
        if header.get("alg") != "EdDSA":
            raise ValueError("lease algorithm must be EdDSA")
        kid = header.get("kid")
        try:
            key = self.trusted_keys[kid]
        except KeyError:
            raise ValueError(f"untrusted lease key id {kid!r}") from None
        try:
            key.verify(_decode(encoded_signature), f"{encoded_header}.{encoded_payload}".encode())
        except Exception as exc:
            raise ValueError("invalid lease signature") from exc
        try:
            claims = LeaseClaims.model_validate(payload)
        except Exception as exc:
            raise ValueError("malformed lease claims") from exc
        if claims.key_id != kid:
            raise ValueError("lease key id mismatch")
        if claims.iss != "mrqlab-license" or claims.aud != "mrqlab-local-runtime":
            raise ValueError("lease issuer or audience mismatch")
        if claims.device_id != self.device.device_id:
            raise ValueError("lease is bound to the wrong device")
        if claims.device_public_key_hash != self.device.device_public_key_hash:
            raise ValueError("lease public-key binding does not match this device")
        if claims.fingerprint_hash != self.device.fingerprint_hash:
            raise ValueError("lease hardware fingerprint does not match this device")
        # The time window is the validity gate, so evaluate it before the
        # compatibility window: an expired lease must report expiry, not a
        # software mismatch, so the denial reason names the actual cause.
        now = self.clock.now(wall_time=wall_time, monotonic_time=monotonic_time)
        if now < claims.not_before:
            raise ValueError("lease is not yet valid")
        if now > claims.expires_at:
            if now > claims.offline_grace_until:
                raise ValueError("lease expired beyond offline grace")
            self._verify_software_compatibility(claims)
            return LeaseDecision(state="offline_grace", claims=claims)
        self._verify_software_compatibility(claims)
        return LeaseDecision(state="active", claims=claims)

    def _verify_software_compatibility(self, claims: LeaseClaims) -> None:
        """Enforce the lease's declared runtime-compatibility window.

        The signed `software` claim is part of the lease contract, not advice:
        `min_version` is the oldest runtime the issuer will run against and
        `max_major` caps the runtime major version. A runtime outside that
        window fails closed rather than executing under an unknown build.
        """
        software = claims.software
        if software.min_version is not None:
            try:
                too_old = not _version_at_least(self.runtime_version, software.min_version)
            except ValueError as exc:
                raise ValueError("malformed lease software claim") from exc
            if too_old:
                raise ValueError(
                    f"local runtime {self.runtime_version} is older than the lease minimum {software.min_version}"
                )
        if software.max_major is not None:
            try:
                runtime_major = _version_tuple(self.runtime_version)[0]
            except ValueError as exc:
                raise ValueError("malformed local runtime version") from exc
            if runtime_major > software.max_major:
                raise ValueError(
                    f"local runtime major {runtime_major} exceeds the lease maximum {software.max_major}"
                )


def require_entitlement(decision: LeaseDecision, feature: str) -> None:
    if feature not in decision.claims.features:
        raise PermissionError(f"lease does not entitle feature {feature!r}")


def build_registration_request(
    device_id: str,
    public_key: Ed25519PublicKey,
    fingerprint_components: dict[str, str],
) -> DeviceRegistrationRequest:
    if not fingerprint_components or any(not key or not value for key, value in fingerprint_components.items()):
        raise ValueError("device fingerprint components must be non-empty")
    public_bytes = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    canonical = json.dumps(fingerprint_components, sort_keys=True, separators=(",", ":")).encode()
    return DeviceRegistrationRequest(
        device_id=device_id,
        device_public_key_b64=base64.urlsafe_b64encode(public_bytes).rstrip(b"=").decode(),
        device_public_key_hash=hashlib.sha256(public_bytes).hexdigest(),
        fingerprint_hash=hashlib.sha256(canonical).hexdigest(),
    )
