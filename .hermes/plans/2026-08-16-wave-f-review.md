# Wave F Dual-Axis Review

**Verdict: PASS-WITH-NITS**

Reviewed `origin/main @ e62fbec...eac1800` on `feature/experiment-kernel-f`.

## Findings

No P0 findings.

### Nit: plan mentions undo/redo/persistence; v0 provider is in-memory only

**Location:** `apps/web/components/workspace/WorkspaceProvider.tsx`

Task 8 interface text says the provider owns undo/redo and persistence. The plan's concrete implementation is the in-memory React state shown in the task body. This slice matches that code exactly and does not invent those extra stores.

### Nit: Explore cards are static, not `/presets`

**Location:** `apps/web/app/page.tsx`

Task 9 lists `/presets` as a consumed interface and adds `lib/api.ts`, but the specified Home implementation uses hardcoded clinical cards. Matches the plan code. Live wiring is later.

## Axis A: Lock / Spec / TDD Fidelity

- Workspace IDs and five cursor names match the spec exactly.
- Layout wraps `WorkspaceProvider` + `WorkspaceShell`.
- Explore is clinical-first: T1 Contrast, Dark Blood, Dixon, T2 Mapping; sequence names are `Uses:` text.
- Linked Lens labels are SYSTEM / PHYSICS / STATE / OBSERVATION.
- Design tokens `--rail:19%`, `--canvas:62%`, `--timeline:38%`, `--visualization:62%` exist; no mechanical `1.618`.
- Vitest RED was observed (missing `WorkspaceProvider`, then missing `LinkedLens`) before GREEN.
- No backend/physics/SequenceIR edits. Signal Lab (Task 10 / Wave G) not implemented.

## Axis B: Quality / Regressions

- `apps/web/lib` was initially ignored by root `lib/`; fixed to `/lib/`.
- Vitest needs `esbuild.jsx = "automatic"`; required for the plan's JSX tests.
- Python suite unchanged and still green.

## Verification

- `cd apps/web && npm test` → 3 passed
- `cd apps/web && npm run typecheck` → pass
- `cd apps/web && npm run build` → pass (`/`, `/editor`)
- `.venv/bin/python -m pytest tests/ -q` → 138 passed, 1 warning
