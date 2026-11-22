# Local license: deferred findings (pre-existing, not yet fixed)

Parent anchor `ec3355f`. Research/teaching only; no scanner validation, clinical
quality certification or scanner-ready claim. These are **not** fixed by the
`feat/milestone-c-licensed-compute` line; they are recorded here as separate
follow-up tasks so they are not lost.

They were surfaced by an independent (Codex) blind review of the Milestone C
branch and each one was **reproduced locally** before being written down. All
three pre-date the Milestone C change: the fields and the key lookup are
byte-identical at the base `ec3355f`. They are filed separately rather than
folded into the Milestone C increment because none of them is on the
software-compatibility axis that increment owns, and two of them (F1, F3) touch
the lease claim schema in ways that deserve their own design decision.

## F1 — non-finite timestamps can make a signed lease never expire

- **Severity:** major. **Files:** `services/local_agent/mrqlab_agent/models.py`
  (`issued_at`, `not_before`, `expires_at`, `offline_grace_until`),
  `services/local_agent/mrqlab_agent/license.py` (the `now > claims.expires_at`
  and `now > claims.offline_grace_until` tests).
- **Why:** the timestamp fields are plain `float`. Python's JSON parser accepts
  `NaN` and `Infinity`, and a valid JSON number such as `1e999` becomes `inf`. A
  signed lease with `expires_at: NaN` (or `Infinity` / `1e999`) therefore never
  compares `now > expires_at` true and stays `active` indefinitely; a non-finite
  `offline_grace_until` likewise prevents the grace window from closing.
- **Repro:** build a lease token whose payload has
  `"expires_at": NaN` (raw JSON text, since `json.dumps` would emit `NaN` too),
  `"offline_grace_until": NaN`, sign it, and call
  `LeaseVerifier(...).verify(token, wall_time=10**10, monotonic_time=10)` — it
  returns `state="active"` at a wall time far past any expiry.
- **Fix sketch:** reject non-finite timestamps in a `LeaseClaims` validator
  (`math.isfinite` on each), and validate the chronological ordering
  (`issued_at <= not_before <= expires_at <= offline_grace_until`). Add
  signed-token regression tests for `NaN`, `Infinity`, and `1e999`.
- **Note:** this is the same class as rule R3 (numeric contracts must reject
  values the domain forbids), extended from booleans to non-finite floats; it
  may be worth a new `regular.md` rule.

## F3 — lease timestamps accept boolean values (R3 class)

- **Severity:** major. **File:** `services/local_agent/mrqlab_agent/models.py`.
- **Why:** `issued_at` / `not_before` / `expires_at` / `offline_grace_until` are
  plain `float`, and `bool` is an `int` subtype, so a signed `expires_at: true`
  is coerced to `1.0` rather than rejected — the R3 anti-pattern on the lease
  contract. The Milestone C change made `software` and `limits` strict but left
  these four fields coercing.
- **Repro:** `LeaseClaims.model_validate({... "expires_at": true ...})` succeeds
  and yields `expires_at == 1.0`.
- **Fix sketch:** use a strict numeric type (or a pre-validation guard) for the
  four timestamp fields and test each with a boolean value, mirroring the
  `limits`/`software` treatment.

## F4 — an unhashable `kid` in the token header becomes a server error

- **Severity:** minor. **File:** `services/local_agent/mrqlab_agent/license.py`
  (the `self.trusted_keys[kid]` lookup and its `except KeyError`).
- **Why:** `kid` comes from the untrusted header. A header whose `kid` is a JSON
  array or object (`"kid": []`) is unhashable, so the dict lookup raises
  `TypeError` before signature verification. `verify_lease` in `main.py` maps
  only `PermissionError`/`ValueError`, so the request surfaces as an HTTP **500**
  instead of the intended 401.
- **Repro:** POST a token whose header is
  `{"alg":"EdDSA","kid":[]}` to `/jobs` with the lease gate configured — the
  response is 500, whereas a merely malformed lease is 401.
- **Fix sketch:** validate that `kid` is a `str` before the lookup and raise
  `ValueError` otherwise; add a malformed-header endpoint test asserting 401.

## Verification

Each repro above was executed against
`feat/milestone-c-licensed-compute` at its current head and reproduced as
described. These are local results, not CI or scanner validation.
