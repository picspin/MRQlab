# Causal flow, slice RF and motion-encoded EPI

This extends `71f2f4d` with an actual acquired-image chain, available as
`kind="flow_epi"` and **Flow / encoded EPI** in `/research`. The earlier
pressure-driven signal experiment remains unchanged. This is a synthetic,
authored-pressure teaching/research experiment, not measured hemodynamics,
scanner execution, clinical quality certification or a patient recommendation.
The two Milestone A catalog entries remain unchanged; B/C remain parked.

## Physical chain and stated boundaries

The existing rigid-pipe Newtonian Womersley solution provides radius-dependent
through-plane trajectories, including acceleration/backflow. Transverse positions
are fixed at a Cartesian phantom's voxel centers: blood inside the pipe and a
stationary 1 mm wall annulus outside. Blood T1/T2=1.6/0.15 s and wall=1/0.08 s
remain authored. Each voxel has a finite, bounded upstream/downstream axial
reservoir covering the observation horizon. Spins retain all prior state: no
wrapping, equilibrium reinsertion, magnetization reset or fitted inflow mixture.

DIR applies the existing ideal hard nonselective inversion, finite 8 ms sinc
selective reinversion, recovery, finite 4 ms selective excitation and 2 ms
slice rephaser. Then opposite-polarity bipolar flow encoding and a finite-ramp
Cartesian EPI train act on the **same evolving spins**. Every gradient hold
propagates off-resonance, T2 decay and exact analytic axial position integral;
fixed xy phase is added with the physical gradient area. Finite RF still uses
the independently tested midpoint field rotation/relaxation scheme. Overlapping
RF and transverse gradients is explicitly unsupported.

The receiver is a uniform top-hat slab. Axial cells contribute their actual
geometric intersection length with the receiver, divided by the declared slab
thickness. Boundary cells are included fractionally. This fixes point-center
counting's receive-volume error without fitting a normalization to observed
signal. A constant state integrates to the same declared volume as the cells
translate. There must be at least three contributing cells per active voxel.
Magnetization/phase remains evaluated at cell centers, so RF/axial refinement
is still required. In-plane circular boundaries are sampled at voxel centers;
they do not have exact continuous cross-sectional area.

Gradient commands approximate finite linear ramps by midpoint sample-and-hold
steps. The actual sampled first moment sets the encoding amplitude, and actual
integrated xy area sets each Cartesian ADC coordinate. The convention is
`k_xy=-gamma_bar*integral(G_xy dt)`, consistent with the project's negative-sign
Fourier acquisition; axial motion phase is `+gamma*integral(Gz*z dt)`.
Reception sums physically encoded transverse spins. It does not apply a second
Fourier phase. Reconstruction is an unscaled centered inverse FFT of complete
measured k-space, with no reference image, support constraint or image gain fit.

The default 16×16, 12 mm FOV design has 60 microsecond point-ADC spacing,
two 2 ms flow-encoding lobes, and 36 ms total encoding/EPI waveform duration.
Excitation/rephasing adds 6 ms to the controller's readout window. Default
gradient quantities are:

| Quantity | Value |
|---|---|
| Pair differential first moment | 2.3486594917442797e-7 T·s²/m |
| VENC | 0.05 m/s |
| Peak encoding/readout gradient | 0.034539110172709955 T/m |
| Nominal finite-ramp slew | 115.13036724236652 T/m/s |
| Complete readout samples | 256 |

The declared design limits are 0.04 T/m and 150 T/m/s. These check nominal
encoding/readout ramps, **not** all hardware switching: slice-gradient edges,
hard RF and immediate command cutoff on an interrupt remain idealizations.
No hardware abort ramp, eddy current, delay or PNS/SAR certification is modeled.
ADC values are instantaneous dwell-boundary samples, not integrated receiver
bandwidth/aperture averages. The gradient/phase concepts have primary precedents
in [Moran (1982)](https://pubmed.ncbi.nlm.nih.gov/6927206/) and
[Butts and Riederer's EPI flow analysis](https://pubmed.ncbi.nlm.nih.gov/1627863/).
Their studies do not validate this implementation or its authored priors.

## Causal completion, partial acquisitions and phase interpretation

The existing controller schedules from already detected triggers and previous
RR history. The new full excitation/encoding/EPI duration participates in that
decision. Encoding polarity alternates by scheduled preparation index, independent
of future completion. A later trigger or observation horizon clips the currently
executing RF/gradient interval at that time. Executed spin state, command prefix,
partial-interval duration, RF/gradient energy proxies and acquired ADC values
remain recorded and affect subsequent preparations.

An interrupted acquisition retains its actual samples but produces no complete
k-space/image: missing samples are not zero-filled. A complete image alone
produces no velocity measurement. Only adjacent complete opposite-sign images
form an encoding pair; their trigger IDs and different encoding times are stored.
If a preparation was skipped/interrupted, pairing never invents its opposite.

Velocity uses `angle(I_plus*conj(I_minus))/(gamma*delta_M1)` only where both
measured magnitudes exceed the declared numerical signal floor. The validity map
is displayed separately; stored zeros outside it are **not** measured zero flow.
There is no phase unwrapping to match the simulation reference. Anatomical masks
are used only for reported phantom ROI error/flow evaluation, not for image
reconstruction or the magnitude-derived validity decision.

The gradient-moment reference integrates the two actual bipolar windows along
the analytic trajectories. It is generally different from the velocity at the
mean clock time. Both references and the continuous instantaneous pipe flow
are retained. For the default pair, encoding starts near 0.909/2.109 s; the
moment-reference grid flow is 3.10413e-7 m³/s while instantaneous analytic flow
at their mean time is 2.97204e-8 m³/s. They must not be relabelled as the same
quantity. Preparation state, finite slice RF, low/negative signal and EPI
evolution can also invalidate a simple phase-velocity interpretation.

## Explicit failed targets and controls

Targets require a complete pair with all phantom blood voxels observable,
velocity RMSE <=0.002 m/s against the moment reference, complex image NRMSE
<=0.05 against a frozen post-encoding/pre-EPI snapshot, blood |Mz|<=0.1,
wall |Mz|>=0.7, and interrupted fraction <=0. Known reference speeds exceeding
VENC also fail simulation validation; this is not a clinical alias detector.

| Case | Images / pairs | Velocity RMSE (m/s) | Complex frozen-image NRMSE | Blood max abs(Mz) | Wall min abs(Mz) | Combined targets |
|---|---|---|---|---|---|---|
| Default pulsatile DIR | 2 / 1 | 0.04820858 | 0.20250200 | 0.39870918 | 0.58154581 | FAIL |
| Steady no-DIR control | 2 / 1 | 0.00024026 | 0.16799727 | 1.00000000 | 0.70872448 | FAIL |
| Trigger interrupts EPI at 0.917 s | 0 / 0 | unmeasured | unmeasured | unmeasured | unmeasured | FAIL |
| Single complete image | 1 / 0 | unmeasured | 0.19215765 | 0.13880689 | 0.65526047 | FAIL |
| Horizon 0.5 s | 0 / 0 | unmeasured | unmeasured | unmeasured | unmeasured | FAIL |
| Steady no-DIR, pressure 400 Pa/m | 2 / 1 | 0.07202223 | 0.30737928 | 1.00000000 | 0.70871371 | FAIL / alias |

The no-DIR control verifies useful phase-encoding behavior under its own steady
conditions; it does not satisfy the DIR suppression or frozen-image targets and
is not substituted as an optimized DIR design. Its measured grid flow is
1.83962e-7 m³/s versus moment-reference grid flow 1.83817e-7 m³/s. Continuous
analytic pipe flow is 1.79520e-7 m³/s: finite in-plane center quadrature remains
visible rather than being rescaled to agree.

The [recorded finite search](examples/flow-epi-plan.json) preserves executable
TI=0.6/0.9 s failures and a 10 microsecond dwell candidate rejected by nominal
gradient limits. **No best design is selected.** Search varies only TI, VENC and
dwell; pressure, preparation control, targets, quadrature and gradient limits
cannot change through candidate patches. Separate sensitivity/control runs remain
available, with their inputs and outcomes explicit.

## Independent checks, refinement and replay

All 256 complex ADC values for independent constant-velocity spins match a
separately written Cartesian Bloch exponential to maximum absolute error
**2.59184e-14**. Tests independently integrate actual gradient moments and
Cartesian coordinates, check acceleration phase with successively refined time
quadrature, and reconstruct images with a direct inverse Fourier sum. Existing
finite-volume Womersley and RF RK4 checks continue to pass. Geometric receive
volume tests translate cells without any post-reception normalization. Prefix
tests verify causal decisions/polarity; partial/no-pair and alias cases remain
explicit failures.

Joint RF/axial/ramp refinements keep the default failure:

| Axial cells / RF samples / ramp holds | Velocity RMSE (m/s) | Frozen-image NRMSE | Work proxy |
|---|---|---|---|
| 201 / 64 / 8 | 0.04821187 | 0.20221330 | 36,146,041 |
| 401 / 128 / 8 | 0.04820887 | 0.20250809 | 76,666,561 |
| 801 / 128 / 16 | 0.04820768 | 0.20258336 | 231,510,481 |

These are combined refinement observations, not separate universal error bounds.
Offline refinement explicitly allows 400 million work units. The API remains
capped at 200 million per run; the finest case's planned 236,917,231 work exceeds
that API limit and is not presented as an API-feasible experiment. The default
run uses 72,047,041 under planned 73,598,911, with estimated peak retained memory
9,920,512 bytes under 128 MiB. Budgets/energy are planning proxies, not hard RSS,
wall-time containment or scanner safety values.

The [compact evidence](examples/flow-epi-evidence.json) retains complete input,
run/image/k-space/actual-command/sample/final-state hashes, controls, refinements,
source/runtime and verifier hash. Reproduce with new output paths:

```sh
.venv/bin/python scripts/verify_flow_epi.py \
  --verify docs/research/examples/flow-epi-evidence.json \
  --output /tmp/flow-epi-evidence.json --record-output /tmp/flow-epi-record.json
.venv/bin/python -m mrqlab_api.scientific_records --store /tmp/flow-epi.sqlite3 \
  import /tmp/flow-epi-record.json
.venv/bin/python -m mrqlab_api.scientific_records verify /tmp/flow-epi-record.json
.venv/bin/python -m mrqlab_api.scientific_records --store /tmp/flow-epi.sqlite3 \
  replay /tmp/flow-epi-record.json --output /tmp/flow-epi-replayed.json
```

`import`/`verify` check integrity only; the evidence script and `replay` actually
recompute physics and every failed/infeasible candidate. The complete scientific
search record is **1,584,821 bytes**, ID
`d8d102a7ebd8693c9e424c97be548418b1508b50c7b77caee3c0203717ef0e23`, payload
`1b2e644ff38dc1ab45f6e192d662c2c2b78049b64ae9a36473e88c6db212c51b`.
It and build artifacts are outside source at
`/private/tmp/mrqlab-flow-epi-71f2f4d-20261030/`. Independent evidence recomputation
and a new-process generic CLI replay match the complete record byte-for-byte.
Actual HTTP/CORS create/read/export/import/full replay on local port 8009 also
match both identities. HTTP additionally verifies that the interrupted case
retains exactly **30/256** samples without an image or invented velocity.

## Product entry, verification and remaining requirements

The tenth research entry exposes timing, VENC and dwell, physical limits, the
failed targets, causal decision table and actual ADC counts/stopping stages.
Magnitude/frozen reference, phase, velocity, moment reference and measured-validity
images use separate physical-quantity groups and explicit units. Same-group
references share color scales. No-image and missing-pair states are distinct.
All outputs use the existing immutable scientific run/search store and complete
source/runtime-pinned replay, with no new clinical catalog route.

Final full regression after the receive-geometry correction: **881 Python
passed**, one existing Starlette/httpx warning; **114 frontend passed** in 16
files; TypeScript and production build passed. Generated build outputs were
preserved outside source and restored without `git clean`. Earlier committed
scientific examples and original handoff scratch/notes were not regenerated or
removed. A fresh browser inventory still reports **The browser access host is
unavailable**. Rendered browser clicking, visual inspection and native file flows
remain unverified; component/HTTP checks do not close that boundary.

Remaining: measured pressure/velocity/relaxation calibration, compliant/branching
or general 3D flow, transverse transport/deformation, intravoxel velocity spread,
coils/noise/field maps, realistic receiver sensitivity, full gradient/RF switching
and abort ramps, delays/eddy currents, ADC aperture, acquisition/phase calibration
and uncertainty propagation, better DIR/readout designs and validated temporal
flow estimation. Current combined targets fail; no target was relaxed or image
rescaled to manufacture success. Earlier CEST/MRS and platform-level gaps remain.
The full goal stays active. No push, PR, merge, B/C unlock, submission import,
production-router change or project-folder relocation was performed.
