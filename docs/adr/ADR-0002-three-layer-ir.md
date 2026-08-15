# ADR-0002: Three-layer Intermediate Representation

**Status:** Accepted
**Date:** 2026-08-15

## Context

One IR cannot simultaneously preserve clinical intent, scanner events, and execution-specific state propagation without leaking abstractions between layers.

## Decision

MRQLab uses this compilation boundary:

```text
Experiment IR → Sequence Compiler → Sequence IR → Physics Compiler → Physics IR
              → StateRepresentation + PhysicsOperator → Observation
```

Experiment IR contains graph meaning and intent. Sequence IR remains the current validated eight-channel scanner event graph. Physics IR is a versioned typed operator stream based on the existing scheduler output.

The Physics Compiler may emit dedicated representation spans. ssEPG is a distinct span/compiler path and is never modeled as `epg.enable_slice_profile=True`. PDG is the bridge between abstract phase pathways and spatial Bloch/image formation.

## Consequences

- Existing scheduling and numerical engines are elevated rather than replaced.
- Compilers own translation; the frontend never authors physics operators directly.
- Hybrid representation work can be added by new spans without changing Experiment IR.
- Floquet, CEST, MRS, and DCE are documented seams only for v0.1.

