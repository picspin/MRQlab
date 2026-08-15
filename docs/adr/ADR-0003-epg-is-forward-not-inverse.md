# ADR-0003: EPG Is a Forward Model, Not an Inverse Algorithm

**Status:** Accepted
**Date:** 2026-08-15

## Context

EPG, EPG-X, and ssEPG efficiently propagate configuration states. Calling them inverse engines conflates a forward representation with the algorithm that searches parameter space.

## Decision

EPG-family implementations are `StateRepresentation` plus `PhysicsOperator` forward paths. Inverse design is a separate optimizer plugin evaluating an `ObjectiveFunction` over observations:

```text
theta* = argmin_theta ObjectiveFunction(Observation(forward(theta)))
```

Grid search, Bayesian optimization, and CMA-ES are planned non-differentiable plugins. Differentiable EPG with Adam/LBFGS is later work. AI may help formulate or explain an objective, but does not replace the optimizer.

Representation and operator remain separate: Bloch/EPG/PDG/density matrix are representations; RF/relaxation/gradient/exchange/diffusion/flow/chemical shift are operators. EPG-X is EPG plus exchange operators. The MRS base is density matrix and Liouville–von Neumann propagation; Floquet is only a future periodic accelerator or steady-state solver.

## Consequences

- Engines expose capabilities through a matrix, not a `BaseSimulator` inheritance tree.
- Objective v0 can land before any search algorithm.
- Optimization results can compare representations under one objective and later expose Pareto trade-offs.

