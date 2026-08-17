# Agent Tool Schemas

These schemas describe tools over `ExperimentGraph`. They are offline JSON Schema definitions only.

- `run_optimization` is reserved until an optimizer plugin exists.
- No runtime agent ships in this repository.
- Every compute tool calls canonical experiment services (`/experiments/validate`, `/experiments/run`).
- The simulator remains offline-capable: no credentials, network tools, or autonomous loop are required to run the core.
