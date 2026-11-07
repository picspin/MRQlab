# Static tissue exposure and linked MR Image / Signal Vector control

Continuation of `d383d52`, addressing the expanded platform objective. This adds
an actual concentration-to-relaxation binding in the shared experiment kernel,
a lossless TSE image/signal representation and a human/agent semantic-edit path
through immutable scientific records. It is a partial, declared research adapter,
not completion of general RF/gradient orchestration, biological validation,
diagnostic interpretation, pharmacokinetics or scanner/clinical certification.
There remain twelve general research runner kinds. B/C remain parked.

## Explicit biophysical state

The legacy field is **`PhysiologyModel.contrast_agent_concentration`**, not a
`TissueModel` field. The preceding platform audit misidentified its location;
this report and the current audit correct that description. A nonzero legacy
value previously had no executable unit/relaxivity binding. It is now rejected
at experiment planning/execution, with an instruction to declare a tissue
exposure. Zero/default values keep their previous baseline behavior.

Each `TissueModel` and clinical `TissuePrior` may declare a typed
`contrast_exposure`. Its explicit model is `static_linear_R1_R2`, with
`concentration_mmol_l`, `r1_l_mmol_s`, `r2_l_mmol_s`, reference B0, temperature,
medium, upper valid concentration, source reference and user-declared origin.
Units are fixed as mmol/L and L/(mmol*s); this is local tissue concentration,
**not an administered dose**. No agent catalog or clinical values are inferred.

The applied law is `R1 = 1/T1_baseline + r1*C`, `R2 = 1/T2_baseline + r2*C`;
effective times are their reciprocals. Baseline tissue values are retained and
never mutated. This additive-rate research model and field dependence are
consistent with the physical measurement-model discussion in the original
[Rinck/Muller study](https://pubmed.ncbi.nlm.nih.gov/10370005/). The example
coefficients 4 and 5 are explicitly **synthetic**, not a recommendation for an
agent, tissue or scanner. Medium and temperature applicability remain supplied
assumptions, not measured conditions established by this software.

Strict finite numeric validation rejects booleans, unknown units, blank sources,
negative/excessive concentration, extrapolation above the supplied validity
range, reference-field mismatch, semisolid/shifted-solute exposure and unsupported
T2*/susceptibility combinations. Baseline/effective rates must obey R2 >= R1/2
for this spin-1/2 state model. There is no field interpolation or automatic
concentration conversion. Zero concentration retains baseline times while still
preserving the explicit declared exposure/reference.

The same pure binding is consumed by shared phantom conversion, execution-plan
parameter states, observations and independent-tissue scoring. Every applied
binding records baseline/effective rates/times, source and unchanged priors.
Bloch, EPG, periodic TSE, Gaussian PGSE diffusion and liquid-water CEST integration
are tested. Diffusion ADC and exchange matrices remain independently authored;
this model does **not** infer agent-induced changes in them. The CEST test checks
that the derived water relaxation reaches the existing coupled-pool solver,
matching an explicitly supplied effective-state control with unchanged exchange.

Exposed measured-T2 calibration is rejected: an already exposed measured T2 must
not be silently treated as contrast-free baseline and shortened twice. The
radial/inverse callers of shared TSE preparation also reject exposure until
effective within-readout/inverse priors are consistently bound. This is an
explicit gap, not a fallback to baseline physics.

## One acquisition, two linked representations

Existing Cartesian TSE runs now return `linked_readout` with schema
`mrqlab-image-signal-pair-1` and binary64 typed-JSON canonicalization. It contains:

- Complete complex image values, shape, (z,y,x)/(y,x) axes and C-order layout.
- Complete complex k-space vector in acquisition order, grid indices, normalized
  coordinates in cycles/voxel, sample times in seconds and echo membership.
- Authored structure/label grid and tissue-ID bindings, typed control fields and
  the centered inverse-DFT relationship including 1/product(shape) normalization.
- A pair SHA256 and explicit scope/timing assumptions.

Image magnitude is the human preview; complex values remain available to agents.
No gain fit, reference-image conditioning, normalization of data or image
postprocessing is added. TSE still holds one periodic EPG echo-center amplitude
across each ideal Fourier line. Sample times describe that authored schedule;
they do not establish additional within-ADC relaxation, gradient propagation,
finite-RF/slice or scanner waveform fidelity. The physical limitations of the
underlying TSE model remain visible.

`verify_linked_readout` checks pair integrity, bounded matched arrays, complete
unique sampling, grid coordinates, acquisition-order times and the complex
inverse transform. Independent voxel-sum tests cover odd-size 2D/3D grids and
linear/centric ordering. A real Node JSON roundtrip preserves the pair identity;
signed zero and 1.0→1 conversion cannot invalidate its numeric fingerprint.
The standalone download is the complete linked image/vector object, not just
the first eight displayed signal rows.

## Human and agent parameter control

`/research/contrast-study` loads an explicit synthetic TSE scientific plan from
`/research/contrast-study/example`, computes/saves a baseline and displays linked
outputs. Its controls use the same `edited_tse` scientific-plan contract as a
programmatic agent. The contract accepts only refocusing start/end angles, TR,
echo spacing, ideal ky order and concentration for an already bound tissue ID.
It rejects arbitrary paths, gradient-waveform edits, duplicate edits and unknown
unbound tissues. A single-echo train does not advertise an unused terminal-angle
control. Supplied concentration validity bounds and normal model RF/timing/work
checks are applied to every child request.

The parent must be a linked TSE run or edited TSE record. Its complete integrity,
source/runtime and actual computation are checked **before** child computation.
A consistently rehashed forged parent target report passes integrity alone but
is rejected by mandatory computational replay. The unchanged full parent is
embedded in the child's portable request. No separate store is needed to replay
that exported child. At most three edit generations are accepted, bounding a
single complete replay to four TSE computations with their original per-run
caps; no unbounded parent walk or arbitrary execution is exposed.

Seven stages retain question → parent image/signal record → typed edits → design/
inputs → source/runtime → complete execution → reported validation. Exact before/
after parameter hashes and applied edits are retained. The source and runtime
remain pinned. User edits hide prior output until the new matching computation
finishes; they do not write pixels or signal samples directly. Root/child target
failure reports remain distinct from integrity, transform checks and replay.

## Independent evidence and preserved failures

The [plan](examples/contrast-tse-plan.json) uses the existing two-tissue synthetic
16×16 structure and 140→110 degree refocusing. A separate 180-degree child at
concentrations 0, .05, .2, .5 and 1 mmol/L is checked against independent analytic
longitudinal recovery through the complete spoiled periodic CPMG TR, transverse
decay, direct voxel Fourier sums for **all 256 complex samples** and direct inverse
DFT for every image voxel. A 2×8×8 volume checks all 128 complex samples too.
The physical reference does not call the EPG solver, FFT or contrast-binding
helper. Maximum errors across these cases are:

| Observable | Maximum absolute error |
|---|---:|
| Tissue echo amplitudes | 1.66534e-16 |
| Complete complex samples | 2.84218e-14 |
| Image vs direct inverse DFT | 9.99567e-16 |

The reference tolerances are tied to the inherited 1e-9 periodic-state tolerance,
not to a fitted signal gain. The .5 child image NRMSE against the flat-echo
reference is **0.16709967**, failing its unchanged 1e-10 image target, while PSF
forward consistency passes. It is a computed design state, not a selected valid
clinical design. The synthetic exposure/relaxivity values are not measured lab
calibration, parameter uncertainty or a dynamic biological model.

**Known model difference (issue #62), not an implementation error.** The train-mean
reference holds one tissue amplitude constant across the echo train, so it cannot
match an acquisition whose per-line weights decay with T2 and evolve under the
refocusing-angle ramp. The 0.16709967 gap is that physical T2-modulation effect;
the echo-weighted acquisition is intentional and the constant-weight regression
(`test_constant_echo_weight_ideal_recovery_regression`, `weighting='mean'`) already
covers the ideal 1e-10 recovery on the path where the reference is the exact image.
`quality` is therefore left unchanged as a modulation diagnostic. A parallel metric
`nrmse_vs_echo_reference` (target 1e-10) now certifies the reconstruction step by
comparing the image against an independent direct inverse DFT of the sampled
per-line weights; it passes at ~1e-16 for both weightings on the teaching grids,
so the echo-weighted reconstruction path is verified without hiding the modulation
signal. Both sides are inverse transforms of the same `kspace`, so this cannot
detect an encoding or acquisition fault (wrong EPG weights, modulation or kspace
assembly) — those are shared by both sides; it only proves the two reconstruction
paths agree.

`scripts/verify_contrast_image_signal.py` produces the complete
[evidence](examples/contrast-image-signal-evidence.json), both language request
variants and invalid field/range/legacy-input cases. Two independent processes
produce identical complete evidence. Offline root/child scientific SHA256:
`df08427ec60dc6e2d45f680946bb1e19b3a59966038bf0ca40d089b6e6890eba` /
`cf78f72a24df801513e0d99e6a1a1a3bf35ad61331d74b5170675f46d4114030`.

Historical raw graph/plan/result hashes distinguish free-metadata numeric tokens
such as `62500.0` and `62500`. These hashes are not silently relabelled. Each
scientific record retains its own exact lossless request and replays fully.
A real Node request roundtrip reproduces the actual browser root/child:
`a1f15837a49503979b14c56720f5049dfe498a6e5412d0318fe71e13a221509c` /
`040e65a9b3c6ae6e4e7420050d96b4848a62f183c7010fd4c42695b498bc3ff1`.
Their raw execution hashes differ from the Python-token variant, while the
**complete linked physical image/vector objects are identical**, with pair hash
`94a9808c77e3dfabf4eb395083b5628bcc691c0456a13d101541a2de310b2e44`.

Native browser validation loads/runs the baseline, changes both RF angles to 180
and gray-matter concentration to .5, checks stale output removal and recomputes
the parent/child. Actual image/vector and full child files were downloaded.
The standalone pair passes integrity/transform after browser JSON serialization.
The actual native child also replays through a fresh CLI process with exact
full-record identity. Native file-chooser child re-import and complete library
replay pass; the independent immutable parent can still be opened with its old
image/values. Browser warning/error logs are empty. Evidence, raw records and
logs are preserved outside the project in
`/private/tmp/mrqlab-contrast-image-signal-d383d52/`. Full and summary screenshots
are under this task's visualization directory.

Full regression is **1026 Python passed** (one existing Starlette warning),
**132 frontend passed** in 18 files, TypeScript and production build passed.
The 49 new backend cases cover binding/units/domain, independent Bloch/CPMG and
PGSE references, CEST-water integration, complete odd-size 2D/3D Fourier pairs,
real Node transport, immutable typed edits, forged-parent rejection, bounded
generations and full HTTP/store replay. Eight new frontend cases cover the
common semantic contract, hidden stale outputs, no empty-to-zero concentration,
replay receipts/errors and correct parent identity/navigation. Full regression
also exposed and fixed the old measured-TSE preview decoder's scalar-only
complex assumption; legacy measurement and radial parent/child replay pass.

## Remaining platform requirements

This is the first shared image/vector **TSE adapter**, not a cross-modality
universal contract or proof of actual physician/LLM usability. General spatial
biophysical state, concentration-time kinetics, measured relaxivity/uncertainty,
diffusion/exchange changes induced by agents, finite-RF/gradient operation control
in this paired imaging path, coherent complex within-window evolution, calibrated
anatomy and multimodal search remain incomplete. Existing paired raw-hash numeric
conventions also remain distinct from semantic binary64 identity. No manuscript
content, push, PR, merge, router change or Milestone B/C promotion is included.
