# ADR-0005: Modular Monolith Deployment

**Status:** Accepted
**Date:** 2026-08-15

## Context

MRQLab needs microkernel extension boundaries, but its current teaching workloads do not justify distributed-system operations or network boundaries between physics modules.

## Decision

MRQLab v1 runs one Python process containing the experiment kernel, engines, recon, optimization ports, and FastAPI, plus one Next.js application. Microkernel is a code architecture, not a mandate for microservices.

Implementation starts in `packages/mrqlab_experiment` and wraps existing `packages/sequence-ir`, `packages/physics`, `packages/recon`, and `services/api`. The documented five-year layout uses `core/`, `engines/`, `disturbances/`, `optimization/`, and related top-level domains, reached by incremental moves and re-export shims only.

`POST /simulate` remains compatible. `POST /experiments/validate` and `POST /experiments/run` become canonical. The simulator core stays offline-capable; AI Lab is last and initially contributes schemas only.

## Consequences

- Local development and deployment remain simple.
- In-process contracts are still strict enough for future extraction.
- Job queues or GPU workers are deferred until measured workloads require them.
- No product work in the v0.1 plan creates microservices.

