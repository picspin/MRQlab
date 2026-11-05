# Common linked image/vector core and TSE migration

This round starts from `586cd3e` and implements the first verifiable common-schema
slice. It reuses the contrast adapter's complete data, bounded controls and
scientific-record execution/replay chain. It does not complete the expanded
platform goal. This remains teaching/research simulation, without scanner
validation or clinical-quality certification. Milestones B/C remain parked.

## Common design and safe edits

`mrqlab-linked-image-vector-1` is implemented in the Python linked-readout core
and the corresponding TypeScript contract. Neither the core's field definitions
nor its edit model enumerate TSE parameters or require two tissues or echo
numbers. A separate ideal TSE adapter supplies physics, capabilities and input
mapping. The first transform implementation is deliberately restricted to a
complete 2D/3D Cartesian centered inverse DFT; other transforms fail explicitly.

The common object retains complete binary64 real/imaginary arrays in both views,
C-order image shape/axes, acquisition-order grid indices, normalized coordinates
in cycles/voxel, and times in seconds. The shape/axes link the signal grid,
image voxels and complete structure label grid. Every label binds to a unique
tissue ID. Per-tissue state, source reference and declared origin are retained.
Source-manifest SHA256, complete runtime manifest and input-parameter fingerprint
are included in the standalone pair, along with adapter identity and scope.
Scientific records also check these pins against their envelope and replay input.
The canonical pair fingerprint covers all metadata and both complete views.

The core retains at most 1,000,000 complete samples and 128 declared controls;
the scientific TSE API retains its existing stricter per-run limits.

The shared validator checks complete unique bounded integer sampling, matched
finite complex arrays, coordinate/time/axis/unit consistency, tissue bindings,
capability uniqueness and the actual complex inverse transform. It retains the
existing transform tolerance `1e-12 * max(1, max(abs(image)))`. Pair integrity and
transform consistency remain distinct from numerical physics, reported target
status and full replay. A self-consistently rehashed target forgery still requires
actual computational replay and is rejected by that computation.

`LinkedEdit` has a semantic field, value, optional tissue binding and optional
`image` or `signal_vector` view. View omission preserves existing callers. The
pair's capability descriptors specify either a finite numeric interval or unique
categorical choices, with units. The common validator rejects duplicate edits
(including contradictory edits across views), unknown/unbound fields or tissues,
booleans, numeric strings, nonfinite numbers, unsupported categories, arbitrary
extra/path keys and values outside bounds. No clamp, extrapolation, field alias
or pixel/sample overwrite occurs. Low-level read-only runs can have current
values outside the narrower scientific API edit range; this never expands that
range. Coupled timing, relaxation-domain and work constraints still execute in
the existing physical model after the individual descriptor checks.

The migrated adapter's edit intervals remain the existing scientific API domain:

| Control | Accepted edit domain |
|---|---|
| Refocusing start/end | 1–180 degrees; no unused end control for a single echo |
| TR | .05–2 seconds |
| Echo spacing | .006–.03 seconds |
| Ideal ky order | `linear` or `centric` |
| Bound tissue concentration | 0 through the declared validity maximum, mmol/L |

The existing `edited_tse` scientific-plan carrier now consumes common edits and
validates them against the parent's common pair before applying the TSE mapping.
Only this declared adapter is executable in this slice. Each child first fully
replays the immutable source/runtime-pinned parent, then recomputes physics and
both complete views. Parent embedding, before/after hashes, seven dependency
stages and the existing maximum of three edit generations remain. Importing a
portable child now saves its embedded immutable ancestors too, so record-link
navigation works in an empty store. No separate TSE-only pair is emitted.

Rejected edits produce explicit exceptions / HTTP 422 reasons and no child is
saved. The frontend retains the attempted input and error while hiding stale
outputs; it never substitutes a successful result. Rejection tests retain the
failure assertion and verify the unchanged parent/store. Physical gradient
waveform edits are explicitly unsupported and fail. No operation-level waveform
or within-ADC Bloch fidelity is implied by the authored ideal sample times.

## Migration mapping

| Previous TSE pair | Common core / declared adapter |
|---|---|
| `mrqlab-image-signal-pair-1` | `mrqlab-linked-image-vector-1`; new identity, no relabelling of old hashes |
| Complete complex image and acquisition vector | Same physical values, axes, order, times, normalized coordinates and inverse-DFT convention |
| Two-class spatial labels and tissue IDs | Common complete label grid and arbitrary unique tissue binding list; TSE still supplies its two authored tissues |
| `signal_vector.echo_numbers` | Adapter metadata at `signal_vector.extensions.echo_numbers` |
| RF/TR/echo-spacing/order/concentration fields | Adapter-supplied numeric/category descriptors, common typed edit validation, existing TSE input mapping |
| Pair hash with no standalone execution pins | Pair hash includes source/runtime/input pins and per-tissue provenance |
| `edited_tse` with immutable embedded parent | Same bounded carrier/replay chain; common edit payload supports either view |
| Child-only import | Embedded ancestors also stored for parent-link navigation |

The frontend type and existing contrast page consume descriptor kinds and
category choices, preserving the existing stale-output/error behavior. This is
migration of an existing research surface, not frontend productization or a
physician/LLM usability study. Existing odd-size 2D/3D direct voxel-sum tests now
exercise the common validator. A separate three-tissue, arbitrarily named-axis,
complex direct-sum fixture verifies the core without TSE physics or fields.
Historical records retain their original source anchors and identities. This
round does not automatically transcode/replay old-schema records under changed
source, nor add a legacy standalone-pair reader.

## Verification

Fresh verification on the final source:

| Check | Result before the final frontend command |
|---|---|
| Full Python `pytest -q` | **1070 passed**, one existing Starlette warning, 240.87 s |
| Frontend `npm test` | Pending; final remaining command, no frontend pass claimed |
| TypeScript `tsc --noEmit` | Passed |
| Repo `git diff --check` | Passed |

No full dual-end pass or commit is claimed before frontend verification finishes.
If the specified Vite-cache EPERM occurs, work stops immediately and its actual
result is reported in the handoff without staging/committing or changing the
node_modules symlink, configuration or permissions. The new schema/replay subset has **43 passed**; the migrated existing
linked-readout/TSE-control subset has **25 passed**. Tests cover strict rejection,
view-origin equivalence, unchanged parents, failed target preservation, complete
HTTP parent/child export/import, parent-link reads, shared-library full replay and
byte-identical parent/child replay in fresh CLI processes. Existing forged-parent,
runtime/source mismatch and three-generation-bound cases remain in the full suite.

The unchanged independent contrast verifier was executed against this migration,
then repeated in a second process with complete evidence equality. Five
concentrations each check all **256** complex samples and a 3D case checks all
**128**. Fresh maximum absolute errors are:

| Observable | Maximum error |
|---|---:|
| Tissue echoes | 1.6653345369377348e-16 |
| Complete complex signal samples | 2.842170943040401e-14 |
| Image against independent direct inverse DFT | 9.995665849454016e-16 |
| Pair inverse-transform check | 0 |
| Authored sample schedule | 0 s |

The .5 mmol/L child retains image NRMSE **0.16709967168449194**, failing its
unchanged **1e-10** target. Its PSF forward check passes. No 0.4 NRMSE gate or
other threshold was changed or retuned. Node numeric transport preserves the
complete new common pair. Fresh evidence and parent/child exports are in
`.mrqlab/linked-schema-586cd3e/{evidence,parent,child}.json`, with a second
complete evidence file at `.mrqlab/linked-schema-586cd3e/evidence-repeat.json`.
These are new execution artifacts, not the previous round's verification counts.
Fresh parent / child scientific SHA256:
`3925a766ce0ac173d60c429db16724ad41315325e4a3ed7e70ad556520a26e3e` /
`f84d851832f35a611c05da5f6d1b7e25736ef80410975fcf293cbdbf8dd5c234`.

## Explicit remaining gaps

- Additional transform implementations, non-Cartesian/sparse/multichannel and
  nonspatial signal contracts, measured spatial coordinates/anatomy, units beyond
  the current grid convention and general multimodal adapter registration.
- A modality-independent scientific execution carrier beyond the retained
  `edited_tse` adapter, general parameter proportions and tissue-modality inference.
- Non-Cartesian NRMSE recalibration; the existing 0.4 gate remains unchanged.
- General operation-level RF/gradient orchestration, physical gradient waveform
  edits in this adapter, finite RF/slice effects and coherent within-ADC evolution.
- Dynamic biology, concentration-time kinetics, measured relaxivity and
  uncertainty, and agent-induced diffusion/exchange changes.
- Frontend productization, actual physician/LLM usability and clinical judgement.

No goal-file changes, other modality adapters, manuscript/submission work,
Milestone B/C work, router/provider/classifier changes, other-worktree changes,
push, merge or PR are part of this slice.

Verification artifact copies are retained inside this worktree. Initial artifacts
were mistakenly written under `/private/tmp/mrqlab-linked-schema-*`; this path
error is disclosed, and no other repository/worktree was changed.
