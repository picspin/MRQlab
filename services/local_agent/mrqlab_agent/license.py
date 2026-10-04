from __future__ import annotations

import base64
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from .models import DeviceIdentity, DeviceRegistrationRequest, LeaseClaims, LeaseDecision


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


class TrustedClock:
    def __init__(self, max_rollback_s: float = 300):
        self.max_rollback_s = max_rollback_s
        self._wall = None
        self._monotonic = None

    def observe(self, *, wall_time: float, monotonic_time: float) -> None:
        self._wall = wall_time
        self._monotonic = monotonic_time

    def now(self, *, wall_time: float, monotonic_time: float) -> float:
        if self._wall is None:
            self.observe(wall_time=wall_time, monotonic_time=monotonic_time)
            return wall_time
        expected = self._wall + max(0, monotonic_time - self._monotonic)
        if wall_time < expected - self.max_rollback_s:
            raise ValueError("wall clock rollback exceeds trusted-time tolerance")
        current = max(wall_time, expected)
        self.observe(wall_time=current, monotonic_time=monotonic_time)
        return current


class LeaseVerifier:
    def __init__(self, trusted_keys: dict[str, Ed25519PublicKey], device: DeviceIdentity, clock: TrustedClock | None = None):
        self.trusted_keys = dict(trusted_keys)
        self.device = device
        self.clock = clock or TrustedClock()

    def verify(self, token: str, *, wall_time: float, monotonic_time: float) -> LeaseDecision:
        try:
            encoded_header, encoded_payload, encoded_signature = token.split(".")
            header = json.loads(_decode(encoded_header))
            payload = json.loads(_decode(encoded_payload))
        except (ValueError, json.JSONDecodeError) as exc:
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
        except InvalidSignature as exc:
            raise ValueError("invalid lease signature") from exc
        claims = LeaseClaims.model_validate(payload)
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
        now = self.clock.now(wall_time=wall_time, monotonic_time=monotonic_time)
        if now < claims.not_before:
            raise ValueError("lease is not yet valid")
        if now <= claims.expires_at:
            return LeaseDecision(state="active", claims=claims)
        if now <= claims.offline_grace_until:
            return LeaseDecision(state="offline_grace", claims=claims)
        raise ValueError("lease expired beyond offline grace")


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
