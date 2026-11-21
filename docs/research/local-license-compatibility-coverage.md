# Local license: enforced runtime-compatibility window

Parent anchor `ec3355f`. Research/teaching only; no scanner validation, clinical
quality certification, hardware/export path or scanner-ready claim. This stage
advances Milestone C (Licensed Local Compute) and does not unlock Milestone B.

## What was missing

The Ed25519-signed device lease already carried a `software` claim
(`{"min_version": ..., "max_major": ...}`), and the local agent parsed it into
`LeaseClaims.software`. Nothing ever read it: a signed lease demanding a runtime
the local agent does not provide was accepted exactly like a compatible one. The
claim was signed control-plane data with no enforcement — the same class of
defect as an unenforced entitlement, but on the software-compatibility axis.

Concretely, before this change a lease with `software={"min_version": "99.0.0"}`
verified as `active` against a `1.0.0` runtime.
## What is connected

`mrqlab_agent.license.LeaseVerifier.verify` now enforces the claim. The
time-window decision runs first, so an expired lease reports expiry rather than a
software mismatch; the compatibility window is then checked before the lease is
accepted as `active` or `offline_grace`:

- `min_version` — the oldest runtime the issuer will run against. The runtime is
  rejected when it is below the minimum. Missing components compare as zero, so
  a minimum of `"1.0"` equals runtime `"1.0.0"`. Version components must be
  ASCII decimal digits, so a non-ASCII digit such as `"١"` is rejected rather
  than silently compared.
- `max_major` — an upper cap on the runtime major version. A runtime whose major
  exceeds the cap is rejected. The boundary itself is allowed.

`RUNTIME_VERSION` is the local runtime's compatibility version, distinct from the
product version, and is derived from the package's single source of truth
(`mrqlab_agent.__version__`) so the enforced axis cannot drift from the shipped
runtime. `LeaseVerifier` takes an explicit `runtime_version` so tests and future
runtimes can override it.

The `software` claim is a required, typed sub-model (`LeaseSoftware`) whose only
declared keys are the two the verifier enforces; an unknown signed key fails
validation rather than being accepted and ignored. Strict scalar members matter
because `bool` is an `int` subtype and a quoted number is a string: without them
a signed JSON `true` or `"2"` would coerce into a numeric version bound. Because
the claim has been part of the signed schema since the plan
(`docs/superpowers/plans/2026-09-27-protocol-platform.md`), it stays **required**
— an omitted claim fails closed as malformed rather than verifying active with no
window. The sibling `limits` map is likewise `dict[str, StrictInt]`, so a signed
`true` cannot become the concurrency limit `1`.

## Boundaries

This is compatibility gating, not a production license service. It does not
implement key rotation, revocation, a hosted issuance endpoint, persistent
device registration, or the device proof-of-possession renewal flow. It does not
change `POST /experiments/run` (Tier 1 stays synchronous) or add running-job
preemption. No physics operator imports licensing code; the check remains at the
execution gateway.

**The verifier is now wired into the gateway.** `main.py` constructs
`lease_verifier` at import from the process environment via
`mrqlab_agent.config.load_lease_verifier`, so a provisioned deployment enforces
the lease with no code change and `POST /jobs` / `POST /jobs/{id}/cancel` verify
a real signed lease. The verifier's own decision logic is unchanged; only its
construction is added.

Configuration is read from four environment variables:

| Variable | Meaning |
|---|---|
| `MRQLAB_LEASE_TRUSTED_KEYS` | JSON object `{kid: base64url Ed25519 public key}` |
| `MRQLAB_DEVICE_ID` | this device's id, bound by the lease |
| `MRQLAB_DEVICE_PUBLIC_KEY_HASH` | this device's public-key hash |
| `MRQLAB_FINGERPRINT_HASH` | this device's hardware fingerprint hash |

The loader fails closed: it returns `None` (the gateway's existing 503) only when
*no* variable is set, and raises on a partial or malformed configuration rather
than silently falling back to the unconfigured state, so a deployment that meant
to enforce leases cannot run open by accident. It never fabricates a trusted key
or a device identity.

## Verification

`tests/local_agent/test_license.py` adds the enforced-window regressions: below
minimum, the exact-minimum boundary, a short `"1.0"` minimum against `"1.0.0"`,
a runtime major above the cap, the cap boundary itself, malformed version
strings, non-strict (boolean/string) bounds, an unknown signed key, a required
`software` claim, non-ASCII version digits, a boolean `limits` value, the
expiry-before-compatibility ordering, and that `RUNTIME_VERSION` tracks
`mrqlab_agent.__version__`.

`tests/local_agent/test_lease_wiring.py` covers the wiring: an unconfigured
environment yields no verifier, a partial or malformed configuration raises
rather than opening, a configured verifier accepts a lease bound to its device
and rejects an unknown key id, a bad signature, and a wrong-device lease, the
gateway returns 503 when unconfigured and 202/401 (never 503) when configured,
and a fresh process imports the app with the verifier built from its environment.

These are local results, not CI or scanner validation. No frontend file changed
in this backend-only stage, so the frontend suite was not run.

Full source-bound Python suite
(`PYTHONPATH=packages/sequence-ir:packages/physics:packages/recon:packages/mrqlab_experiment:services/api:services/local_agent`,
`pytest -q -p no:cacheprovider`): **1209 passed, 15 skipped**, one
Starlette/httpx deprecation warning.
