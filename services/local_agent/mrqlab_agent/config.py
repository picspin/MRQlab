"""Environment-driven lease configuration for the local gateway.

The shipped agent has no baked-in keys or device identity: a deployment supplies
them through the environment. ``load_lease_verifier`` is the strict single place
that turns those variables into a ``LeaseVerifier`` and raises on a partial or
malformed configuration; ``configure_lease_verifier`` is the boot-time wrapper
the gateway uses, which never raises — it logs loudly and leaves the gate
unconfigured, so a misprovisioned box still starts.
"""
from __future__ import annotations

import base64
import json
import logging
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

logger = logging.getLogger(__name__)


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


def configure_lease_verifier(environment: Mapping[str, str] | None = None) -> LeaseVerifier | None:
    """Boot-time wrapper: never raise, leave the gate unconfigured and log loudly.

    A misprovisioned deployment must still start; the lease-protected routes then
    answer 503 (unchanged) rather than the process dying at import. Every
    unconfigured path — no variables at all, or a partial/malformed set — logs a
    warning naming the exact problem, so the operator can see why the gate is off.
    """
    env = os.environ if environment is None else environment
    try:
        verifier = load_lease_verifier(env)
    except ValueError as exc:
        logger.warning(
            "lease gate unconfigured: %s; lease-protected routes will answer 503 "
            "until %s are set correctly",
            exc,
            ", ".join(_REQUIRED),
        )
        return None
    if verifier is None:
        logger.warning(
            "lease gate unconfigured: none of %s is set; lease-protected routes "
            "will answer 503",
            ", ".join(_REQUIRED),
        )
    return verifier
