# Finite-memory CEST / semisolid MT / Solomon relay

This continuation of `de9cdb3` adds the eleventh research kind,
`cest_memory`, through the existing run/search and scientific-record paths.
It addresses finite shaped RF near semisolid resonance, including zero offset.
The default design and the complete finite search fail their combined targets;
no design is selected. This is homogeneous teaching/research simulation with
authored priors, not measured molecular calibration, a scanner implementation,
clinical image-quality certification or permission to unlock Milestones B/C.

## Model and numerical boundary

The approach follows the time-domain Green-function formulation in
[Assländer et al., Generalized Bloch model: a theory for pulsed magnetization
transfer](https://pubmed.ncbi.nlm.nih.gov/34811794/). Our implementation couples
liquid Cartesian Bloch/exchange states, the existing signed longitudinal Solomon
pair/bridge relay and one common semisolid longitudinal reservoir. The semisolid
RF term is a complex Volterra convolution; it retains the carrier phase and all
previous pulse/gap intervals. There is no lag cutoff or inter-pulse reset.

For the super-Lorentzian case the real FID kernel is
`G(t) = integral_0^1 exp[-(t/T2)^2 (3u^2-1)^2/8] du`. It has `G(0)=1` and a
resolved magic-angle neighborhood at long lags. The orientation integral is
split at `1/sqrt(3)`; omitted tails have integrand at most `exp(-64)`.
The implementation does not turn a divergent zero-frequency absorption rate
into a finite rate. The older canonical absorption-rate model still rejects
its singular zero-offset case; it is not silently replaced or clamped.
Lorentzian and Gaussian *time-domain* kernels are explicit selectable models.

Each piecewise constant complex RF hold uses linear longitudinal-state product
integration, implicit endpoint self-memory and affine Crank–Nicolson evolution.
RF acts directly on the liquid states and only through the memory integral on
the bound reservoir. The old generator is called with zero RF, so its canonical
absorption-rate function is never evaluated. Bound exchange assumes short
transverse coherence, with the explicit guard `k_bound_to_water * T2_bound <= .01`.
This common-Z model does not include coherent liquid/bound transverse exchange,
full molecular Redfield relaxation, spatial imaging or measured T1/PD calibration.
Negative bound Z during a short hard pulse is retained rather than clipped.

Default RF is four 20-ms sampled-Hann pulses, 40-ms gaps, 16 amplitude bins and
24 integration substeps per bin: **3,840 coarse / 7,680 refined intervals over
0.2 seconds**. The same authored RF holds are subdivided for refinement; the
waveform does not change. Gap boundaries must lie on the declared uniform grid.
The 0.04001-s candidate fails that alignment check rather than being rounded.
Pulse phase changes survive into subsequent pulses through the full history.
Peak normalization belongs to the authored RF waveform; no signal gain is fit.

Every offset and all five controls (`full`, `no_cross`, `no_bridge_exchange`,
`no_amide`, `no_mt`) run at both resolutions. The numerical gate compares water
Z and bound Z divided by the authored bound density at **every aligned time
node**, not merely at the displayed trace samples or final state. Records keep
the maximum-error time/channel/values and full-state history hashes; replay
recomputes all nodes. Display traces retain about 256 uniform nodes plus RF
changes, and the complete RF holds remain in provenance. Lag-cell kernel weights
also receive independent time/orientation refinement, 32 to 64 quadrature nodes.

The seven offsets stay `[-5, -3.5, -2, 0, 2, 3.5, 5]` ppm. Coarser integration
failed at the larger offsets; they were not dropped to claim convergence.
The explicit API work allowance is 32 billion proxy units. Each default run
plans **21,518,491,300**, executes **9,130,897,060**, and estimates a peak
**69,160,328 bytes**, under the unchanged 128-MiB memory allowance. These are
documented allocation/work proxies, not OS-level hard containment or timing
guarantees. Per-train RF energy is the search objective; complete modeled
control/offset duration and energy are separately recorded.

## Preserved results and failures

Targets remain amide and signed relay contrasts at least **0.005**, maximum
normalized full-trace refinement difference at most **0.0002**, kernel-weight
error at most **1e-6**, and unsaturated water within **1e-8** of one. RF-only
search cannot vary molecular/lineshape priors, numerical grids, targets or budgets.
Only a candidate passing every gate can qualify for minimum-RF selection.

| Peak B1 (µT) | Amide contrast | Signed relay contrast | no-MT difference at zero | Full-trace error | Numerical gate | Overall |
|---|---:|---:|---:|---:|---|---|
| 0.5 | 0.0042530162 | 0.0007818188 | 0.0082152314 | 0.0000309813 | PASS | FAIL |
| 1.0, default | 0.0100522612 | 0.0025574892 | 0.0653537191 | 0.0001184018 | PASS | FAIL |
| 2.0 | 0.0079805610 | 0.0054934737 | -0.0153269507 | 0.0003887770 | FAIL | FAIL |
| gap 0.04001 s | — | — | — | — | infeasible timing | no result |

Kernel error is `8.584913554117633e-16` for the three executable points;
unsaturated water is `1.0000000000004652`. The 2-µT design meets both contrast
thresholds but fails numerical convergence and is excluded. The full search has
`selected_index: null`, not an invented best design.

Four substeps per RF bin give full-grid error **0.0008042390** and fail the same
numerical gate. Separate three-offset controls retain a fast-correlation-time
relay contrast **-0.0001454090**, exactly zero relay contrast when bridge exchange
is disconnected, and a `[0, pi/2]` phase-cycled zero-offset no-MT difference
**-0.0082262992**. These signed conditional differences are not clipped,
additive isolated biomarkers or clinical concentrations. Changing one pathway
changes the coupled system, so its control difference may have either sign.

Independent references include direct orientation quadrature and the long-lag
limit `sqrt(2*pi/3)*T2/t`: at `t=1 s`, `T2=1e-5 s`, the kernel is
`1.4472025093320162e-5` versus `1.4472025091165353e-5`. A Lorentzian kernel
reduces to an independently assembled augmented **19-state Bloch matrix
exponential**, including complex RF, detuning, liquid exchange and the signed
relay. Final-state errors for 128/256/512 intervals are
`2.48561684e-5`, `6.21416209e-6`, `1.55354805e-6`, demonstrating second-order
refinement for that reference. A 10-ns pi pulse with `T2=1e-5 s` produces bound
`Z=-0.9999999544231916`, retaining the hard-rotation inversion limit. Tests also
exercise phase/gap memory, forbidden resets, zero offset, exact waveform
refinement, rejected budgets/inputs and unchanged search restrictions.

## Reproducible records and validation

The committed [plan](examples/cest-memory-plan.json) and compact
[evidence](examples/cest-memory-evidence.json) retain all candidate/control
outcomes, complete input requests, source/runtime/script identities and full
history hashes. Compact evidence is **185,216 bytes**. The complete CLI record is
**3,189,354 bytes**, generated outside the project at
`/private/tmp/mrqlab-cest-memory-de9cdb3/complete-record.json`.

* Search record: `e80f314cdf0d46113fef9f413f7625d047881e774d67d9de3cf691256eafdae7`.
* Payload: `2e0b85fcfa33ed783b7a52a630bda253abad2070c914cf9ccb9b3534e9288ce6`.

From the locked local Python environment, use fresh output paths:

```sh
.venv/bin/python scripts/verify_cest_memory.py \
  --output /private/tmp/cest-memory-new-evidence.json \
  --record-output /private/tmp/cest-memory-new-record.json \
  --verify docs/research/examples/cest-memory-evidence.json
.venv/bin/python -m mrqlab_api.scientific_records replay \
  /private/tmp/cest-memory-new-record.json \
  --output /private/tmp/cest-memory-new-replayed-record.json
```

The evidence script was independently executed again after source freeze;
complete evidence and the entire search record match. A separate generic CLI
process and actual HTTP create/read/full replay match the complete record,
including failed and infeasible candidates and absent selection. JSON formatting
may differ in HTTP export; parsed full records and both identities match.
Isolated-store import checks integrity without claiming recomputation.
Historical example records were not regenerated.

Full backend regression: **903 passed**, with the existing Starlette warning.
Final frontend regression after the browser-discovered record-status fixes:
**115 passed in 16 files**, TypeScript and production build passed. Generated
static output is retained outside the project and excluded from the source commit.

## Actual browser and native-file verification

The in-app browser host became available in this phase. Actual `/research`
interaction ran the default seven-offset design, showed numerical PASS alongside
failed combined targets, and recomputed the same result hash:
`eaa315761db7758c5922df4f38f3425a0a85ccdab79c104057f9df96a38b6d78`.
Native download followed by native file-chooser import and replay matched.

The browser then recomputed/saved study `browser-cest-memory`, opened its actual
record link, filtered the local library, natively exported/imported the complete
scientific record and fully recomputed it. Record ID:
`9fc1285bb7e06f28be0d5fbc25b40e7bff2df7d4b3ca4544c00b01419fa1a71c`;
payload `a68224012160546b70c22ac9845b3cd40582daedc856c1ac77262103992f3853`.
The visible pane correctly reports integrity PASS, historical physical targets
FAIL, and current computational replay PASS. Import alone reports integrity only.
The selected sidebar now reflects replay completed in the current session, and
an already-open record no longer receives an instruction to open a record after
list refresh. The complete portable browser downloads and actual rendered
screenshots are preserved under `/private/tmp/mrqlab-cest-memory-de9cdb3/`,
including `browser-cest-memory.jpg` and `browser-record-replay-proof.jpg`.

This closes the native JSON boundary for this CEST run and the shared scientific
record flow. It does not retroactively test every modality, native CSV flow or
every historical entry. Remaining platform gaps include measured CEST/flow/MRS
bindings, molecular relaxation libraries, spatial/field/coil/readout realism,
noise-aware uncertainty, cross-platform replay, attachment provenance and durable
replay receipts. The broader goal remains active. No submission material,
push, PR, merge, router change, workspace relocation or B/C unlock occurred.
