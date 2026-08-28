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

The v0.67 Control Bank overlays saturation B1, offset span, and pulsed duty cycle into `metadata.cest` (CW still rejects duty). 0.67.1: virgin RUN posts `{}`. 0.67.2: knobs hydrate from recipe `metadata.cest`. 0.67.3: pulsed recipe declares `duty_cycle`; frontend reads that field and does not recompute `n·pulse/duration`. 0.67.4: recipes declare `offset_span_ppm`; frontend reads that field and does not `Math.max(offsets)`. 0.67.5: CEST knobs start null (`—`) until recipe hydrate; no hardcoded 2 / 5 / 0.5 seeds. 0.67.6: duty slider and pulsed/CW copy follow `metadata.cest.mode`, not the recipe id; CW recipes declare `mode="cw"`. 0.67.7: Explore launches both CW (`cest-apt`) and pulsed (`cest-apt-pulsed` → `cest_amide_pulsed_z_spectrum`); pulsed copy does not say CW. CEST imaging, multi-solute CEST, shaped RF, and MRS density-matrix work remain later roadmap items.

- Next fidelity: physical gradient units and diffusion wiring, then Bloch–McConnell/MT, CEST saturation, richer MRS, and an optional PDG provider distribution.
- Progressive Beginner, Clinical, Physics, and Hardware *concept* curricula. “Hardware” remains a learning mode, never an acquisition connection.
- Optimizer plugins consuming `ObjectiveFunction` (grid / Bayesian / CMA-ES). Differentiable EPG is later.
- Fidelity layers driven by the Reality Slider over a typed `DisturbanceStack`, with explicit assumptions and error budgets.

## Delivery

After the local learning loop is stable, the static/web surface may deploy to Vercel or Cloudflare and the API to a separately bounded Python host. Codex Cloud is a development agent only; it is not runtime infrastructure, a simulator backend, or a deployment target. Real scanner hardware, MaRCoS, Red Pitaya, and acquisition services remain out of scope.
