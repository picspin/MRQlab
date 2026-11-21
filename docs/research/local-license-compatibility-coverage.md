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

`mrqlab_agent.license.LeaseVerifier.verify` now enforces the claim, after the
audience/device/fingerprint binding and before the time-window decision:

- `min_version` — the oldest runtime the issuer will run against. The runtime is
  rejected when it is below the minimum. Missing components compare as zero, so
  a minimum of `"1.0"` equals runtime `"1.0.0"`.
- `max_major` — an upper cap on the runtime major version. A runtime whose major
  exceeds the cap is rejected. The boundary itself is allowed.

`RUNTIME_VERSION` is the local runtime's compatibility version, distinct from the
product version. `LeaseVerifier` takes an explicit `runtime_version` so tests and
future runtimes do not depend on a module constant.

The `software` claim is now typed with strict scalar members
(`dict[str, StrictStr | StrictInt]`) and defaults to empty. Strict typing matters
because `bool` is an `int` subtype: an ordinary `int` member would silently
coerce a signed JSON `true` into the numeric bound `1`. An absent claim imposes
no window, preserving leases issued before the claim existed.

## Boundaries

This is compatibility gating, not a production license service. It does not
implement key rotation, revocation, a hosted issuance endpoint, persistent
device registration, or the device proof-of-possession renewal flow. It does not
change `POST /experiments/run` (Tier 1 stays synchronous) or add running-job
preemption. No physics operator imports licensing code; the check remains at the
execution gateway.

## Verification

`tests/local_agent/test_license.py` adds the enforced-window regressions: below
minimum, the exact-minimum boundary, a short `"1.0"` minimum against `"1.0.0"`,
a runtime major above the cap, the cap boundary itself, malformed version
strings, non-strict (boolean/string) bounds, and an absent claim.

The full local suite and the frontend suite are recorded in the stage report;
these are local results, not CI or scanner validation.
