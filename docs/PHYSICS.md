# Physics

MRQLab is a teaching MRI simulator, not a clinical scanner, safety simulator, or hardware controller. The experiment kernel selects a `StateRepresentation` and applies typed `PhysicsOperator` records. `SequenceIR` remains the only scanner-level event source. The physics microkernel converts its RF, gradient, ADC-gate, and NCO channels into `RfOp`, `Relax`, `Shift`, `GradInterval`, and `AdcSample`; plugins apply those operators to their own state.

## Forward models versus inverse search

EPG, EPG-X, and ssEPG are forward models. Optimizer plugins own inverse search over an `ObjectiveFunction`:

```text
theta* = argmin_theta ObjectiveFunction(Observation(forward(theta)))
```

v0 evaluates scalar scores only. No search algorithm ships. Grid, Bayesian, and CMA-ES are planned non-differentiable plugins. Differentiable EPG with Adam/LBFGS is later work. See [ADR-0003](adr/ADR-0003-epg-is-forward-not-inverse.md).

## Representation versus operator

Bloch, EPG, PDG, and density matrix are representations. RF, relaxation, gradient/shift, exchange, diffusion, flow, off-resonance, and chemical shift are operators. There is no `BaseSimulator` inheritance tree.

- EPG-X means an EPG state plus exchange operators.
- ssEPG uses dedicated compiler spans; it is never `epg.enable_slice_profile=True`.
- PDG bridges phase pathways and spatial image formation.
- The MRS base is density matrix + Liouville–von Neumann propagation.
- Floquet is only a future `PeriodicSequenceAccelerator` / `SteadyStateSolver`.

## Capability matrix

Selection is set inclusion. Missing capabilities fail closed.

| Representation | Available | Supports | Teaching use / boundary |
|---|---|---|---|
| Bloch | yes | hard_rf, off_resonance, spatial_encoding, magnetization_states | SE, GRE, off-resonance and spatial dephasing. Instantaneous RF and dimensionless teaching gradients. |
| EPG | yes | hard_rf, configuration_states, steady_state, isotropic_diffusion | TSE/CPMG echo trains. Single pool, bounded integer orders, metadata-first `dk`; isotropic diffusion requires physical gradients. |
| Spectral | yes | hard_rf, off_resonance, multi_pool, magnetization_states | Fat/water phase and beating. No exchange, MT, CEST saturation, or fitted MRS lineshapes. |
| ssEPG | yes | hard_rf, shaped_rf, configuration_states, spatial_encoding, slice_selective | Dedicated slice-selective shaped RF / z-profile compiler path. |
| EPG-X | yes | hard_rf, configuration_states, exchange, multi_pool | Two-pool liquid Bloch–McConnell evolution on the 6-row layout, or MT free evolution on the 4-row free/bound layout. Super-Lorentzian saturation and CEST remain closed. |
| PDG | yes | hard_rf, configuration_states, spatial_encoding, off_resonance, phase_distribution | Dedicated spatial B0 pathway↔image compiler on a phase-distribution grid. |
| Density matrix | no | (future) | MRS base via Liouville–von Neumann. Vocabulary only in v0.1. |

Built-in routing is SE/GRE → Bloch and TSE → EPG through `preferred_engine` metadata; an explicit engine preference still wins if capabilities allow.

All shipped engines are returned as a kernel-owned `SimulationEngine` implementing `simulate(SequenceIR, Phantom, ScannerModel, EngineOptions) -> SimResult`. The façade classes include `BlochEngine`, `EPGEngine`, `EpgXEngine`, and `SpectralEngine`. Recon, API, and web consume `SimResult`; they do not import engine classes.

EPG-X is selected only for exchange (or an explicit `epg-x` preference). Two liquid pools are declared as a two-item `graph.tissue` tuple. Pool a declares `k_ab` in `exchange_rate_hz`; detailed balance sets `k_ba = k_ab * f_a / f_b`. Both fractions must be positive and sum to one. Each tissue's proton density is its longitudinal equilibrium (`Za0 = PD_a`, `Zb0 = PD_b`). A positive rate without the second tissue fails closed. Hard RF rotates both liquid-pool triplets independently with the same pulse, and both pools currently share the sample off-resonance.

## Units and signal convention

- IR RF amplitude and phase are degrees; the scheduler converts them to radians.
- Time is seconds.
- Gradients are dimensionless teaching values by default (an absent or `"teaching"` `SequenceIR.metadata["gradient_units"]`) and retain the v0.59 scaling by `ScannerModel.gradient_scale` in Hz/m.
- `gradient_units="mt_m"` is an explicit opt-in declaring channel values in mT/m. The physics kernel converts them with the proton gyromagnetic ratio; existing templates deliberately do not opt in. Physical EPG order spacing is one cycle across `metadata["fov_m"]`, or across the documented 0.22 m default FOV.
- Signal is `Mx + 1j*My`; positive off-resonance accumulates positive phase and NCO demodulation removes phase with a negative exponential.
- EPG shifts prefer `SequenceIR.metadata["epg_dk_events"]`. Area quantization by `EngineOptions.epg_dk_scale` is a fallback for untagged IR.

## Operators

For RF flip `α` and phase `φ`, `RfOp` applies the Weigel classic EPG matrix to `(F+, F-, Z)` and the equivalent right-hand Rodrigues rotation about `(cos φ, sin φ, 0)` to Bloch states. `Relax` applies `E1 = exp(-dt/T1)`, `E2 = exp(-dt/T2)`, with equilibrium regrowth only at `Z0`. `Shift` translates `F+` by `+dk` and `F-` by `-dk`; `Z` is unchanged. `GradInterval` applies spatial phase in Bloch/spectral states and advances the shared k-trajectory. `AdcSample` observes the current transverse state and applies NCO demodulation.

## Work safety

Before schedule or backend-state materialization, an arithmetic preflight counts ADC samples and planned operators, then the kernel estimates work as operator count times backend state width: isochromat count for Bloch, `3 × (2*kmax + 1)` for EPG, and isochromat count times pool count for spectral. A sequence is additionally limited to 100,000 channel events and 250,000 ADC samples. The API clamps request `max_work` to `SIM_MAX_WORK=2000000` by default. Legacy `/simulate` still disables magnetization/configuration snapshots because its response does not return them. Canonical `/experiments/run` honors snapshot flags only when the matching product is requested. `SIM_MAX_MATRIX=64` remains the reconstruction/UI dimension cap. Sequence duration is not treated as wall-clock runtime.

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

`diffusion_attenuation` provides the diagonal configuration-space free-diffusion propagator. Classic EPG applies it to transverse configuration orders during free evolution only when tissue ADC is positive and the SequenceIR declares `gradient_units="mt_m"`; ADC with teaching or absent units fails closed. Bloch, hybrid, ssEPG, PDG, EPG-X, and spectral simulation do not apply diffusion. `EpgXLayout` fixes Bloch–McConnell and magnetization-transfer state rows. `apply_bloch_mcconnell` is the two-liquid-pool exchange-and-relaxation free-evolution operator; exchange couples matching orders only. `apply_magnetization_transfer` evolves the four-row free/bound layout: free-pool transverse relaxation, longitudinal relaxation and exchange, with hard RF leaving bound Z untouched. Super-Lorentzian absorption, pulsed off-resonance MT, and CEST remain unavailable.

Floquet, CEST, MRS, and DCE are documented seams only. They have no implementation modules in `packages/mrqlab_experiment`.

## Algorithm references

- Weigel 2015, *Extended phase graphs: dephasing, RF pulses, and echoes—pure and simple* — classic RF, shift, relaxation, and echo semantics.
- Malik et al. 2018, EPG-X — multi-pool exchange/MT layouts and diffusion extension concepts.
- Pruessmann et al. 2021, doi:10.1002/mrm.29101 — configuration-space representation and discrete EPG framing.
- Endres/Möbius et al. 2024, doi:10.1002/mrm.30055 — phase distribution graphs and the future provider-adapter direction.
- Pulseq, PyPulseq, and MaRCoS — event timing and event-stream concepts.
- imr-framework/epg, mriphysics/EPG-X, and pulseq-zero/PDG — numerical/conceptual comparison targets; their source is not vendored or copied.
