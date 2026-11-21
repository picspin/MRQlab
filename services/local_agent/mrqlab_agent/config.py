"""Environment-driven lease configuration for the local gateway.

The shipped agent has no baked-in keys or device identity: a deployment supplies
them through the environment, and an unconfigured or partially configured process
stays *unconfigured* rather than open. ``load_lease_verifier`` is the single
place that turns those variables into a ``LeaseVerifier``; it never fabricates a
trusted key or a device identity, so a missing value fails closed.
"""
from __future__ import annotations

import base64
import json
import os
from collections.abc import Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .license import LeaseVerifier
from .models import DeviceIdentity

TRUSTED_KEYS_ENV = "MRQLAB_LEASE_TRUSTED_KEYS"
DEVICE_ID_ENV = "MRQLAB_DEVICE_ID"
DEVICE_PUBLIC_KEY_HASH_ENV = "MRQLAB_DEVICE_PUBLIC_KEY_HASH"
FINGERPRINT_HASH_ENV = "MRQLAB_FINGERPRINT_HASH"

_REQUIRED = (TRUSTED_KEYS_ENV, DEVICE_ID_ENV, DEVICE_PUBLIC_KEY_HASH_ENV, FINGERPRINT_HASH_ENV)


def _decode_public_key(value: str) -> Ed25519PublicKey:
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        return Ed25519PublicKey.from_public_bytes(raw)
    except Exception as exc:
        raise ValueError("invalid Ed25519 public key in lease configuration") from exc


def load_lease_verifier(environment: Mapping[str, str] | None = None) -> LeaseVerifier | None:
    """Build a lease verifier from the environment, or ``None`` if unconfigured.

    Returns ``None`` only when *no* lease variable is set, which keeps the
    gateway's existing 503 behaviour for an unprovisioned local process. A
    partial or malformed configuration raises ``ValueError`` instead of silently
    falling back to the unconfigured state, so a deployment that intended to
    enforce leases cannot run open by accident.
    """
    env = os.environ if environment is None else environment
    present = [name for name in _REQUIRED if env.get(name)]
    if not present:
        return None
    missing = [name for name in _REQUIRED if not env.get(name)]
    if missing:
        raise ValueError(f"incomplete lease configuration: missing {', '.join(missing)}")
    try:
        keys = json.loads(env[TRUSTED_KEYS_ENV])
    except json.JSONDecodeError as exc:
        raise ValueError("trusted lease keys must be a JSON object") from exc
    if not isinstance(keys, dict) or not keys:
        raise ValueError("trusted lease keys must be a non-empty JSON object")
    trusted = {kid: _decode_public_key(value) for kid, value in keys.items()}
    device = DeviceIdentity(
        device_id=env[DEVICE_ID_ENV],
        device_public_key_hash=env[DEVICE_PUBLIC_KEY_HASH_ENV],
        fingerprint_hash=env[FINGERPRINT_HASH_ENV],
    )
    return LeaseVerifier(trusted, device)
