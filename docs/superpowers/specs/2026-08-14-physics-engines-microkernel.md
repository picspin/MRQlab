# Physics Engines Microkernel — Locked Product Spec

## Goal

Complete the backend physics layer as a NumPy-first microkernel with three production engines behind one stable call:

```python
simulate(
    sequence: SequenceIR,
    phantom: Phantom,
    scanner: ScannerModel,
    options: EngineOptions,
) -> SimResult
```

The engines are:

1. `BlochEngine`: multi-isochromat simulation, with SE and GRE as its primary teaching sequences.
2. `EPGEngine`: classic configuration states for TSE and echo trains, with explicit extension seams for diffusion and EPG-X Bloch–McConnell/magnetization-transfer state layouts.
3. `SpectralEngine`: independent multi-pool chemical-shift simulation v0, demonstrated with fat and water; richer CEST and MRS behavior remains outside this follow-up.

## Ownership Boundary

The microkernel owns `SequenceIR` scheduling, unit conversion, work estimation and caps, engine discovery, entry-point loading, shared operator contracts, ADC/NCO sampling, and common result assembly. Engine plugins own state representation and application of scheduled operators.

The dependency direction remains:

```text
sequence-ir → physics → recon → api → web
```

Recon and web consume `SimResult` and engine descriptors; neither may import or branch on a concrete backend class.

## Locked Decisions

- `SequenceIR` remains the MaRCoS-like event-stream source of truth with `rf_amp`, `rf_phase`, `gx`, `gy`, `gz`, `adc_gate`, `nco_freq`, and `nco_phase` channels.
- RF amplitude and phase values are degrees at the IR boundary; physics operators use radians internally.
- Time is seconds throughout the IR and physics public API.
- Current template gradient values remain dimensionless teaching units scaled by `ScannerModel.gradient_scale` in Hz/m.
- EPG configuration shifts prefer `SequenceIR.metadata["epg_dk_events"]`; gradient-area quantization is a documented fallback.
- Work is capped from operator count × backend state width, not from sequence duration as a proxy for wall-clock runtime.
- The default install requires NumPy, not torch, MRzero, pulseq-zero, PyPulseq, or SigPy.
- PDG is an adapter protocol and unavailable-provider error path only; it is not a fourth built-in engine in this follow-up.
- Bloch–McConnell and magnetization-transfer integration lands as typed EPG-X state/layout seams with explicit unsupported-feature errors, not partial biology.
- Algorithms are reimplemented from equations and verified by independent golden values. Upstream source files are not copied or vendored.
- This software is a teaching simulator, not a clinical scanner, safety simulator, or hardware control surface.

## Algorithm References

- Weigel 2015: classic EPG RF, relaxation, shift, and echo-state semantics.
- Malik et al. 2018: EPG-X state organization, diffusion, exchange, and MT extension points.
- Pruessmann et al. 2021, doi:10.1002/mrm.29101: configuration-space framing and EPG as a discrete representation.
- Endres/Möbius et al. 2024, doi:10.1002/mrm.30055: PDG concepts and the rationale for a future optional adapter.
- Pulseq and PyPulseq: event timing concepts.
- MaRCoS: timed TX, gradient, RX-gate, and NCO event-stream concepts.
- imr-framework/epg, mriphysics/EPG-X, and pulseq-zero/PDG: conceptual comparison targets only.

## Acceptance

- `BlochEngine`, `EPGEngine`, and `SpectralEngine` all return `SimResult` through the unchanged `SimulationEngine.simulate` signature.
- RF phase changes the rotation axis.
- Bloch evolves and combines multiple isochromats.
- TSE produces a real classic-EPG echo train with bounded configuration orders.
- Fat/water pools produce the expected chemical-shift phase evolution and beating.
- The API accepts an explicit engine or uses template metadata without binding recon or web to an engine.
- Third-party engines load through the `mrqlab.physics_engines` entry-point group.
- EPG-X diffusion/layout seams and the PDG provider seam have executable contract tests.
- Cross-engine overlap tests establish phase convention, signal scaling, ADC timing, and relaxation consistency.
- All caps reject excessive estimated work before backend allocation.
