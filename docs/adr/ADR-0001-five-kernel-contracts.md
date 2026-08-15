# ADR-0001: Five Stable Experiment-Kernel Contracts

**Status:** Accepted
**Date:** 2026-08-15

## Context

MRQLab already has a working `SequenceIR → SimulationEngine → SimResult` physics microkernel. That seam is useful but too narrow to express clinical intent, sample/scanner context, objectives, multi-product observations, and future experiment-level processes without turning sequence or simulator classes into the product center.

## Decision

The stable kernel contracts are named exactly:

1. `ExperimentGraph`
2. `PhysicsOperator`
3. `StateRepresentation`
4. `ObjectiveFunction`
5. `Observation`

`SequenceIR` remains the scanner-level event representation beneath `ExperimentGraph`. Existing `SimulationEngine` and `SimResult` stay as compatibility and physics execution seams wrapped by the new contracts.

Named sequences are presets that build an `ExperimentGraph`; they are not subclasses of a common sequence base. The first package is `packages/mrqlab_experiment`; `core/experiment` is a later target rename performed incrementally.

## Consequences

- API, web, and future tools address experiments rather than concrete engines.
- Physics internals remain reusable and independently testable.
- New modalities compose graph nodes, capabilities, objectives, and observations instead of adding top-level simulator classes.
- The kernel adds coordination types but must not absorb Bloch, EPG, recon, or optimizer algorithms.

