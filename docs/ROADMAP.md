# Roadmap

## v0.1 — now

- v0.1: SE timeline ↔ Bloch ↔ signal ↔ image.
- v0.1: GRE gradient ↔ k-space ↔ contrast.
- v0.1 thesis: TSE refocusing FA ↔ EPG ↔ echo train ↔ k-space weighting ↔ contrast + relative SAR.
- Clinical Explore, Editor Linked Lens, and Signal Lab share one experiment workspace.
- Canonical `/experiments/validate` and `/experiments/run`; `/simulate` remains compatible.
- Agent tool JSON schemas only; no runtime agent.
- Do not implement Floquet/CEST/MRS/DCE in v0.1.

Waves A–H follow the plan; AI Lab runtime is last.

| Wave | Scope |
|---|---|
| A | `ExperimentGraph`, presets, compiler façade, canonical APIs |
| B | `PhysicsOperator`, `StateRepresentation`, capability negotiation, Physics IR |
| C | `Observation`, `ResultGraph`, provenance |
| D | `ObjectiveFunction` v0 forward scores |
| E | `DisturbanceStack` schema and reselection explanations |
| 7.5 | Backend hardening (immutable resolution, exact products, fail-closed reserved kinds) |
| F | Workspace shell, clinical Explore, Editor Linked Lens |
| G | TSE Signal Lab teaching chain |
| H | Agent tool schemas only |

## Next

The v0.64 single-voxel two-liquid-pool CW CEST Z-spectrum observation seam is closed. CEST imaging, multi-pool CEST, pulsed saturation trains, and MRS density-matrix work remain later roadmap items.

- Next fidelity: physical gradient units and diffusion wiring, then Bloch–McConnell/MT, CEST saturation, richer MRS, and an optional PDG provider distribution.
- Progressive Beginner, Clinical, Physics, and Hardware *concept* curricula. “Hardware” remains a learning mode, never an acquisition connection.
- Optimizer plugins consuming `ObjectiveFunction` (grid / Bayesian / CMA-ES). Differentiable EPG is later.
- Fidelity layers driven by the Reality Slider over a typed `DisturbanceStack`, with explicit assumptions and error budgets.

## Delivery

After the local learning loop is stable, the static/web surface may deploy to Vercel or Cloudflare and the API to a separately bounded Python host. Codex Cloud is a development agent only; it is not runtime infrastructure, a simulator backend, or a deployment target. Real scanner hardware, MaRCoS, Red Pitaya, and acquisition services remain out of scope.
