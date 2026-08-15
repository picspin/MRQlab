# Physics v1

MRQLab is a teaching MRI simulator, not a clinical scanner, safety simulator, or hardware controller. `SequenceIR` is the only event source. The physics microkernel converts its RF, gradient, ADC-gate, and NCO channels into `RfOp`, `Relax`, `Shift`, `GradInterval`, and `AdcSample`; plugins apply those operators to their own state.

## Engines

| Engine | State | Primary teaching use | Physics v1 boundary |
|---|---|---|---|
| `BlochEngine` | Cartesian `Mxyz` per weighted isochromat | SE, GRE, off-resonance and spatial dephasing | Instantaneous RF and dimensionless teaching gradients |
| `EPGEngine` | Signed classic `(F+, F-, Z)` configuration orders | TSE/CPMG echo trains | Single pool, bounded integer orders, metadata-first `dk` |
| `SpectralEngine` | Independent chemical-shift Bloch pools | Fat/water phase and beating | No exchange, MT, CEST saturation, or fitted MRS lineshapes |

All are returned as a kernel-owned `SimulationEngine` implementing `simulate(SequenceIR, Phantom, ScannerModel, EngineOptions) -> SimResult`. Recon, API, and web consume `SimResult`; they do not import engine classes.

## Units and signal convention

- IR RF amplitude and phase are degrees; the scheduler converts them to radians.
- Time is seconds.
- Current gradients are dimensionless teaching gradients scaled by `ScannerModel.gradient_scale` in Hz/m.
- Signal is `Mx + 1j*My`; positive off-resonance accumulates positive phase and NCO demodulation removes phase with a negative exponential.
- EPG shifts prefer `SequenceIR.metadata["epg_dk_events"]`. Area quantization by `EngineOptions.epg_dk_scale` is a fallback for untagged IR.

## Operators

For RF flip `α` and phase `φ`, `RfOp` applies the Weigel classic EPG matrix to `(F+, F-, Z)` and the equivalent right-hand Rodrigues rotation about `(cos φ, sin φ, 0)` to Bloch states. `Relax` applies `E1 = exp(-dt/T1)`, `E2 = exp(-dt/T2)`, with equilibrium regrowth only at `Z0`. `Shift` translates `F+` by `+dk` and `F-` by `-dk`; `Z` is unchanged. `GradInterval` applies spatial phase in Bloch/spectral states and advances the shared k-trajectory. `AdcSample` observes the current transverse state and applies NCO demodulation.

## Work safety

Before schedule or backend-state materialization, an arithmetic preflight counts ADC samples and planned operators, then the kernel estimates work as operator count times backend state width: isochromat count for Bloch, `3 × (2*kmax + 1)` for EPG, and isochromat count times pool count for spectral. A sequence is additionally limited to 100,000 channel events and 250,000 ADC samples. The API clamps request `max_work` to `SIM_MAX_WORK=2000000` by default and disables magnetization/configuration snapshots because its response does not return them. `SIM_MAX_MATRIX=64` remains the reconstruction/UI dimension cap. Sequence duration is not treated as wall-clock runtime.

## Plugins

External distributions publish an `EnginePlugin` backend descriptor. Its state-width function must not allocate backend state; its factory returns an object that applies scheduled non-ADC operators, exposes the raw transverse signal through `observe()`, and optionally snapshots its state.

```python
from mrqlab_physics import EnginePlugin

plugin = EnginePlugin(
    name="my_engine",
    description="Example state backend",
    state_width=state_width,
    backend_factory=make_backend,
)
```

```toml
[project.entry-points."mrqlab.physics_engines"]
my_engine = "my_package.engine:plugin"
```

Names must match the entry-point name and may not shadow `bloch`, `epg`, or `spectral`. Full `SimulationEngine` entry points are rejected with a migration error because they could bypass kernel scheduling and caps. The kernel wraps every descriptor in the same four-argument façade and owns scheduling, cap enforcement, ADC/NCO demodulation, k-trajectory, and `SimResult` assembly. PDG remains a standalone `PDGAdapter` seam with a caller-supplied provider; torch, MRzero, and pulseq-zero are not default dependencies.

## Extension seams

`diffusion_attenuation` provides the diagonal configuration-space free-diffusion propagator but is not applied to teaching-unit gradients. `EpgXLayout` fixes Bloch–McConnell and magnetization-transfer state rows; their evolution functions raise explicit physics-v1 boundary errors. This prevents partially correct exchange or MT behavior from appearing as supported simulation.

## Algorithm references

- Weigel 2015, *Extended phase graphs: dephasing, RF pulses, and echoes—pure and simple* — classic RF, shift, relaxation, and echo semantics.
- Malik et al. 2018, EPG-X — multi-pool exchange/MT layouts and diffusion extension concepts.
- Pruessmann et al. 2021, doi:10.1002/mrm.29101 — configuration-space representation and discrete EPG framing.
- Endres/Möbius et al. 2024, doi:10.1002/mrm.30055 — phase distribution graphs and the future provider-adapter direction.
- Pulseq, PyPulseq, and MaRCoS — event timing and event-stream concepts.
- imr-framework/epg, mriphysics/EPG-X, and pulseq-zero/PDG — numerical/conceptual comparison targets; their source is not vendored or copied.
