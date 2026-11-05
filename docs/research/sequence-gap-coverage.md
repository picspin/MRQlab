# Sequence-family coverage correction

Baseline: c938ab1 (lab/clinical-e2e). Missing complete chains are **not** missing implementations. This work reuses the following components; legacy Darkblood TSE remains intact. All new claims are research/teaching claims, not scanner or clinical validation.

| Family | Existing implementation (baseline evidence) | Missing end-to-end links | Scope to add in this work |
|---|---|---|---|
| 3D TSE T1 | `packages/sequence-ir/mrqlab_sequence/templates.py:25` TSE echo train and EPG crusher events; `packages/recon/mrqlab_recon/trajectories.py` 3D coordinates; `presets.py:155` GRE 3D TOF | TSE partition encoding, short-TR preparation, flip strategy, T1 recipe/search | Extend TSE with explicit partition encoding and short-TR repeated-train simulation; T1 target/reference search and provenance. Reconstruction coordinates alone do not establish sequence design. |
| SSFP / Darkblood | `presets.py:39` dark_blood_vessel_wall_tse, `presets.py:21` dark-blood-tse; EPG steady_state capability | SSFP template and steady-state reference; explicit blood suppression physics; combined chain | Balanced SSFP and independent steady-state verification; explicit preparation/inflow assumptions, optimization. Preserve legacy TSE recipe; its name does not model suppression. |
| EPSE 2D DWI | `packages/mrqlab_experiment/mrqlab_experiment/gradient.py` Stejskal–Tanner and diffusion waveform; physical gradient composition; recon EPI fill order | Spin-echo EPI template, clinical question, simulated diffusion series, ADC, b optimization | Reuse physical diffusion waveform/b values and EPI traversal; ADC recovery across b values and objective-backed search. |
| Multi-pool CEST | `backends/epg_x.py:39` two-liquid BM; `ops/cest_saturation.py:19` affine saturation; `engines/epg_x_engine.py:78` Z spectrum; `tests/experiment/test_lab_clinical_e2e.py::test_cest_coupled_pool_lab_search_exchange_contrast` | Variable pool count / exchange matrix and N-pool execution/search | General N-liquid-pool BM with two-pool regression; multi-pool Z spectrum/search. Spatial CEST imaging and semisolid MT/NOE lineshape models remain explicit gaps. |
| MRS | `backends/spectral.py:19` chemical shift expansion and `SpectralBackend`; `models.py::SpectralPool`; `tests/physics/test_spectral_engine.py` | Localization, metabolite basis, readout, water reference, integration/search | Idealized PRESS localization, independent metabolite singlets, spectral readout, water-referenced peak integration and design search. No full-spectrum fitting or clinical quantification claim. |

Paths without a prefix are relative to their package above. This is the pre-implementation matrix; acceptance evidence and remaining limitations will be appended after verification.

## Implemented acceptance matrix

The new recipes are available through `build_clinical_recipe` and
`list_clinical_recipes`. The two locked Milestone A protocol-catalog entries
remain unchanged; these extensions are research recipes, not promoted clinical
validation verticals. Each recipe now carries a `ClinicalQuestion` and explicit
`measurement_objective`. The original signal-contrast vector remains available
for the older protocols. Family measurements use `search_family_parameters`
because ADC, coupled-pool Z and water-referenced peak integration require
controls that cannot be represented as independent tissue signal contrast.

| Family | Added design → simulation → optimization → validation | Remaining gaps / exact validity boundary |
|---|---|---|
| 3D TSE T1 | `brain_t1_3d_tse`; extends existing TSE with centric kz partitions, per-echo encoding/rewinding lobes and a 140→110° linear CPMG refocusing ramp. Repeated spoiled EPG trains converge before acquisition. Search varies TR/TE/refocusing strategy; equal-PD/equal-T2 target/reference isolate T1 sensitivity. `test_tse_partition_encoding_and_authored_flip_ramp`, `test_tse_t1_weighting_disappears_for_equal_t1`. | Sparse ky train per kz, teaching gradient moments and ideal RF. This is sequence partition encoding, **not** a fully sampled 3D volume reconstruction. No vendor VFA optimization, B1 profile, scanner export or clinical contrast validation. Preparation time/RF energy is counted. |
| SSFP-Darkblood | `vessel_wall_ssfp_darkblood`; balanced moments, alternating 0/180° RF, TE=TR/2. Two actual inversion events: nonselective at 0, local at 1 μs. Resident spins see both; incoming blood sees only nonselective inversion. Search varies TI/flip/incoming fraction. SSFP fixed-point signal agrees with independent exact on-resonance formula and long Bloch trains off resonance. `test_double_inversion_null_and_inflow_boundary_and_legacy_retained`. | Ideal instantaneous inversions and fixed incoming/resident mixture. Eight repetitions sample a **transient** after DIR; blood nulling is not a steady-state SSFP property. No continuing replacement, realistic flow velocities, cardiac gating or finite selective-RF profile. The legacy Darkblood TSE recipe and preset remain TSE and retain their original semantics. |
| EPSE 2D DWI | `brain_epse_dwi`; 90/180° spin echo, rectangular physical diffusion lobes, alternating Gx readouts/Gy blips, existing EPI geometric traversal. Reuses existing diffusion spec/waveform and ST reference; b is independently integrated from actual gz intervals in the refocusing toggling frame. Isotropic attenuation is applied to the simulated echo. Search selects diffusion amplitude/b; matched-TE b=0 controls recover ADC, including voxelwise multi-b maps. `test_dwi_waveform_integrated_b_signal_attenuation_and_adc`, `test_voxelwise_multi_b_adc_map_and_failures`. | Gaussian isotropic diffusion; no tensor/kurtosis, Rician floor, ramps/slew validation, EPI distortion or eddy currents. EPI geometry is a traversal reference, not a reconstructed anatomical image. Imaging-gradient contributions to b are excluded. Raw physical gradient trajectory uses cycles/m; effective diffusion q is tracked separately. |
| Multi-pool CEST | `cest_multi_pool_z_spectrum`; extends EPG-X relaxation, RF, shifts, observation and affine CW saturation to variable liquid-pool count. Explicit source-row/destination-column rate matrix; N-pool recipes require detailed balance with densities. Default water+amide+amine Z spectrum; tests cover 1/2/3/5-pool operators and 4-pool CW/pulsed spectra, fully connected exchange, permutation invariance and independent Cartesian RK4. Search optimizes saturation power against a no-exchange control. | **No spatial CEST imaging.** All N pools here are liquid Lorentzian pools: no claim of combined semisolid MT/NOE lineshapes. The existing separate two-pool MT backend remains available. Historical two-pool density/rate semantics remain accepted by the compatibility adapter. Full-BM RF saturation evolves k=0 only, as in the existing CEST model. |
| MRS | `brain_press_mrs`; PRESS 90/180/180° timings and orthogonal ideal slab intersection. Reuses the spectral backend with declared NAA/Cr/Cho singlets, chemical-shift FID readout, matched unsuppressed water acquisition, phased absorption-spectrum integration and relative peak-area ratios. Search minimizes area-ratio bias against declared teaching amounts. `test_press_localization_water_reference_and_peak_quantification`. | Ideal top-hat localization, independent singlets and Lorentzian relaxation. Finite integration windows and unequal water/metabolite T2 produce visible bias. No full-spectrum fitting, STEAM, J coupling, finite-RF chemical-shift displacement, water-content/proton-number correction or clinical concentration accuracy. The objective uses known teaching truth, not patient ground truth. |

### Independent SSFP reference

With E1=exp(-TR/T1), E2=exp(-TR/T2), flip α, alternating RF phases and
on-resonance TE=TR/2, the exact magnitude reference is

`PD * (1-E1) * sin(α) * sqrt(E2) / [1-E1*E2-(E1-E2)*cos(α)]`.

`ssfp_steady_state` solves the affine rotating-frame Bloch fixed point instead
of evaluating that expression. Tests compare both with a 2048-repetition pulse
train for several T1/T2/flip combinations; separate off-resonance tests compare
the general fixed point with long trains. No short-TR approximation is used in
these checks. The DIR boundary is checked separately at `TI=T1_blood*ln(2)`.

### Search and provenance

Public entry points: `build_clinical_recipe`, `search_family_parameters`,
`evaluate_family`, `ssfp_steady_state`, `adc_map`, `peak_integrals`.
`LiquidPoolSystem` is exported from `mrqlab_physics`.

Actual search records (`sequence-family-search-results.json`, not committed on this branch; held in worktree `gap-fill`, commit `8e5895f`) contain each
baseline experiment snapshot, candidates, selected feasible point, explicit
clinical question/objective, parameter units, timings, measurements, RF proxy
units, and provenance for **every** tissue/control acquisition. Provenance uses
the existing observation graph's experiment SHA256 and resolved-plan
fingerprint, scanner/prior version, resolved parameters, engine, assumptions,
operator count and work estimate. Source content is pinned by a SHA256 over
`packages/**/*.py`; the recorded baseline commit c938ab1 identifies the parent revision. The
progress-anchor commit containing this document pins the implementation; the
source fingerprint below remains independent of Git commit metadata. Tests replay selected parameters and compare
measurements, loss and provenance exactly; input graphs remain unchanged.

Budgets include TSE conditioning trains, DIR waiting, all CEST offsets and
unsaturated controls, DWI b=0 controls, and the MRS water reference. RF energy is
`sum((flip_deg/180)^2)` for pulse sequences; CEST reports `uT^2 s` explicitly.
These are model-specific teaching budgets, **not** interchangeable SAR values
or scanner safety certification. An infeasible search returns `best=None`.

Observed grid results (loss is minimized; these are not global optima):

| Recipe | Baseline loss | Selected loss | Selected patch |
|---|---:|---:|---|
| brain_t1_3d_tse | -0.0691158380 | -0.0880615962 | TR=0.6 s |
| vessel_wall_ssfp_darkblood | -0.2774193066 | -0.3153016159 | TI=1.1 s |
| brain_epse_dwi | -0.0738083791 | -0.0759427248 | G=35 mT/m |
| cest_multi_pool_z_spectrum | -0.2986461879 | -0.3810429264 | B1=1 μT |
| brain_press_mrs | 0.3093159595 | 0.2181149186 | TE=0.01 s |

The spectroscopy loss is summed relative peak-area bias. Its residual is
reported rather than hidden with a calibration fit. DWI returns ADC values of
0.0006 and 0.001 mm²/s for its declared restricted/normal compartments.

### Added tests and validation

All new tests live in
[`tests/experiment/test_sequence_family_e2e.py`](../../tests/experiment/test_sequence_family_e2e.py):
60 parametrized cases across 24 named test functions.

- Five-family clinical/design/simulation/search/target/provenance replay;
  infeasible budgets, invalid parameters, explicit CEST control-time budget.
- TSE kz lobe moments/rewinders, authored flip ramp, steady preparation, T1
  specificity, and standard tissue-observation consistency.
- SSFP independent exact formula, off-resonance long-train convergence,
  explicit DIR null/inflow boundary, and legacy TSE preservation.
- Five diffusion amplitudes including b=0, waveform-integrated b versus ST,
  attenuation, multi-voxel ADC recovery and physical trajectory units.
- Variable-pool equilibrium/conservation, RF and saturation; two-pool adapter
  regression; no longitudinal recovery at nonzero configuration orders;
  four-pool CW/pulsed Z spectra; fully connected exchange/permutation;
  independent RK4 and defective-generator exponential checks; imaging rejection.
- PRESS slab exclusion, water reference, relative integration bias, empty-voxel
  failure, Nyquist/window-resolution rejection, invalid timing/designs.

Full verification in `gap-fill`:

- Python: `python -m pytest tests/ -q` — **488 passed** (428 existing + 60 added).
  One pre-existing FastAPI/Starlette httpx deprecation warning remains.
- Frontend: `npm test -- --cache=false` in `apps/web` — **82 passed**, 12 test files.
  Plain `npm test` also passed all 82 tests but exited 1 because the sandbox
  blocked writing Vitest results through the shared `node_modules` symlink.
  Disabling only the test cache gives exit 0 without changing test behavior.
- TypeScript: `npx tsc --noEmit` in `apps/web` — exit 0.
- `git diff --check` — clean.

Python uses the existing `MRQlab-mainfix/.venv/bin/python` executable with this
worktree's packages resolved by pytest; no files in that checkout were edited.
The ignored `apps/web/node_modules` symlink reuses lab-clinical's installed
dependencies. No network fetch/install was needed.

There is no blocking user decision for this research scope. Future choices are
which remaining extension to prioritize: full spatial acquisition/reconstruction,
realistic inflow/selective RF, semisolid/NOE CEST imaging, or richer spectroscopy
and calibration. This progress anchor is committed locally after full verification. No
submission files, portals, pushes, PRs or merges are part of this work.
