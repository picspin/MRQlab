# Task 12 Dual-Axis Review

**Verdict: PASS-WITH-NITS**

Reviewed working tree on `feature/experiment-kernel-docs` (Task 12 / Acceptance), branched from `origin/main` @ `7229f1a` (PR #12 merge).

## Findings

No P0 findings.

### Nit: PHYSICS.md retains shipped façade class names

**Location:** `docs/PHYSICS.md`

Task 12 asked for representation/operator vocabulary. Existing `tests/physics/test_physics_docs.py` still requires `BlochEngine` / `EPGEngine` / `SpectralEngine`. Those names are documented as kernel-owned façades, not as a new inheritance tree. Matches the wrap-don't-rewrite lock.

### Nit: ROADMAP names 7.5 as a landed hardening wave

**Location:** `docs/ROADMAP.md`

The original A–H table did not list 7.5. Recording it as already-landed backend hardening is accurate and does not reopen scope.

## Axis A: Lock / Spec / TDD Fidelity

- Five contracts appear with exact names.
- Three-layer IR string is present: Experiment IR → Sequence Compiler → Sequence IR → Physics Compiler → Physics IR.
- `ONE Python process`, `packages/mrqlab_experiment`, `/experiments/run`, `/simulate` are named.
- Roadmap holds `Do not implement Floquet/CEST/MRS/DCE in v0.1`.
- README points at locked spec, plan, ADRs, canonical `/experiments/*`, and `/simulate` compatibility.
- RED observed: old SequenceIR-centered ARCHITECTURE/ROADMAP failed the new contract tests.
- Anti-scope: no SpinEcho/TSE/CEST/ASL Sequence classes; no AdvancedSimulator; Floquet/CEST/MRS/DCE absent from experiment/web/API impl; exactly one FastAPI app.

## Axis B: Quality / Regressions

- Docs-only slice plus the new docs contract test.
- Physics backends untouched.
- Full Python and web gates green.

## Verification

- `.venv/bin/python -m pytest tests/experiment/test_experiment_docs.py -q` → 2 passed
- `.venv/bin/python -m pytest tests/ -q` → 142 passed, 1 warning
- `cd apps/web && npm test` → 4 passed
- `npm run typecheck` → pass
- `npm run build` → pass (`/`, `/editor`, `/signal-lab`)
- `rg` anti-scope checks as specified in Task 12 Step 6
