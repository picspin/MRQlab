#!/usr/bin/env python3
"""Shadow walk-through of the lease gate.

An in-process end-to-end shadow of the change: boot the real gateway and assert
the *observable* HTTP behaviour against an independently stated expectation
matrix, rather than trusting unit tests that share helpers with the code. The
valid-lease cell deliberately submits one real CPU job, so it writes a job record
and, when its worker runs, an artifact **to the process-local in-memory store**;
that state dies with this process. No server process is left running and no
filesystem or external service is written.

Expectation matrix (the contract the change claims):

  gate configured + valid signed lease      -> POST /jobs 202 (reaches work)
  gate configured + missing/malformed/forged-> POST /jobs 401
  gate unconfigured                         -> POST /jobs 503
  reads (loopback+pairing+CSRF)             -> 200 regardless of gate state

Exit code 0 iff every cell matches.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for rel in ("packages/sequence-ir", "packages/physics", "packages/recon",
            "packages/mrqlab_experiment", "services/api", "services/local_agent"):
    sys.path.insert(0, str(ROOT / rel))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from mrqlab_agent import main as agent_main  # noqa: E402
from mrqlab_agent.config import load_lease_verifier  # noqa: E402
from mrqlab_agent.main import app, local_security  # noqa: E402
from mrqlab_experiment import build_protocol_experiment  # noqa: E402

HEADERS = {
    "origin": "https://app.mrqlab.local",
    "x-mrqlab-pairing": local_security.pairing_secret,
    "x-mrqlab-csrf": local_security.csrf_token,
}


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _token(key, claims, kid="k1"):
    header = _b64(json.dumps({"alg": "EdDSA", "kid": kid}, separators=(",", ":")).encode())
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    return f"{header}.{payload}.{_b64(key.sign(f'{header}.{payload}'.encode()))}"


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


def _environment(key, kid="k1"):
    return {
        "MRQLAB_LEASE_TRUSTED_KEYS": json.dumps({kid: _b64(key.public_key().public_bytes_raw())}),
        "MRQLAB_DEVICE_ID": "d1",
        "MRQLAB_DEVICE_PUBLIC_KEY_HASH": "pkh",
        "MRQLAB_FINGERPRINT_HASH": "fph",
    }


def main() -> int:
    key = Ed25519PrivateKey.generate()
    other = Ed25519PrivateKey.generate()
    graph = build_protocol_experiment("brain_lesion_t2_tse")
    body = {"provider_id": "local_cpu_numpy", "experiment": graph.model_dump(mode="json")}
    client = TestClient(app)
    rows: list[tuple[str, int, int]] = []

    def post_jobs(headers, decision=None):
        prev = agent_main.lease_verifier
        try:
            agent_main.lease_verifier = decision
            return client.post("/jobs", json=body, headers=headers)
        finally:
            agent_main.lease_verifier = prev

    # Configured gate: valid lease reaches work (202), bad tokens are 401.
    configured = load_lease_verifier(_environment(key))
    rows.append(("configured + valid lease", post_jobs({**HEADERS, "authorization": f"Lease {_token(key, _claims())}"}, configured).status_code, 202))
    rows.append(("configured + missing lease", post_jobs(HEADERS, configured).status_code, 401))
    rows.append(("configured + malformed lease", post_jobs({**HEADERS, "authorization": "Lease nonsense"}, configured).status_code, 401))
    rows.append(("configured + forged lease", post_jobs({**HEADERS, "authorization": f"Lease {_token(other, _claims())}"}, configured).status_code, 401))
    # Unconfigured gate: fail closed with 503.
    rows.append(("unconfigured + valid lease", post_jobs({**HEADERS, "authorization": f"Lease {_token(key, _claims())}"}, None).status_code, 503))
    # Reads are not lease-gated: 200 whether configured or not.
    prev = agent_main.lease_verifier
    try:
        agent_main.lease_verifier = None
        rows.append(("unconfigured read /v1/capabilities", client.get("/v1/capabilities", headers=HEADERS).status_code, 200))
        agent_main.lease_verifier = configured
        rows.append(("configured read /v1/capabilities", client.get("/v1/capabilities", headers=HEADERS).status_code, 200))
    finally:
        agent_main.lease_verifier = prev

    ok = True
    print(f"{'cell':<38} {'got':>4} {'want':>5}  result")
    for name, got, want in rows:
        good = got == want
        ok = ok and good
        print(f"{name:<38} {got:>4} {want:>5}  {'PASS' if good else 'FAIL'}")
    print("\nshadow walk-through:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
