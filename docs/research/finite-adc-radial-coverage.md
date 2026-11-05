# Finite-ADC radial TSE, known field and receive maps

This continuation of `998b612` extends the existing `radial_tse` research kind
with explicit `readout_model: "finite_adc"`. There are still twelve research
entries. The older echo-center exact-DFT/FINUFFT models remain available with
their original physics. This new mode is an **exact dense DFT reference**, not
a fast NUFFT, measured field/coil calibration or scanner/clinical certification.
The default 20-billion-work search fails all declared targets and selects nothing.

## Physical acquisition and inverse model

The previous mode holds each spoke's echo-center magnitude constant. The new
mode uses the same periodic EPG amplitudes but propagates T2 and spatial B0 phase
at every point ADC, with individual complex receive maps. This is valid here for
ideal hard **180-degree CPMG** and free evolution around each echo. Variable-flip
and finite-RF within-window coherence are not implemented; unsupported angles and
the FINUFFT backend fail explicitly rather than falling back to another model.

For component j, echo e and time offset tau from that echo, its temporal weight
is `W[j,e] * exp(-tau/T2[j])`. The sample at coil c is

`sum_j weight[j,m] sum_r coil[c,r] component[j,r] exp(-2*pi*i*k[m].r + 2*pi*i*B0[r]*tau[m])`.

Negative tau means the physical sample precedes the echo, not that relaxation
runs backward: `W[j,e]` already includes decay to the echo; total elapsed time
from excitation remains positive. Perfect refocusing makes static B0 phase zero
at each ideal echo. Receiver phase is explicitly pi/2, so physical `Mx+iMy`
after an x excitation becomes a real positive on-resonance echo reference.

The role of known receive maps in a linear complex imaging model follows the
measurement-model discussion in [Fessler's MR reconstruction review](https://arxiv.org/html/1903.03510v2#S1.SS2).
Our finite-ADC weights, direct reference operator and independent Bloch checks
are implemented locally. No paper implementation, reconstruction library,
regularizer, external dataset or calibration map is imported.

All points are midpoint samples of a centered ADC gate. With 32 points and a
2-ms window, dwell is 62.5 microseconds and offsets are -0.96875 to +0.96875 ms.
The radial position is `tau/window` in cycles/voxel, so this new mode uses
midpoint k samples, distinct from the older endpoint trajectory. Golden-angle
spokes and centered Cartesian kz are retained. Field/coil mismatch controls use
these same actual samples and geometry.

At FOV .24 m, a balanced positive prephaser, negative radial readout and positive
rewinder produce `k=-gamma_bar * integral(G dt)`. Each prephaser/rewinder lasts
.5 ms; three-dimensional kz uses opposite z moments before/after the readout.
All moments sum to zero per spoke. Peak ideal gradient amplitude is checked
against the authored limit. ADC plus both lobes must fit between neighboring
ideal RF events; an 8-ms window with .5-ms lobes fails at 8-ms echo spacing.
The model has instantaneous rectangular gradient switching, no slew/eddy-current
or ADC integration model and no finite-RF pulse duration. It is not a hardware
waveform validator. The ExperimentGraph supplies EPG echo centers only; the
explicit research timeline supplies the new ADC/gradient schedule.

Default B0 and two coil maps are analytic functions of coordinates, independent
of labels. They are authored priors, not estimated measurements. Complete maps
and their hashes are returned. Optional `field_hz` and `coils_ri` inputs retain
explicit units and real/imaginary pairs. Malformed, nonfinite, excessive-amplitude
or jointly invisible coil maps are rejected. No RSS/coil normalization occurs.
`basis_field_scale` is a declared mismatch input, never fitted by the solver.

The operator accepts only coordinates, temporal weights, field and coil maps;
it receives no labels, reference image or spatial support. Unknowns are two
unrestricted complex component images. The complete temporal SVD is a lossless
coordinate change; no mode is truncated. Forward and Hermitian adjoint include
the conjugated temporal, field and coil terms. CGLS starts at zero, uses no
regularizer/gain fit and measures a fresh data residual on termination. A small
data residual still does not certify component or image recovery.

The separate `static_control` payload field now holds a **frozen-ADC** mismatch
control in this mode: the same acquired data, receive maps, coordinates and two
unknown component images, omitting only within-ADC B0/T2 evolution. Its preview
is explicitly labelled “Frozen-ADC mismatch control” and has a separate numeric
color range. It is not the older one-image static-control model.

## Independent validation and preserved failures

Operator tests compare complete forward/adjoint sums and complex inner products
with independent voxel loops in 2D and odd/even-kz 3D. An independently assembled
dense matrix/lstsq test recovers arbitrary non-unit complex maps; this is an
operator mathematics test, not a radial identifiability claim. Zero coil coverage,
complex coordinates and insufficient allocation/work budgets fail closed.

A separate physical reference computes longitudinal recovery under hard RF,
executes x excitation/y refocusing rotations, integrates B0 and each physical
gradient interval, propagates T1/T2, and sums each receive channel. It does not
call the inverse operator or the acquisition formula. All **6,144** complex
samples in the default 2D case match to maximum absolute **1.18624e-12**, relative
**2.13698e-14**. Arbitrary component phases [.2,-.6] also match all 6,144 samples
to **1.16396e-12** absolute. A two-partition 3D case matches all **512** samples
to **7.89760e-13** absolute. The reference uses local sequence times to avoid
cancellation from subtracting large global TR timestamps; the global timeline
is separately checked against those local times.

The strict physical/image targets remain image and component NRMSE ≤1e-6,
magnitude ROI contrast ≥.005 and RF proxy ≤200. The default measured data target
is 1e-10. Baseline 16×16, 96 spokes, four echoes, [40,120]-ms T2, 2-ms ADC and
two coils yield:

| Case | Complex image error | Component error | Fresh data residual | Stop / iterations | Total work |
|---|---:|---:|---:|---|---:|
| Default 20-billion budget | .0018707920 | .0183800985 | 6.50136e-8 | max_work / 2145 | 19,991,819,886 |
| Explicit 50-billion budget, same 1e-10 data target | 1.10060e-7 | **1.45323e-6** | 9.96574e-11 | data_residual / 4643 | 35,832,603,246 |
| 50-billion allowance, **stricter 1e-12** data target | 9.51648e-10 | 7.64134e-9 | 9.82551e-13 | data_residual / 5046 | 38,388,693,614 |
| Fitting field omitted, 50-billion allowance | 1.29851854 | 41.86928896 | .030275666 | max_iterations / 6000 | 44,442,758,766 |
| Small undersampled 2-partition case | .02833030 | .26800260 | .000443083 | max_iterations / 40 | 70,786,670 |

The middle row has passing image/data residual but failed component recovery;
it remains **FAIL**. Tightening the data target and explicitly increasing work
produces a passing conditional reference without changing image/component/ROI/RF
targets. This does not turn the default budget into a pass. The frozen-ADC
control's default image NRMSE is **.3847829515**; omitting the field in the
fitting model leaves the acquired samples unchanged and is not recalibrated away.

The fixed-budget ADC search preserves three executable failures at 1/2/4 ms
and one timing-infeasible point at 8 ms. Image errors are .00185913/.00187079/
.00185006 and component errors .01822634/.01838010/.01799225. There is no selected
design. Search may vary pulse timing/ordering and ADC/prephaser durations, while
field/coil priors, fitting assumptions, budgets, resolution and targets stay fixed.

Memory preflight reserves the dense matrix/conjugate, construction workspace,
all retained raw data/maps, coefficient CG vectors and a complete frozen-control
solve before acquisition/inversion. Default estimated peak is **30,638,080 bytes**
under 128 MiB. Sample count includes every coil (6,144 complex values by default).
The 20-billion API default and 50-billion cap are not silently increased; large
grids fail before dense allocation. Estimates are planning proxies, not hard RSS,
native allocation, wall time, SAR or scanner guarantees.

## Reproducible records and delivery

The [plan](examples/finite-adc-radial-plan.json), compact
[evidence](examples/finite-adc-radial-evidence.json) and
[independent verifier](../../scripts/verify_finite_adc_radial.py) retain all
inputs, numerical outcomes, full-run/source/runtime/script identities, complete
residual-history hashes and raw-data/map/timeline identities. Compact evidence
is **106,478 bytes**. Full records retain all complex raw samples, maps, component
and echo images, residual histories and gradient timelines; the generated
scientific search record is **4,637,958 bytes**, preserved outside source at
`/private/tmp/mrqlab-finite-adc-998b612/complete-record.json`.

* Record: `c67469fda9a00aec6653e18db559fe5556eabad8043a287ad58aa1ce756234e4`.
* Payload: `a0a683aa53e903b1114496aca27b1658a405f36037b295df2cc39308bb132ade`.

Use fresh output paths in the locked local environment:

```sh
.venv/bin/python scripts/verify_finite_adc_radial.py \
  --output /private/tmp/finite-adc-new-evidence.json \
  --record-output /private/tmp/finite-adc-new-record.json \
  --verify docs/research/examples/finite-adc-radial-evidence.json
.venv/bin/python -m mrqlab_api.scientific_records replay \
  /private/tmp/finite-adc-new-record.json \
  --output /private/tmp/finite-adc-new-replayed-record.json
```

Independent evidence execution, a new generic CLI process and actual HTTP
create/read/full replay match the complete search record, every failed and
infeasible point and the absent selection. Historical example records remain
unchanged.

Full regression is **954 Python passed** (one existing Starlette warning),
**117 frontend passed** in 16 files, TypeScript and production build passed.
React checks retain controlled inputs, source-pinned imports, existing abort/
stale-result handling, labelled readout selection, numeric alternatives and
backend-only physics. Generated static output is preserved outside source.

Actual browser testing ran/replayed the default failed run, switched the existing
readout selector and compared all four ADC durations. Its **13,176,510-byte**
native research download was reimported through the actual file chooser;
recomputing all candidates and the absent choice matched search hash
`eef8c1e5ea5cda44d1da0d8852f94e85b5756e6465f7c8d1190b9aa55d68bcf8`.
The displayed first failed candidate has result hash
`17fbf23f95ac97003dc55302a1e016aeb92a1f44c28620a3f5de51208764aa91`.

The browser then recomputed/saved study `browser-finite-adc-radial`, followed
its actual record link, natively exported/imported the **4,641,102-byte** complete
scientific search and fully recomputed it. Record ID:
`b04c35150977520efb2c51a1fac7b53bf9556d2b37fb347717d1fdd5811e3dae`;
payload `4dddeb8eb0631ea929837b1bac3c03396e6f279360ad88ec58920176378c3969`.
The UI keeps physical target FAIL, integrity PASS and current replay PASS
distinct, and explicitly says no design was selected. Browser and CLI plans have
different authored contexts/explicit request snapshots, so their record/payload
identities remain distinct. No browser console errors were captured. Actual
`browser-search.jpg`, `browser-record-replay-proof.jpg`, both native downloads,
HTTP receipts and complete recomputed records remain under
`/private/tmp/mrqlab-finite-adc-998b612/`.

Remaining physics: variable-flip/finite-RF echo-window coherence, general slice
profiles, gradient ramps/eddy currents, finite dwell integration, trajectory and
field/coil measurement calibration, correlated noise/whitening/uncertainty,
motion and scalable field-aware NUFFT inversion. The full platform goal stays
active; these gaps are not replaced by a claim of clinical/scanner validation.
High-level portable custom maps currently use JSON lists (with a final real/imag
axis for coils); arbitrary NumPy map containers are not normalized by that wrapper.
No submission import, push, PR, merge, router change, folder relocation or
Milestone B/C unlock occurred.
