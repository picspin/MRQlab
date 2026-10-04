# ADR-0007: Feature PRs Must Ablate New Modules

## Status

Accepted.

## Context

MRQLab ships one locked seam per PR. Agents and humans still tend to add
pass-through wrappers, future-only interfaces, and catalog types that exist
only in tests. Superpowers plans already require an ablation checkbox per
task; that gate was not a repository-wide merge rule.

## Decision

Every **product feature PR** (new public type, module, endpoint, UI surface,
or execution path) must include a written **Ablation Report** and evidence
that the new module is necessary.

Ablation means: try to delete the new module, layer, wrapper, or config and
record what happens.

| Outcome | Action |
|---|---|
| Named lock-face test or fail-closed path breaks | Keep. Cite the test or path. |
| dual-stack still green | Delete it in this PR. It is not necessary. |
| one-use wrapper that does not enforce a boundary | Delete it. |
| Interface or config reserved only for an unspecified future | Delete it. Park the future in ROADMAP, do not land a stub. |

Honesty / fail-closed patch PRs (`0.xx.x`) use the slim form: “remove this
guard → which test fails.” Chrome-only version bumps with no new module are
exempt.

Docs-only PRs that add no runtime types still need a one-line ablation:
“no new runtime module.”

## Report shape (required in the PR body)

```text
## Ablation
- Added: <types / modules / endpoints>
- Keep: <name> — removing it fails <test or path>
- Deleted before merge: <names or none>
- One-use wrappers: none | <name + boundary it enforces>
- Future-only stubs: none
```

## Consequences

- Codex Cloud / Mac review **blocks** a feature PR with no Ablation section
  or with a new public type that has no caller outside its test file.
- License, GPU workers, Pulseq adapters, Hybrid restacks, N-pool, MRS, and
  CEST imaging remain parked; an ablation report cannot unlock them.
- Physics stays in `packages/physics`. TypeScript must not gain tissue /
  SAR / EPG math to “justify” a module.
