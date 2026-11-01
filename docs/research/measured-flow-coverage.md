# Velocity measurements → conditional pressure → finite-RF causal DIR

Continuation of `fdbad1c`. The new `/research/flow-study` entry consumes declared
velocity measurements rather than silently treating an authored pressure waveform
as measured. It uses the existing finite-slice RF, persistent moving Bloch state
and causal detected-trigger DIR runner. This is a conditional research model,
not patient pressure inference, an image-based 4D-flow reconstruction, scanner
validation or clinical quality certification. Milestones B/C remain parked.
There are still twelve general research runner kinds.

## Measurement and physical contract

CSV columns are exactly `measurement_id,acquisition_id,split,time_s,radius_m,velocity_m_s,std_m_s`.
Times/positions/velocity/standard deviations use SI. `split` is `calibration` or
`holdout`; measurement IDs must be unique and acquisition IDs disjoint between
splits. Each split needs at least six rows at three distinct times. Input is
bounded to 256 rows and 1 MB of UTF-8 CSV; BOM and CRLF bytes are preserved.
The archive retains exact base64 bytes, their SHA256, parsed rows, source reference
and user-declared measured/synthetic origin. Hashes establish integrity, not
authenticity. Manually supplied structured rows may omit the byte archive, which
is then explicitly reported as absent. Mutating rows while retaining an
inconsistent archive is rejected before execution.

The conditional forward model is the existing straight rigid circular Newtonian
pipe, following the periodic pressure/velocity model in
[Womersley's original paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC1365740/).
Radius, density, viscosity, frequency and absolute clock alignment are explicit
priors. The pressure convention is positive `-dp/dz`, in Pa/m:

`G(t) = G0 + Gc*cos(omega*t) + Gs*sin(omega*t)`.

The harmonic complex forcing is `Gc-i*Gs`; magnitude/phase sent to the physical
runner are `hypot(Gc,Gs)` and `atan2(-Gs,Gc)`. The velocity-space design matrix
uses the steady unit-pressure response and the real/imaginary harmonic response.
Only calibration rows enter weighted linear least squares. Complete covariance
is `(A' W A)^-1` for the declared independent known-sigma Gaussian errors; it is
computed with SVD and never multiplied by the fitted residual variance. Lossless
parameter-column scaling improves conditioning; no signal/image gain, reference
map, regularizer or hidden amplitude calibration is fitted. Rank deficiency or
scaled condition above 1e6 fails with no invented pressure coefficients.

Checks separately gate calibration chi-square/(n-3), holdout maximum absolute
standardized residual, holdout chi-square/n, relative pressure uncertainty and
the existing physical Reynolds/Womersley domain. Failed calibration or holdout
prevents every MR simulation and produces no pressure binding or preview.
Blood/wall T1/T2, RF family and trigger timestamps remain authored priors.

## Candidate computation and retained failures

Each TI candidate executes nominal pressure plus eight corners of the three
marginal coefficient intervals. Default intervals are mean +/- two standard
errors. The complete covariance is retained; these rectangular stress corners
are **not** a joint confidence region or a continuous robustness guarantee.
For every pressure case, the existing runner executes both authored and refined
RF/radial/axial grids. Refinement doubles RF steps and rings and maps axial n to
2(n-1)+1. Complete causal gates must match, and each real component of blood/wall
Mz and complex signal is compared across every complete readout. Default maximum
absolute observation difference is 0.01. All physical targets must also pass on
both grids and every case. No completed readout fails numerical validation.

The total budget reserves two full per-simulation caps for every pressure case
and candidate before MR begins. Failed attempts retain completed partial runs
and conservatively charge the full cap for the failed attempt. Memory is an
explicit conservative allocation estimate, not an operating-system memory limit.
All failed/infeasible cases and reasons remain in the output. Eligible selection
minimizes the worst refined objective among the declared finite candidates; when
none qualifies, `selected_index` is null. A nominal fine-grid preview is labelled
unselected and never promoted to a verified design.

## Reproducible numerical evidence

The [plan](examples/measured-flow-plan.json) embeds the exact **synthetic** CSV:
16 calibration and 16 holdout velocity samples at two radial locations, distinct
acquisition IDs, known sigma 0.001 m/s and a holdout time offset of 0.037 s. No
real patient or scanner dataset has been supplied. True pressure coefficients
are `[100, 193.78248434212895, -49.48079185090459]` Pa/m. Recovery is within 2e-12;
standard errors are `[0.98994949, 2.34727682, 2.34727682]` Pa/m. The tiny noiseless
residual does not collapse the known-sigma covariance to zero. Doubling all
declared measurement standard deviations leaves coefficients unchanged and
multiplies the complete covariance by four.

An independent radial finite-volume momentum solve, with no Bessel/analytic
velocity generator, supplies calibration and holdout velocities at cell centers.
At 64/128/256 cells, maximum coefficient errors are respectively **0.00978554,
0.00246343, 0.000617982 Pa/m**, converging at approximately second order.

The default 8-ring/401-axial/128-RF-step grid and its 16/801/256 refinement execute
all 36 simulations, with 430,412,708 estimated work, 1,800,008,192 reserved work
and 15,123,456 estimated peak allocation bytes. Calibration/holdout pass, and all
18 candidate-pressure numerical checks pass. The physical DIR targets still fail:

| TI (s) | Worst refined blood abs(Mz), limit 0.1 | Worst refined wall abs(Mz), minimum 0.7 | Maximum observation difference, limit 0.01 | Selected |
|---|---:|---:|---:|---|
| 0.6 | 0.36107420 | 0.44918533 | 0.0037837644 | No |
| 0.9 | 0.46642521 | 0.56859525 | 0.0030948388 | No |

The underresolved 4/201/32 case retains maximum observation difference
**0.01521136**, failing the same 0.01 gate. Corrupted independent holdout,
unidentifiable wall-only velocities and insufficient total budget run no MR
cases. None receives an invented selected design.

## Records and delivery

`measured_flow` uses the existing immutable `mrqlab-scientific-record-1` envelope,
SQLite store, lossless request/payload strings and source/runtime-pinned complete
computational replay. Seven chained stages retain question → raw velocity data →
source/runtime → conditional calibration → design/inputs → complete execution →
reported validation. Every coarse/refined pressure case retains readout signals,
positions/state hashes, gate history, physical parameters and numerical outcomes.
Reading/importing a record reports integrity only; full replay recomputes the
whole chain. Raw-byte archive consistency is rechecked on record verification.

`scripts/verify_measured_flow.py` creates the default record, independent momentum
reference and failed measurement/numerical/budget cases. Independent processes
produce identical complete evidence. The current evidence is
[measured-flow-evidence.json](examples/measured-flow-evidence.json).
Default scientific record SHA256:
`8091518e480208a74abd2b942fb654bd8ca7feeb95026a55d4a06426c73069a2`;
payload SHA256:
`376df454d1a71364c5bdfab6c221ffc2e882bf58d097d57a0696bca61c28df20`.
Full raw/output records and logs remain outside the project in
`/private/tmp/mrqlab-measured-flow-fdbad1c/`.

Regression is **977 Python passed** (one existing Starlette warning), **124
frontend passed** in 17 files, TypeScript passed and production build passed.
The 23 new backend cases include an independent finite-volume reference, full
archive consistency, known-sigma covariance, holdout isolation, reservation and
failed-attempt charging, all pressure corners and full shared-record replay.
Seven frontend cases cover source declaration, failure separation, stale-response
discard, complete typed execution and replay errors.

Native browser evidence traversed `/research/flow-study` → example API → actual
CSV download → file chooser re-import → calibration/candidate API → isolated
SQLite save → complete recalculation → actual record download → shared-record
file chooser re-import → complete recalculation. The downloaded 2,697-byte CSV
has SHA256 `d8ba61a1e9c751aa593e88ba43b70008ea02db9e3cc8d672f910098a8fc505f0`,
matching the retained archive. Both actual records retain identical complete
payload SHA256 `376df454d1a71364c5bdfab6c221ffc2e882bf58d097d57a0696bca61c28df20`.
The browser has a different study ID/context snapshot, so its record SHA256 is
`8330a7235c7d80e8424cb87868fe81b6a2d4eced1b522b84606806ee2e9da8b5`.
Import initially reports integrity only; only completed computation changes the
library to “已重算且一致”. Source and runtime pins remain enforced. All observed
API requests succeeded and the final browser error/warning log was empty.

The production export includes `/research/flow-study`. Native interaction used
the project Next server: Python's ordinary static file server does not resolve
the export's extensionless routes. There was no project routing change to hide
that serving mismatch. The final full-page screenshot is retained outside the
repository as `measured-flow-native-replay.png` under this task's visualization
directory. This verifies the CSV and shared-record boundaries for this declared
synthetic case; it does not establish other modalities' native CSV coverage.

## Remaining gaps

This closes a conditional velocity-to-pressure-to-DIR signal workflow, not joint
MR image/velocity/pressure inference. There is no measured image reconstruction,
velocity alias/phase/background calibration, moving transverse anatomy,
compliant/general 3D flow, correlated measurement errors, geometry/viscosity/clock
inference or uncertainty on RF/T1/T2 priors. No actual lab measurement has yet
been independently authenticated or compared with this model. The default
physical targets fail. Current limits remain explicit and unchanged.
