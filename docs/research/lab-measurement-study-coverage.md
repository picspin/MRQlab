# Lab measurement → calibrated experiment → design validation

Parent anchor `94f67b5`. Research/teaching only; no scanner validation, clinical
quality certification or concentration/protocol recommendation claim. B/C parked.

| Existing evidence | Missing link | This phase |
|---|---|---|
| `clinical_search` and `family_search` execute declared prior/candidate grids | Their “lab” checks do not ingest independent measurements | Strict measurement assets with units, source and independent acquisition split |
| `ExperimentGraph`, clinical question and tissue priors | No measured prior calibration record | Fit T2 from signed real CPMG echoes with known Gaussian sigma; preserve the original and fitted graph |
| `run_tse_imaging`: EPG echo weights, ideal line encoding and PSF | No measured uncertainty or independent calibration gate | Use calibrated graphs, independent holdout checks and explicit T2-uncertainty corners in candidate eligibility |
| `/research` pinned JSON run/search | No portable multi-stage calibration record | Complete staged evidence with integrity/source/runtime pins, local CLI save and computational replay |

The scientific record groups measurement evidence around existing experiments;
it is not a new simulator root, scanner export path or execution-provider gateway.
No change to the locked Milestone A catalog is intended.

Statistical assumptions follow [NIST weighted least squares](https://itl.nist.gov/div898/handbook/pmd/section1/pmd143.htm)
and [model-validation guidance](https://www.itl.nist.gov/div898/handbook/mpc/section3/mpc365.htm):
weights are declared known inverse variances. Linearized parameter uncertainty is
conditional on a correct model and known independent noise, not a clinical
confidence guarantee. The CPMG monoexponential regime is motivated by the
[system phantom study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8252537/), without
claiming reproduction, scanner calibration or phantom certification.

## Implemented chain and scientific contract

`LabStudy` is a measurement/design aggregation around an existing
`ExperimentGraph`, not a parallel simulator or a promotion of the locked clinical
catalog. `run_tse_imaging(experiment=...)` now reuses that graph's authored T1/PD
priors and clinical context. It snapshots the chassis before simulation so caller
mutation cannot alter an already returned replay request. Independent relaxation
TSE3D/EPG is required; unsupported physiology, pools and sample overrides fail.

The CSV asset has exact headers:

```text
measurement_id,acquisition_id,tissue_id,split,echo_time_s,signal_a_u,std_a_u
```

Both tissue IDs must bind explicitly to labels 0/1 and the ExperimentGraph's
priors. Each tissue needs at least three distinct calibration times and three
holdout times. Calibration and holdout acquisition IDs must be disjoint. Duplicate
IDs, unknown/millisecond headers, invalid timing, nonfinite values, invalid sigma,
magnitude/Rician noise assumptions and unsupported refocusing protocols fail.
Origin must be explicitly `measured` (user declaration) or `synthetic`.

Browser CSV upload transports the original bytes, not a decoded/re-encoded text
surrogate; UTF-8 BOM and CRLF are retained in the raw-file SHA256. The parser
accepts UTF-8 with an optional BOM while hashing its original bytes. This proves
which supplied bytes were used, not their laboratory authenticity. The committed
example uses LF enforced by `.gitattributes`, keeping its byte hash stable across
checkouts.

T2 is fitted by signal-space weighted nonlinear least squares. For each T2 the
lab amplitude has a profiled positive least-squares solution; a bounded log-T2
scan and refinement produce the estimate. No logarithm of noisy observations,
image gain fit, residual-based sigma rescaling or transfer of lab receiver gain
into image proton density is performed. T1/PD stay authored, uncalibrated priors.
The inverse information matrix uses the declared known Gaussian standard
errors. Boundary/identifiability/relative-uncertainty or residual failures block
selection. Holdout predictions account for conditional fit uncertainty, and
holdout values never enter the fit. Changing only holdout data leaves the
calibration-stage hash unchanged while its validation-stage hash changes.

Every design runs the existing EPG/TSE/PSF chain at its fitted nominal T2 pair and
four rectangular T2 uncertainty corners. The design objective minimizes worst
tissue PSF RMS among points passing all declared PSF, reconstructed-image ROI
contrast, duration and RF-proxy targets. ROI contrast is the absolute difference
between mean **real reconstructed image** values in the two supplied label ROIs;
train-mean signal contrast is a separate diagnostic. It is not a patient CNR or
clinical image-quality metric. A nominally acceptable point may fail a corner.
Incomplete global budgets, failed calibration/holdout, or an all-failed grid yield
no selected design. All outcomes and reasons remain in the record.

The work ledger reserves an upper cap before every simulation, includes fitting,
charges failed attempts conservatively, and distinguishes reserved from estimated
work. A failed TSE readout reports the EPG work it actually spent, including a
partial tissue's completed steady-preparation trains (the per-call cap is shared
across the two tissue runs, so a failure can exceed it); the ledger charges the
larger of that spent work and the reservation, never less. RF is a relative ideal-pulse energy proxy over preparation and acquisition,
not SAR. Time includes the longest coexisting-tissue preparation and full ideal
Cartesian readout; it is not scanner timing certification.

## Portable, staged scientific record

The record includes original and calibrated ExperimentGraphs; all supplied data,
units/noise assumptions and raw-file hash; fitted parameters/covariance; every
holdout residual; every candidate and uncertainty scenario; selected image and
physical provenance; explicit targets; and six hashed dependencies:

1. measurements;
2. calibration;
3. independent holdout validation;
4. calibrated experiment;
5. design search;
6. target validation.

Source Python files, `pyproject.toml` and `uv.lock` have a content manifest. Runtime
records Python, architecture, package versions and NumPy BLAS configuration as an
independent snapshot. A live source edit requires restart; source/runtime mismatch
fails replay. Record integrity verification is distinct from computational replay
and is not a digital signature or authenticity/clinical certification.

Browser testing exposed JSON number representation loss (`1.0` becomes `1`). The
record now declares `typed-json-f64-v1`: a typed JSON hash tree uses exact binary64
hex numeric values, unifies signed zero and keeps booleans/strings/containers
distinct. Exact large integer identifiers belong in strings. It also retains the
validated request as opaque JSON text so existing `ExperimentGraph` int/float
union fields reproduce their legacy plan fingerprints. The request object and
lossless text must have matching semantic hashes. This is a project format,
**not RFC 8785 conformance**; the general interoperability issue is described in
[RFC 8785](https://www.rfc-editor.org/rfc/rfc8785).

Tests execute an actual Node `JSON.parse`/`JSON.stringify` roundtrip before Python
computational replay. Corrupted content, inconsistent requests, wrong source or
runtime and recomputation mismatch fail explicitly. Saving uses atomic
no-overwrite file creation; an invalid record leaves no partial output.

## Local files and reproducible example

The example is explicitly synthetic, not a phantom/scanner measurement dataset:

- [Input experiment/study](examples/tse-lab-study-input.json)
- [Original echo CSV](examples/tse-lab-echoes.csv)
- [Complete study record](examples/tse-lab-study-record.json)

From an editable installation of this source checkout:

```bash
python -m mrqlab_experiment.study_records run docs/research/examples/tse-lab-study-input.json --measurements-csv docs/research/examples/tse-lab-echoes.csv --output /tmp/my-tse-study.json
python -m mrqlab_experiment.study_records verify /tmp/my-tse-study.json
python -m mrqlab_experiment.study_records replay /tmp/my-tse-study.json --output /tmp/my-tse-study-replay.json
```

`verify` checks integrity only; `replay` re-executes calibration, every candidate
and target validation and compares results. Existing destination files are not
overwritten. Without an editable installation, use the same source roots as
pytest via `PYTHONPATH=packages/recon:packages/physics:packages/sequence-ir:packages/mrqlab_experiment`.

A non-editable (wheel/site-packages) install has no repository manifest. Importing
the study-record helper must still succeed there; only recording or replaying a
study fails, at use time, with a message naming the editable-source requirement.
The import-time source anchor is therefore captured as `None` when the checkout
is absent instead of raising during module import.

In this declared example, fitted T2 is 40/120 ms with conditional standard
uncertainty 0.13157/0.66200 ms. Worst PSF RMS for 2/4/8 echoes is
0.21067/1.30026/1.52809 voxel; nominal ROI image contrasts are
0.047339/0.027771/0.019730 in the authored signal units. All pass the example
constraints, and the 2-echo point minimizes the declared objective. This is a
finite teaching grid, not a universal or clinical protocol optimum.

## UI and API evidence

`/research/lab-study` connects explicit-origin input/CSV to calibration, holdout,
uncertainty-aware design comparison, preview and full record replay. Nothing is
shown as measured before execution. A failed gate has no selected preview; edits
clear stale evidence and abort stale responses. The existing five-chain research
page uses the same extracted measurement renderer and remains available.

Endpoints are `/research/lab-study/example`, `/import-echoes`, `/run`, `/replay`
under that prefix. Server validation bounds samples, CSV bytes, grids, work and
request shapes. JSON export has a copyable-record fallback, and the verified CLI
provides local-file delivery independent of native browser downloads.

The production static build emitted ten pages including the lab-study route.
A real in-app browser executed the production page against the local API,
displayed calibration and selected images, and reported full computational replay
agreement. Original CSV import through the native file chooser was observed with
its raw hash retained. The browser was later navigated away before a subsequent
post-import simulation check; API and real CLI tests cover CSV→study→replay, and
this observation is not claimed as a complete native-picker roundtrip. Native
JSON download/re-import remains unverified.

## Remaining gaps

This is a TSE measured-input pilot, not a universal calibration schema for all
modalities. Unknown/correlated/Rician noise, complex phase preprocessing, uncertain
TE, multiexponential relaxation, B1/finite-RF effects, calibrated T1/PD, joint
posterior propagation, global continuous optimization, multi-study project
persistence and measured phantom/scanner transfer remain incomplete. Other chains
still need corresponding measured-data adapters and independent validation. No
patient/clinical calibration or scanner quality claim follows from synthetic
agreement. Original physics-fidelity gaps remain in the platform status ledger.

## Full validation

- Python: **667 passed**, one existing Starlette/httpx deprecation warning.
- Frontend: **95 passed**, 14 files; TypeScript passed.
- Production build: passed, ten static pages including `/research/lab-study`.
- Independent scientific evidence includes analytic CPMG recovery, real EPG
  effects of changed measured T2, sigma-scaling and repeated-noise uncertainty,
  holdout leakage prevention, corner rejection, budget/no-target selection,
  image gain preservation, input nonmutation and immutable replay snapshots.
- File/transport evidence includes exact CSV BOM/CRLF hashes, real CLI
  CSV→record→replay, atomic no-overwrite saving, tamper/source/runtime rejection,
  actual Node JSON roundtrip and production-browser computational replay.
- The final example's raw CSV hash matches the file bytes; its saved complete
  record equals an independently executed CLI replay at
  `/private/tmp/mrqlab-study-replay-final-20261029.json`.
- Generated static files are preserved separately at
  `/private/tmp/mrqlab-lab-study-build-94f67b5-20261028`; the historical tracked
  `apps/web/out` snapshot is restored before the source anchor.

No new dependency installation, submission material, scanner connection, licensed
provider activation, push, PR or merge is part of this stage. The remaining gaps
above keep the complete platform goal active.
