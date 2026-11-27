# Local license: review findings and resolved follow-ups

Parent anchor `ec3355f`. Research/teaching only; no scanner validation, clinical
quality certification or scanner-ready claim.

These findings were surfaced by an independent (Codex) blind review of the
Milestone C branch. All three pre-date the Milestone C change: their original
fields and key lookup are byte-identical at the base `ec3355f`.

**Disposition (PR #70 follow-up):** the two Major findings on the lease validity
window — F1 and F3 — are fixed in this branch rather than deferred. The common
schema change uses finite strict timestamps and chronological window validation;
regression coverage exercises model inputs and raw signed JSON spellings. F4 is
also fixed: a non-string `kid` is a malformed lease (401 at the gateway), not a
server error. The retained sections are the historical review record and explain
the regressions that must remain.

## F1 — non-finite timestamps could make a signed lease never expire (**fixed**)

- **Severity:** major. **Files:** `services/local_agent/mrqlab_agent/models.py`
  (`issued_at`, `not_before`, `expires_at`, `offline_grace_until`),
  `services/local_agent/mrqlab_agent/license.py` (the `now > claims.expires_at`
  and `now > claims.offline_grace_until` tests).
- **Original mechanism:** the timestamp fields were plain `float`. Python's JSON
  parser accepts `NaN` and `Infinity`, and a valid JSON number such as `1e999`
  becomes `inf`. A signed lease with `expires_at: NaN` (or `Infinity` / `1e999`)
  therefore never compared `now > expires_at` true and could stay `active`
  indefinitely; a non-finite `offline_grace_until` likewise prevented the grace
  window from closing.
- **Original repro:** build a lease token whose payload had
  `"expires_at": NaN` (raw JSON text, since `json.dumps` would emit `NaN` too),
  `"offline_grace_until": NaN`, sign it, and call
  `LeaseVerifier(...).verify(token, wall_time=10**10, monotonic_time=10)` — it
  returned `state="active"` at a wall time far past any expiry.
- **Resolution:** `LeaseTimestamp` is now `Annotated[StrictFloat,
  Field(allow_inf_nan=False)]`, and the `LeaseClaims` after-validator requires
  `issued_at <= not_before <= expires_at <= offline_grace_until`. This rejects
  `NaN`, infinities, and parsed `1e999` before `verify()` reaches a comparison.
  Regressions cover model input and signed raw JSON `NaN`/`Infinity`/`-Infinity`/
  `1e999` spellings.
- **Rule connection:** this is the same numeric-contract family as R3, extended
  from boolean coercion to non-finite values the time domain forbids.

## F3 — lease timestamps accepted boolean values (R3 class) (**fixed**)

- **Severity:** major. **File:** `services/local_agent/mrqlab_agent/models.py`.
- **Original mechanism:** `issued_at` / `not_before` / `expires_at` /
  `offline_grace_until` were plain `float`, and `bool` is an `int` subtype, so a
  signed `expires_at: true` was coerced to `1.0` rather than rejected — the R3
  anti-pattern on the lease contract. The initial Milestone C change made
  `software` and `limits` strict but left these four fields coercing.
- **Original repro:** `LeaseClaims.model_validate({... "expires_at": true ...})`
  succeeded and yielded `expires_at == 1.0`.
- **Resolution:** the shared `LeaseTimestamp` contract is strict, so booleans
  and quoted numbers now fail validation. Regressions cover true/false/quoted
  values for every timestamp field.

## F4 — an unhashable `kid` in the token header became a server error (**fixed**)

- **Severity:** minor. **File:** `services/local_agent/mrqlab_agent/license.py`
  (the `self.trusted_keys[kid]` lookup and its `except KeyError`).
- **Original mechanism:** `kid` comes from the untrusted header. A header whose
  `kid` is a JSON array or object (`"kid": []`) is unhashable, so the dict lookup
  raised `TypeError` before signature verification. `verify_lease` in `main.py`
  mapped only `PermissionError`/`ValueError`, so the request surfaced as an HTTP
  **500** instead of the intended 401.
- **Original repro:** POST a token whose header is `{"alg":"EdDSA","kid":[]}`
  to `/jobs` with the lease gate configured — the response was 500, whereas a
  merely malformed lease was 401.
- **Resolution:** `LeaseVerifier.verify` now validates `kid` is a string before
  the lookup and raises `ValueError` otherwise. Unit and gateway endpoint
  regressions assert an array `kid` fails as a normal 401 lease rejection.

## Verification

The original repro mechanisms were confirmed locally before this follow-up.
The fixes are covered by the focused agent suite; results are local verification,
not CI or scanner validation.
