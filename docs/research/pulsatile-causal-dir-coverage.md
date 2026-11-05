# Pressure-driven pulsatile flow and causal DIR interruptions

Parent anchor: `3acac6a`. Entry: `pulsatile_dir.run_pulsatile_dir`, available as
`kind='pulsatile_flow'` in the research API and **Pulsatile / causal DIR** in the
Research page. Research/teaching only. No scanner execution, clinical quality
certification, submission material or Milestone B/C promotion is involved.
The existing constant-velocity/known-next-RR experiment remains available.

## Physical model and numerical coupling

The fluid model solves the fully developed axisymmetric Newtonian momentum
balance in a straight rigid circular pipe:

`∂v/∂t = a(t) + ν/r ∂(r ∂v/∂r)/∂r`, with `v(R,t)=0` and centerline symmetry.

`a(t)=[G0+G1 cos(ωt+φ)]/ρ`, where G is **minus** the axial pressure gradient
in Pa/m, ν=μ/ρ, μ in Pa·s and ρ in kg/m³. The steady Poiseuille term plus the
complex Bessel Womersley harmonic gives velocity, cross-section flow rate and
analytic axial displacement. These assumptions and pressure-driven solutions
follow [Womersley (1955)](https://pubmed.ncbi.nlm.nih.gov/14368548/). The pressure
wave is authored, not fitted to a measured pump trace or synchronized to ECG
frequency. Hydraulic initial state is periodic; magnetization starts at equilibrium.

The implementation uses `λ=(1-i)α/√2`, `α=R√(ω/ν)` and the exp(+iωt)
convention. J0/J1 use bounded complex power series for |argument|≤12. Supported
α is 0.02–12. A conservative speed bound gives a Reynolds upper bound; inputs
above the **declared teaching-domain bound of 1000** are rejected. This is an
implementation-domain guard, not a universal transition criterion or physiological
validation. Turbulence and flow instability are not modeled.

Equal-area midpoint radial rings carry fixed radial coordinates and different
axial velocity phases, including possible backflow. Axial quadrature weights
include each ring's actual longitudinal cell length; magnetization averages use
volume weights, not equal spin counts across unequal reservoirs. Analytic bounds
on displacement create a finite upstream/downstream reservoir covering the whole
explicit observation horizon. No equilibrium reinsertion, periodic wrapping,
magnetization reset or fitted inflow fraction occurs. Each receive ring must
contain at least three spins; otherwise the run fails as undersampled.

The existing moving Bloch ensemble now optionally accepts an analytic motion
object. Between RF pulses, the gradient phase uses the **exact integral of
position**, including acceleration. During finite sinc RF, simultaneous RF/Gz
uses midpoint field rotations and symmetric relaxation splitting. Existing
constant-velocity propagation remains unchanged numerically. Initial position
arrays are now copied to prevent external mutation of the ensemble.

The pulse experiment remains a hard nonselective inversion, 8 ms finite sinc
selective reinversion, recovery, 4 ms finite selective excitation and 2 ms
half-area rephaser. Blood T1/T2=1.6/0.15 s and wall=1/0.08 s. Receive sensitivity
is uniform within a top-hat slab. This is a signal experiment, not motion-encoded
k-space imaging or an optimized/adiabatic DIR pulse.

## Causal trigger policy

Input R peaks are already **detected trigger timestamps**. The controller does
not detect ECG or implement vendor firmware. Its declared policy is:

- At each arriving trigger, use the median of up to four past valid RR intervals,
  or the explicit initial RR prior. No next RR enters this scheduling decision.
- Skip a new preparation if the just-observed previous RR is out of range, or
  if latency+TI+window exceeds that past-based estimate.
- A scheduled preparation starts after the declared latency. If another trigger
  arrives before it finishes, stop the current RF/recovery/readout **at that
  arrival time**. Previously executed pulses still affect all later spins.
- The explicit observation horizon may truncate the final cycle. A final trigger
  may also complete without any following R peak.

`scheduled` decisions and eventual `accepted` completion outcomes are separate.
Tests compare decision prefixes under different future trigger suffixes. Tests
also interrupt reinversion at 6 ms, excitation at 905 ms and rephasing at 908 ms;
partial waveform durations and spin state are retained. Prefix decisions do not
use the known future cancellation time, although batch execution records that
later outcome for replay. Removing an aborted preparation changes the later
blood magnetization and is explicitly tested as incorrect behavior.

The older offline experiment selects preparations with knowledge of the next RR.
It is a useful contrasting model; its historical "retrospective" label should
not be interpreted as a full continuously acquired retrospective cine method.
The new controller is a research policy, not an arrhythmia safety algorithm.

## Design targets and honest failures

Targets use **completed** readouts: max blood |mean Mz|≤0.1, min wall |mean Mz|≥0.7,
and interrupted preparation fraction≤the declared bound (default zero). At least
one completed readout is required. No-readout runs report failure and no invented
blood/wall measurements. Their explicit optimization penalty is 2+interrupted
fraction; other runs minimize mean blood/wall |Mz| ratio plus interrupted fraction.
A grid-selected design may still fail its targets.

| Case | Completed / scheduled | Interrupted fraction | Max blood abs(Mz) | Min wall abs(Mz) | Targets |
|---|---:|---:|---:|---:|---|
| Backend default, triggers 0/1.2/2.4, horizon 3.6 s | 3 / 3 | 0 | 0.406226 | 0.577562 | FAIL |
| UI example, triggers 0/0.45/1.65, horizon 2.8 s | 1 / 2 | 0.5 | 0.274893 | 0.689141 | FAIL |
| Trigger 0, horizon 0.5 s | 0 / 1 | 1 | unmeasured | unmeasured | FAIL |

The 0.45-second trigger interrupts the first preparation and skips its own new
preparation due to the short observed RR. The 1.65-second trigger schedules and
completes a readout with no following R peak. These model failures are preserved
in the frontend, source-pinned API replay and saved evidence.

## Independent verification and replay

[Saved numerical evidence](examples/pulsatile-dir-evidence.json) contains the full
regular, irregular, no-readout, quadrature-refined and partially clipped runs,
plus source/dependency manifest, environment, script hash and all replay inputs.

```sh
uv sync --locked --extra dev --extra noncartesian
python scripts/verify_pulsatile_dir.py --output /tmp/pulsatile-dir-replay.json \
  --verify docs/research/examples/pulsatile-dir-evidence.json
```

An independent process recomputed and exactly matched the entire evidence file.
Existing historical TSE and NUFFT example records keep their original source
anchors (`3b518f5` and `3acac6a`); they are not relabeled as current-source results.

Independent checks include complex Bessel integral quadrature, Poiseuille profile
and flow rate, a separate finite-volume harmonic momentum solve, exact motion
integrals checked by quadrature, and an independently coded RK4 Bloch ODE.
Finite-volume velocity relative errors at 32/64/128 cells were **4.079e-4,
1.020e-4, 2.550e-5**, showing second-order convergence to the analytical profile.
The Bloch RF check likewise tests second-order time refinement. Cross-section
quadrature converges to the analytic volumetric flow, including reversed flow.

Single-trigger MR volume/RF refinement, horizon 1.2 s:

| Radial rings / axial spins per ring / RF samples | Blood mean Mz | Wall mean Mz | Target |
|---|---:|---:|---|
| 4 / 201 / 128 | -0.072191 | 0.655434 | FAIL |
| 8 / 401 / 128 | -0.062386 | 0.655412 | FAIL |
| 16 / 801 / 256 | -0.062761 | 0.655445 | FAIL |

This is measured refinement agreement for this case, not a universal spin-grid
error bound. Partial RF and geometry sampling still require checking per design.
Budgets preflight the total ring/axial spin counts, all scheduled preparations,
RF steps and final wait before allocation. Actual work charges aborted intervals
and every spin operation; finite RF energy is integrated over the executed
waveform only. These are work/energy proxies, not SAR, wall time or hard RSS caps.

## Integration verification and remaining gaps

Full locked-environment Python suite: **719 passed**, one existing Starlette/httpx
warning. Frontend: **97 passed** in 14 files; TypeScript and production build pass.
Real production-browser flow: new entry → execute irregular example → failed
measurements and causal decision table → exact result-hash replay. The no-readout
case was also verified in the browser with no fabricated blood/wall values.
Native download/upload was not retested. The old static preview handle was
confirmed missing before its saved production directory was served again.

Remaining: compliant or branching vessels, radial/transverse transport, general
3D CFD, respiratory/tissue deformation, measured pressure/velocity calibration,
non-Newtonian or turbulent regimes, diffusion, full readout trains and motion-
encoded image reconstruction, actual ECG detection and validated controller
policies. Cross-modality measured-study persistence and robust clinical target
translation remain incomplete. The full platform goal remains active.
