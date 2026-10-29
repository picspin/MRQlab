# Finite-RF PRESS volume fitting and replay

Parent `34e871e`. Entry `mrs_press.run_press_basis`, API kind `mrs_press`,
research page **PRESS / volume fit**. Teaching/research only; synthetic spin
priors, no scanner validation, clinical concentration calibration or quality
certification. Milestones B/C remain parked. No submission material is included.

## Physical question and implementation

The question is whether finite RF bandwidth, chemical shift and spatial
localization bias recovered spectral amounts when a center-point basis is used.
This extends the earlier single-isochromat MRS chain; that chain stays available.

A 90° x-phase sinc excitation and two 180° y-phase sinc refocusers select x, y,
and z respectively. Each waveform sample evolves chemical shift, isotropic J,
RF and its slice gradient concurrently with a Hermitian eigensolver. A negative
excitation-gradient lobe lasts half the RF duration. Pulse starts are 0, TE/4
and 3TE/4; the echo is TE after the excitation center, at TE + RF_duration/2
from preparation start. Free intervals exclude the finite pulses and rephaser.

Ideal filters select coherence orders **[-1,+1,-1]**. The coherence convention
and the use of sequence-specific finite-RF bases follow the primary
[FSL-MRS simulation documentation](https://open.oxcin.ox.ac.uk/pages/fsl/fsl_mrs/simulation.html).
No FSL implementation, molecular library or example dataset is imported.
Projection is independently compared to explicit RF phase cycling, including
phase-shifted propagators recomputed from the Hamiltonian. This validates the
filter convention within the declared spin model; it is not a vendor crusher
waveform, eddy-current or scanner implementation.

The model supports one to three spin-1/2 nuclei. Unit initial total longitudinal
polarization defines signal amount. The runner fits an authored singlet at
-213.3 Hz and synthetic AB at [-300,-270] Hz with 7 Hz coupling, plus a separate
0 Hz unit water reference. These are not named or validated metabolites.
Relaxation is an explicit scalar exp(-time/T2) envelope from preparation start:
0.15 s for teaching components, 0.2 s for water. There is no T1 preparation or
quantum relaxation superoperator.

At each midpoint quadrature cell, the selected echo density is propagated and
its **complex** signal integrated with physical cell volume dV. FID evolution
after the echo is exact in the static Hamiltonian eigenbasis. The reported
normalized signal is the complex integral divided by declared nominal voxel
volume, without fitted localization gain. Summing magnitudes would be a different
operation and is not used. Complete complex 3D maps, axes, raw integral FID,
center FID, density/waveform hashes and timing remain in the API result.

## Separate numerical and signal targets

The default 20 mm cube uses FOV twice the nominal dimensions. A 17³ basis fits
an independent 25³ synthetic sample. Three comparisons are distinct:

- Spatial quadrature: 17³ versus 25³ at fixed RF discretization and molecular priors.
- RF time sampling: 64 versus 128 samples at fixed 25³ grid and molecular priors.
- FOV truncation/resolution: 25³ at 2× FOV versus 39³ at 3× FOV.

These are measured relative complex-FID differences, not certified infinite-grid
error bounds. Power outside the nominal voxel means |complex echo response|²
within the modeled FOV. Its fraction and power-weighted centroids do not measure
unmodeled infinite-space leakage. The expanded-FOV check bounds the observed
change only; full spatial B0/B1, receive-coil and anatomy models remain absent.

| Quantity | Default measured result | Declared target |
|---|---:|---:|
| Maximum relative teaching-amount error | 7.85237e-5 | ≤0.05 |
| Full complex FID fit residual | 4.03995e-5 | ≤0.02 |
| Maximum spatial-grid difference | 1.08984e-4 | ≤0.02 |
| Maximum RF-discretization difference | 0.00115732 | ≤0.002 |
| Maximum expanded-FOV difference | 0.00141511 | ≤0.02 |
| Maximum outside-voxel power fraction | 0.0522133 | ≤0.1 |

All gates must pass. A stricter RF target of 1e-5 fails and remains failed.
An additional 128→256 RF refinement test demonstrates reduced change; the
0.12% 64→128 difference is not concealed by a gain fit or called roundoff.
Only the on-resonance center analytic comparison uses a 1e-13 absolute tolerance
for accumulated floating-point eigensolver roundoff.

Default recovered amounts are [0.0200004397, 0.00800062819] for known authored
[0.02, 0.008]. Center-point basis fitting instead produces [0.00687140718,
0.00270119423], maximum amount error **0.662351** and residual **0.0352578**:
FAIL. An uncoupled fitting basis against the 7 Hz sample gives maximum error
**0.625422**, residual **0.163828**: FAIL. Each mismatch control uses the same
sample, numerical resolution and targets as its matched run.

The singlet spatial power centroid is [1.061898, 1.066496, 1.066496] mm at 33³.
The independent RF-bandwidth prediction for y/z displacement is
`-offset_Hz/(gamma_bar * G)` = **1.066500 mm**. Whole-volume projection versus
phase-cycle FID relative difference is **3.24720e-16** for the saved AB case.
Tests additionally cover three-spin volume phase selection and the analytic
on-resonance center singlet.

## Optimization, budgets and records

The API design search permits pulse TE and RF duration only. Molecular priors,
sample truth, basis mode, acceptance targets and numerical resolution are fixed
within a search; changing these candidate keys is rejected. Separate runs allow
sensitivity or mismatch controls. Physical timing failures stay infeasible;
executable designs can still fail one or more numerical/signal targets.

Shared conservative work/memory preflight reserves every basis, sample, water,
RF refinement, spatial refinement and expanded-FOV simulation before the first
RF propagator. The default work proxy is **55,795,392**, estimated peak memory
**11,991,664 bytes**, below the explicit 100 million / 128 MiB defaults. These
are allocation/operation planning proxies, not measured RSS, wall time, SAR or
scanner constraints. Invalid/over-budget designs fail before RF cache creation.

Source hashes cover the PRESS module and imported physical helpers. Direct
simulation rejects live source changes since import; the API additionally pins
all loaded package/API source. Replay records retain all inputs, raw complex
results and map hashes, Python/NumPy versions and every simulation's provenance.
The saved [evidence](examples/press-volume-evidence.json) keeps full FID, basis,
fit and reference arrays plus hashes over complete runs and complex 3D maps.
It avoids duplicating the whole volume in this repository fixture; the complete
arrays are delivered in the API run/export. Independent CLI verification rebuilds
all maps and compares every saved portable JSON field and complete-result hash.

```sh
uv sync --locked --extra dev --extra noncartesian
python scripts/verify_press_volume.py --output /tmp/press-volume-replay.json \
  --verify docs/research/examples/press-volume-evidence.json
```

Output must be new. Independent-process replay matched; a subprocess regression
modifies a complex FID value and confirms rejection without creating output.
Exact replay requires the recorded source/environment, not arbitrary future
code or platform versions. Other historical evidence retains its original source
anchor and must not be regenerated merely to make its source hashes current.

## Validation and remaining gaps

Full Python suite: **770 passed**, one existing Starlette/httpx warning.
Frontend: **99 passed** in 14 files. TypeScript and production static build pass.
The new entry has a labelled volume/center control, stale-result clearing,
convergence/target tables and source-pinned replay. React review checked controlled
inputs, existing abort/generation guards, no browser-side physics, numeric plot
alternatives and bounded server-side grids. Build output is preserved outside
source at `/private/tmp/mrqlab-press-build-34e871e-20261029/out`.

Real HTTP API/CORS, full complex records, volume and center replay, and the
three-point pulse search/replay were checked against the running local server.
The production static route includes the eighth entry. **Real browser clicking
and visual inspection of this new entry are not verified**: in-app browser
access returned unavailable and native Safari control timed out. Existing browser
verification of earlier anchors does not certify this addition. No native JSON
download/re-import is claimed here. No browser or Codex service was killed and
no thread-writer lock was deleted to work around those tool failures.

Still missing: validated larger molecular spin library and inter-tool numerical
comparison, full quantum relaxation/T1/steady-state preparation, real crusher
and phase-cycle acquisition imperfections, realistic B0/B1/receive maps, patient
motion, measured spectral datasets and uncertainty, macromolecule/baseline/water
suppression modeling, and clinical concentration calibration. This advances
PRESS localization evidence; the full lab-to-clinical teaching/research platform
objective remains unfinished. No push, PR, merge or Milestone B/C unlock occurs.
