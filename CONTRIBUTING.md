# Contributing

MRQLab is a research-use-only teaching MRI simulator. It is not a scanner
console and not diagnostic software.

## One seam per PR

Land one locked honesty or feature seam. Patch versions use `0.xx.x`. Do not
stack Hybrid, Pulseq, GPU jobs, N-pool, MRS, or CEST imaging onto an unrelated
fix.

## Ablation gate (ADR-0007)

Every product feature PR must prove the new module is necessary and delete
abstractions that are not.

1. List every new public type, module, endpoint, or UI surface.
2. Delete each one in turn (locally, do not commit the deletion).
3. If a named lock-face test or fail-closed path breaks, **keep** it and cite
   that test in the PR body.
4. If tests still pass, **delete it for real** before merge.
5. Delete one-use wrappers that do not enforce a boundary.
6. Do not land interfaces reserved only for an unspecified future.

The GitHub pull request template has the required `## Ablation` section.
Cloud / Mac review treats a missing report on a feature PR as **block**.

Honesty patches (`0.xx.x` fail-closed): slim form is enough
(`remove this guard → <test> fails`).
