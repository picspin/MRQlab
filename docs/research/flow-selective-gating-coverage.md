# Through-plane motion, finite slice RF and trigger timing

Parent: `9664125`. Entry: `flow_imaging.run_flow_imaging`, with
`search_flow_timing` for an explicit finite TI grid. Research/teaching only;
no scanner validation or clinical quality certification; B/C remain parked.

| Existing evidence | Missing link | Extension |
|---|---|---|
| `family_execution.simulate_family`: SSFP DIR resident/incoming mixture | Positions never change; fixed inflow_fraction at readout | Persistent Lagrangian spins at `z(t)=z0+v*t` with a finite upstream reservoir |
| `ssepg_engine._profile`: static finite sinc RF and Gz | Static profile disconnected from moving spins | Simultaneous RF/Gz/velocity/relaxation field rotation |
| Bloch backend, `rotate_cartesian`, `relaxation_factors` | No measured trigger or accepted-cycle schedule | Actual R-peak timestamps, RR rejection, explicit windows and reasons |
| Existing recipe/search/provenance patterns | No TI search using moving spins | Every TI executes the complete propagation, with objective, targets and replay |

This is a new research experiment, preserving existing fixed-mixture SSFP
semantics. It does not promote milestones or claim to be a scanner sequence.
The DIR mechanism is established, e.g. the original
[multislice DIR study](https://pubmed.ncbi.nlm.nih.gov/11870851/);
this implementation has no clinical validation against that study.

## Propagation and design

A hard nonselective inversion is followed by a finite 8 ms sinc selective
reinversion with simultaneous physical Gz. At accepted trigger+TI, mean Mz is
measured over the receive slice, then a finite 4 ms selective 90° pulse and 2 ms
half-area gradient rephaser generate a separately reported complex signal.
Sinc area sets the on-resonance flip; the profile is computed by propagation,
not a binary slab inversion. It is not an adiabatic or optimized inversion.
Nonselective hard inversion has a separate relative flip-energy proxy; finite
RF reports uT²s. These proxies do not estimate SAR or hardware safety.

Constant prescribed velocity is a physical trajectory, not a solved velocity
field. Spins retain magnetization across all accepted cycles; no wrapping,
reset, fitted mixture or new equilibrium spin insertion occurs. The initial
reservoir spans all positions that can enter the receive slab by final readout.
Uniform receive sensitivity inside a top-hat slab is a measurement assumption,
not the RF excitation model. Each readout includes actual positions/state
hashes, spin count and geometric incoming fraction, separately from RF response.

Non-RF intervals integrate the constant-velocity gradient phase exactly.
RF intervals use midpoint field rotation with symmetric relaxation splitting.
Tests compare to an independently implemented RK4 ODE at 4096 steps and verify
second-order convergence at 32/64/128 RF steps. Analytic gradient phase,
longitudinal inversion recovery, finite off-slice profile and spatial/RF grid
convergence are independent checks, not self-replay alone.

Gating is **retrospective known-trigger acceptance**: each actual next RR must
be within the declared range and contain the full TI/readout window. The last
R peak has no known next RR and is rejected. This is not a prospective trigger
predictor, ECG detector or arrhythmia safety algorithm. Rejected cycles have no
preparation pulse in this model; their waiting interval still evolves existing
spins. Signal history persists through accepted and rejected time intervals.

```python
from mrqlab_experiment.flow_imaging import run_flow_imaging, search_flow_timing
r = run_flow_imaging()
assert run_flow_imaging(**r['provenance']['replay']) == r
search = search_flow_timing([.6, .9, 1.1, 1.3], r_peaks_s=[0., 1.2])
```

## Measured targets and honest failures

Default TI 0.9 s, triggers 0/1.2/2.4 s, blood velocity 0.025 m/s, slice 5 mm,
801 spins per tissue, 128 samples per RF pulse. Blood T1/T2=1.6/0.15 s;
wall=1/0.08 s. Declared teaching targets: all accepted readouts must have
`abs(mean blood Mz)<=0.1` and `abs(mean wall Mz)>=0.7`.

| Velocity m/s | First/second blood Mz | First/second wall Mz | Mean blood/wall magnitude ratio | Targets |
|---|---|---|---:|---|
| 0 | 0.518028 / 0.423818 | 0.655407 / 0.581596 | 0.759554 | FAIL |
| 0.005 | -0.109623 / 0.399759 | same | 0.427305 | FAIL |
| 0.025 | -0.139467 / 0.398719 | same | 0.449178 | FAIL |

Flow changes suppression; repeated nonselective inversions and finite RF profile
prevent treating every cycle as freshly equilibrated ideal DIR. The default
**fails** its targets and is intentionally tested as failed. Single-cycle blood
at 0.025 m/s agrees with `1-2*exp(-TI/1.6)` to 5e-4. Single-cycle grid search
selects 1.1 s among 0.6/0.9/1.1 s, while 1.3 s has no accepted cycle. A selected
feasible candidate is not automatically target-passing. No optimum or clinical
protocol guarantee is implied.

Budget preflight bounds spins × RF steps × tissues × accepted cycles before RF
allocation. Actual work counts every spin interval/hard rotation; duration
includes trigger waiting. Search retains infeasible candidates with reasons
and returns `best=None` if all fail. Every result contains all replay inputs,
source hash, waveform hash, state/position hashes, explicit targets and loss.
Tests cover full replay and model effects in addition to independent references.

## Remaining gaps

A later [pressure-driven pulsatile/causal extension](pulsatile-causal-dir-coverage.md)
adds accelerating trajectories and rigid-pipe radial velocity profiles. General CFD,
respiratory/tissue deformation, velocity distributions from measurements,
prospective gating, optimized inversion, diffusion during motion, readout trains
and motion-encoded image reconstruction remain absent. The model is one-dimensional
through-plane propagation; the receive slab excludes spins physically outside it.
Grid sampling and finite RF errors remain measurable. No inference of patient
blood flow, scanner pulse export, clinical calibration or quality certification.
Frontend entry remains the later backlog phase. Inherited submission materials
were not modified or newly added.

## Full validation

19 new cases in `tests/experiment/test_flow_imaging.py`; complete Python suite
**583 passed**, one existing Starlette/httpx deprecation warning. Frontend
`npm test -- --cache=false`: **82 passed** (12 files); TypeScript
`npx --no-install tsc --noEmit`: passed; staged diff whitespace check: passed.
Existing shared virtual environment and ignored dependency symlink only.
