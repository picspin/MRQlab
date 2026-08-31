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

The v0.67 Control Bank overlays saturation B1, offset span, and pulsed duty cycle into `metadata.cest` (CW still rejects duty). 0.67.1: virgin RUN posts `{}`. 0.67.2: knobs hydrate from recipe `metadata.cest`. 0.67.3: pulsed recipe declares `duty_cycle`; frontend reads that field and does not recompute `n·pulse/duration`. 0.67.4: recipes declare `offset_span_ppm`; frontend reads that field and does not `Math.max(offsets)`. 0.67.5: CEST knobs start null (`—`) until recipe hydrate; no hardcoded 2 / 5 / 0.5 seeds. 0.67.6: duty slider and pulsed/CW copy follow `metadata.cest.mode`, not the recipe id; CW recipes declare `mode="cw"`. 0.67.7: Explore launches both CW (`cest-apt`) and pulsed (`cest-apt-pulsed` → `cest_amide_pulsed_z_spectrum`); pulsed copy does not say CW. 0.67.8: Spectrum title follows `metadata.cest.mode` (`Amide CEST pulsed Z-spectrum` / `Amide CEST CW Z-spectrum`); hydrate-before stays generic `Amide CEST Z-spectrum`. 0.67.9: any `cest_amide_*` deep-link maps to Spectrum (`cest_amide`), never falls back to MS plaque. 0.67.10: CEST RUN products/params follow Spectrum identity, not a two-id recipe whitelist. 0.67.11: spectroscopy Explore cards omit imaging FA/TE/TR (`parameters` optional; CEST/MRS/X-nuclei do not claim spin-echo products). 0.67.12: `cest_amide` omits imaging `defaultParams`; cockpit reads them optionally and does not seed FA/TE/TR/geometry from a fake spin-echo. 0.67.13: CEST sliders disabled until recipe hydrate (no fake thumb); Spectrum identity / physics tab / clinical dropdown follow `seqType === "CEST"`, not the `cest_amide` key. 0.67.14: CEST sliders omit a numeric `value` until hydrate (no parked 0.5 / 3.5 / 0.2 thumb). 0.67.15: Explore CW card title is `Amide CEST CW Z-spectrum` (pulsed card already says pulsed; CW no longer hides behind a generic Z-spectrum title). 0.67.16: CEST spectrum mapping follows `cest_*` + `z_spectrum`, not a `cest_amide_` prefix (`cest_amine_z_spectrum` stays Spectrum). 0.67.17: Explore CW card `sequence` is `EPG-X CEST CW offset sweep` (pulsed already says pulsed; CW no longer hides behind a generic offset sweep). 0.67.18: Physics Hamiltonian follows `metadata.cest.mode` (`EPG-X CEST pulsed` / `EPG-X CEST CW`); hydrate-before stays generic `EPG-X CEST`. 0.67.19: Explore CW card `clinicalQuestion` names CW (pulsed already names pulsed; CW no longer hides behind a generic amide-exchange question). 0.68: Lego `/sequences/compose` trap blocks write physical mT/m channel values and opt in `metadata.gradient_units="mt_m"`; RF-only compose stays teaching. Existing TSE/GRE templates remain teaching. 0.68.1: G editor loads SequenceIR amplitude when `metadata.gradient_units="mt_m"` (no fake 20 mT/m seed); teaching IR still labels timeline ±1 as not mT/m. 0.68.2: G editor hydrates duration/ramp from `event_overlays` when present (no fake 1 ms / 0.1 ms seeds). 0.68.3: G patch on `gradient_units=mt_m` IR writes channel amplitude as mT/m (teaching IR still overlay-only). 0.68.4: physical-G timeline caption is `Gx/Gy/Gz mT/m` (teaching stays `SequenceIR 5-ch`). 0.68.5: Lego caption follows `gradient_units` (`PHYSICAL G · mT/m` after trap compose; empty/RF-only stays `TEACHING BLOCKS`). 0.69: trap compose writes `fov_m` + `preferred_engine=epg` so physical-G IR can run EPG isotropic diffusion (RF-only compose still teaching, no ADC claim). 0.70: `cest_amine_z_spectrum` is its own two-pool CW amine recipe (+2 ppm), not an amide alias; Explore `cest-amine` and Spectrum identity follow the solute. 0.71: Spectrum viewport splits Z(Δ) and MTR_asym into separate panels and labels the engine boundary (CEST = pool model + Bloch–McConnell + EPG-X, not MRS/COSY density-matrix). 0.72: Spectrum axes are honest — ppm ticks from backend `offset_ppm`; MTR_asym uses its own amplitude, not a Z∈[0,1] scale. 0.73: MTR abscissa is ppm only; amplitude is a separate ordinate (`spectrum-mtr-scale`), not mixed as `±0.12 ppm`. 0.74: MTR abscissa uses its own `offset_ppm` span (e.g. 3.5–5), not the Z-spectrum [-5, 5]. 0.74.1: physical trap compose emits a zero at `t0+duration_s` so scheduler stepwise-hold does not keep G on through ADC; two declared durations yield different gradient moments. 0.74.2: physical G patch moves that compose end-zero when duration changes; overlay-only duration no longer leaves the scheduler holding G. N-pool JSON/YAML pool tables, lineshapes, NH/OH chemical catalogs, and CEST imaging remain v1.0+; EPG-X stays two-pool.

- Next fidelity: diffusion wiring on physical-G IR, then Bloch–McConnell/MT, CEST saturation, richer MRS, and an optional PDG provider distribution.
- Progressive Beginner, Clinical, Physics, and Hardware *concept* curricula. “Hardware” remains a learning mode, never an acquisition connection.
- Optimizer plugins consuming `ObjectiveFunction` (grid / Bayesian / CMA-ES). Differentiable EPG is later.
- Fidelity layers driven by the Reality Slider over a typed `DisturbanceStack`, with explicit assumptions and error budgets.

## Delivery

After the local learning loop is stable, the static/web surface may deploy to Vercel or Cloudflare and the API to a separately bounded Python host. Codex Cloud is a development agent only; it is not runtime infrastructure, a simulator backend, or a deployment target. Real scanner hardware, MaRCoS, Red Pitaya, and acquisition services remain out of scope.
