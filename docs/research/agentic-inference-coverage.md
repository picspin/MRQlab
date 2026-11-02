# Agent-readable acquisition inference and tissue-modality proxies

First slice of the agentic layer on top of `e3a94d9`'s common linked schema. It
lets an agent read the **complete retained complex acquisition vector** from a
scientific parent record, represent relative parameter weight at the declared
anatomical/structure level, and turn those numbers into bounded, human-reviewable
tissue-modality proxies. It reuses `mrqlab-linked-image-vector-1`,
`linked_readout`, `tse_linked_readout`, the TSE scientific runner and the
immutable scientific-record replay chain. No shared schema file was modified.

This is a deterministic, bounded numerical inference layer, not an external LLM
call. Its output is typed JSON intended for an LLM/human reviewer. There is no
model-provider dependency, no free-form reasoning trace and no claim that an LLM
was run in this slice. The "agentic" part established here is the machine-readable
signal ingestion, explicit identifiability gauge and replayable modality-proxy
contract; actual LLM orchestration remains a gap (listed below).

Teaching/research scope only. The declared label grid is not measured anatomy;
the proxies are not tissue classification, diagnosis, scanner validation or
clinical certification. Milestone B/C remain parked.

## Input and output contract

New module: `packages/mrqlab_experiment/mrqlab_experiment/agentic_inference.py`,
schema `mrqlab-agentic-tissue-inference-1`, canonicalization `typed-json-f64-v1`.

`infer_tissue_modalities(pair, reference_tissue_id=None, max_samples=65536)`
first runs `verify_linked_readout(pair)`. Two contracts are distinct:

Forced input requirements — a violation raises `ValueError` before any
inference is returned:

- the complete paired complex image/vector, not a display magnitude;
- unique complete grid indices, matching declared inverse DFT and finite values;
- at least two and at most 16 declared tissues; the reference must be one of them;
- default sample count ≤65,536. Library callers may raise the explicit bound up
  to the linked-grid limit; the HTTP plan does not expose that override.

Coefficient-availability requirements — a violation does not raise; the
structural/image proportions are still returned and the affected layer is
reported as explicitly unavailable (`available=false` with a concrete reason):

- every declared tissue must occupy at least one voxel for coefficient
  identification. A declared-but-empty label is kept, not rejected: it is
  reported with `voxel_count=0`, `voxel_fraction=0` and the per-echo
  coefficients are marked unavailable;
- `signal_vector.extensions.echo_numbers` must cover every sample with
  nonnegative integer IDs, at most 64 echo IDs. Missing or malformed membership
  keeps the structure/image proportions and reports the per-echo coefficients
  as explicitly unavailable.

No data is mutated. `inference_sha256` covers all fields except itself.

Reported layers:

| Layer | Exact basis | What it is not |
|---|---|---|
| `proportions.structure` | voxel count/fraction of each declared label | not imaged or measured anatomy |
| `proportions.image_signal` | energy and magnitude of the complete complex image inside each declared label, plus fractions | not an independent segmentation or tissue classifier |
| `proportions.acquisition` | per-echo sampled Fourier partition model, rank/nullity, residual, identifiable coefficients and relative contrast | not absolute per-tissue amplitude except at the DC-bearing echo, and not T2 |
| `modalities` | constant-per-structure displays of the identifiable proportions and early/late relative contrast | not human tissue modalities validated against a patient |

The present TSE pair remains a 16×16 two-tissue synthetic example by default.
The module is generic over declared 2D/3D label grids and tissue IDs; it does not
assume the TSE adapter's tissue names.

## Identifiability boundary

For a complete tissue partition define `B_t(k) = FFT(mask_t)(k)`. A static
per-echo partition model predicts

`y_e(k) = sum_t w_{t,e} B_t(k)`.

For every non-DC frequency, the mask Fourier columns sum to zero:
`sum_t B_t(k) = 0`, `k != 0`. Adding the same offset `c` to every tissue weight
therefore leaves every non-DC sample unchanged. Absolute per-tissue amplitudes
are not identifiable from non-DC samples; only differences/relative coefficients
are. A DC sample breaks that gauge because `sum_t B_t(0) = N`; a complete
Cartesian partition samples DC in exactly one echo, so at most that one echo can
carry absolute amplitudes.

The implementation verifies this numerically instead of assuming it:

- Build the mask Fourier basis at the retained grid indices.
- Per echo, solve the possibly rank-deficient least-squares problem with `lstsq`.
- Test whether `design @ ones` vanishes. If it does, the common mode is
  unidentified and the expected rank is `T-1`; otherwise the expected rank is `T`.
- Reject any rank other than the expected rank, a relative residual above
  `1e-8` for either the least-squares fit or the retained real coefficients,
  non-real coefficients above `1e-9` of the solution's own magnitude (so the
  criterion stays relative at arbitrarily small amplitudes; an exactly-zero
  solution is accepted as real), or a negative absolute solution beyond `1e-9`
  of that magnitude at a DC-bearing echo.
- On any rejection, return `available=false` with a concrete reason. Partial
  coefficients are never fabricated.

Residual definition (single, consistent across echoes). Each echo bin's
`relative_residual` is the relative residual `||design @ Re(x) - y|| / ||y||` of
the **retained real coefficients** `Re(x)`, where `x` is the per-echo
least-squares solution. It is computed for every echo before any failure
short-circuit, so it stays meaningful even after a rejection on an earlier echo.
The complex least-squares residual is used only for the static-model test
(`model_residual` against `1e-8`) and is not reported in the bin.

When available, coefficients are projected onto zero common mode for every echo,
so columns are comparable as relative weights. Absolute amplitudes are reported
separately only for the identified DC-bearing echo. `contrast_vs_reference` is
the zero-common-mode difference from the chosen reference. A single-exponential
apparent decay is fitted only when at least two echoes exist, mean echo times
strictly increase, and the contrast has a constant nonzero sign; the reported
`apparent_relative_contrast_decay_s` is `-1/slope` of `log|contrast|` versus
time, with a log-domain maximum residual. It is **not** a per-tissue T2 map.

Validation tolerances are explicit and unchanged by this round:

| Check | Tolerance |
|---|---:|
| Parseval relative energy error | 1e-9 |
| Static partition relative residual | 1e-8 |
| Imaginary coefficient relative scale | 1e-9 |
| Structure/image fraction sum | 1e-9 |

Nine boolean checks are retained: pair integrity, complete signal read, Parseval
consistency, echo membership declared, static partition model, identifiable
coefficient basis, structure normalization, image normalization and modality
completeness. `validation.passed` is their conjunction; it is a numerical
identifiability report, not a physics/anatomy/clinical verdict.

## Modality proxies and unavailable items

`modalities` contains, when computable:

1. `structure_voxel_share` — declared voxel fraction, constant per structure;
2. `image_signal_share` — reconstructed complex-image energy fraction;
3. `dc_echo_absolute_amplitude` — absolute amplitude share at the one DC echo;
   omitted, with an explicit `unavailable` note, when the identified amplitudes
   are all zero (a normalized share is 0/0 there and is not fabricated);
4. `early_relative_contrast` — signed zero-common-mode difference at the first echo;
5. `late_relative_contrast` — the same at the last echo when ≥2 echoes exist.

Each carries its shape/axes, full flattened values, min/max, basis and a note
stating it is not measured anatomy or diagnosis. The scientific-record view
includes these as bounded images (3D center plane, max 128×128) and the
coefficient curves through the existing presenter.

`unavailable` explicitly records the unimplemented/indeterminate items, including
per-tissue T2 maps, T1-weighted modality (one TR does not identify T1), tissue
classification, per-echo coefficients when the model is rejected, missing
absolute amplitudes, and the reason a relative-decay fit was not made. This is
the truthful gap list, not a failure to be hidden.

## Scientific-record replay chain

`AgenticInferencePlan` is a typed scientific execution
(`type="agentic_inference"`) with the parent record SHA256, optional embedded
parent record and optional reference tissue. Creating a child:

1. loads the parent from the immutable store if not embedded;
2. calls `replay_scientific_record(parent)` **before** inference, so an imported
   uncompiled parent cannot be trusted on integrity alone;
3. extracts `original['result']['linked_readout']` and runs the bounded inference;
4. stores the parent pair SHA256, `parent_computationally_replayed=true`, the
   inference and its bounded view.

The summary pins `parent_record_sha256`, `parent_pair_sha256`,
`inference_sha256`, source/runtime and the model-reported numerical status.
Stages are:

`question → parent_image_signal_record → agentic_signal_inference →
design_and_inputs → source_and_runtime → computed_execution →
reported_validation`.

Integrity verification checks the inference hash and structural bounds but does
not recompute coefficients; a self-consistently rehashed forgery can pass that
stage. Full `replay_scientific_record` recomputes the parent and inference and
rejects it. Store save recursively persists the embedded parent, so importing a
portable child alone leaves the parent navigable and replayable. Agentic children
themselves are not accepted as parents (`_edit_parent` requires a TSE run or
edited-TSE parent); there is no recursive agentic graph in this slice.

HTTP: `POST /research/records` accepts the typed plan; invalid reference IDs are
422 and save no child; `GET /research/records/{id}` and `/import`, `/export`,
`/replay` retain the existing contract. The only new route is the frontend page
`/research/agentic-study`; no additional API endpoint was introduced.

## Frontend surface

`apps/web/lib/agentic-inference.ts` types the inference payload, extracts it
only when `summary.mode === "agentic_inference"`, and formats exact percentages
without inventing missing values. `ScientificExecution` now includes the typed
`agentic_inference` variant and the summary type carries the two new pins.

`/research/agentic-study` loads the existing synthetic contrast TSE plan, saves
a parent, lets the reviewer choose a declared reference tissue, and saves an
agentic child. It renders:

- the shared `Measurements` view (modality proxy images and coefficient curves);
- structure-voxel/image-energy proportion tables;
- per-echo rank, nullity, absolute-vs-relative status and model residual;
- identified coefficients, DC absolute amplitudes and relative contrast/decay;
- explicit unavailable items and the nine numerical checks;
- pair/inference/record pins, full inference JSON and record download.

Changing the baseline or the reference hides the old inference immediately and
disables inference until a new parent/reference is available. Missing echo
membership produces an explicit unavailable message instead of a coefficients
table. Replay requires a matching backend receipt; a failure removes the result.
The research index links to the new page.

## Tests and fresh verification

New Python cases:

- `tests/experiment/test_agentic_inference.py` (7): complete-signal/Parseval and
  exact structure/image proportions on the real TSE pair; deterministic
  non-mutating reads; DC-only absolute amplitudes checked against the TSE
  amplitude table; rank/nullity per echo; same-T2 synthetic relative-decay
  recovery; generic link without echo membership; non-static signal rejection;
  reference/bound errors; integrity-hash versus replay distinction.
- `tests/test_agentic_inference_replay.py` (4): seven-stage child, parent/pair/
  source pins and replay identity; explicit/unknown reference over HTTP and
  immutable store totals; portable child-only import with parent navigation;
  self-consistent forged inference passing integrity but failing replay.

New frontend cases: `apps/web/tests/agentic-study.test.tsx` (7) covers typed
parent→inference flow and default reference, proportion/echo/coefficient/decay
rendering, reference-change stale hiding and explicit re-inference, unavailable
coefficients without a fabricated table, malformed/wrong-mode rejection, replay
receipt and failure hiding, baseline-edit invalidation, and invalid initial plans
never reaching the API. `apps/web/tests/research-workbench.test.tsx` continues to
cover the existing research index; its assertions are not weakened.

Fresh dual-end verification (this worktree, branch `herdr/claude-agentic`):

| Check | Result |
|---|---|
| Python `pytest -q` | 1061 passed, 15 skipped, 0 failed (1076 collected) |
| Frontend `npm test` | 19 files, 141 tests passed |
| TypeScript `tsc --noEmit` | 0 errors |
| `git diff --check` | 0 whitespace errors |

The frontend dependency tree was absent in this fresh worktree; `npm ci` was run
inside `apps/web` to install it. No symlink, permission or test configuration was
changed. The EPERM `vitest results.json` failure mode described by the operator
did not occur in this run.

## Remaining gaps

- No external LLM is invoked. An LLM still has to consume the typed inference;
  no prompt, tool schema, model-routing or output-quality evaluation exists here.
- No per-tissue T2, T1 map, absolute amplitude for non-DC echoes, tissue
  classification or measured anatomy. The gauge argument above is why some of
  these are not inferable from one complete partition at all, not a temporary
  plotting omission.
- The static-per-echo scalar partition model is a declared research model. It
  rejects real non-static/nonlinear signals; it does not fit arbitrary dynamics,
  diffusion, flow, exchange, motion or contrast pharmacokinetics.
- Only the existing TSE linked adapter is exercised end to end. Other adapters
  must declare the same echo membership and complete pair before reuse.
- Relative decay is a two-parameter log-linear fit with no uncertainty,
  confidence interval or model-selection evidence; it must not be reported as T2.
- The display proxies are constant per structure and normalized to the largest
  tissue. They are not calibrated MR contrast or quantitative parameter maps.
- No scanner validation, measured relaxivity, clinical decision, dose advice,
  multi-subject cohort or physician usability study exists.
- The parent graph is bounded to one agentic generation over a TSE run/edit;
  arbitrary multi-modal or recursive agentic derivation is not supported.
- The inference tests exercise 2D pairs. 3D label grids use the same `fftn` code
  path and the preview takes a center plane, but no independent 3D agentic
  fixture was added in this round.
- No native browser run, screenshot or physician review was performed in this
  round. Frontend evidence is component tests plus TypeScript, not a clinical
  usability claim.
- The pre-existing 0.5-concentration child image NRMSE failure
  `0.16709967168449194` against the unchanged `1e-10` target remains preserved
  and was not re-labelled by this layer.
