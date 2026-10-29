# Shared local scientific records and computational replay

Parent `2d6e8fa`. Implementation `mrqlab_api.scientific_records`; UI
`/research/records`. Teaching/research only. No scanner validation, clinical
quality certification, submission content, push, PR, merge or Milestone B/C unlock.

## Platform connection

All nine research runners, their bounded searches, and the measured-input TSE
workflow now share an immutable scientific-record envelope and local persistent
store. Existing physics models, thresholds and legacy measured-study records
are reused, not replaced. This connects question/target rationale → design and
inputs → source/runtime → complete execution → reported target validation.
Each stage hashes its value and preceding stage. Underlying physical provenance,
complete complex arrays, every candidate/stop reason and measured calibration /
holdout / uncertainty evidence remain inside the complete execution snapshot.

A required context records study ID, research question, target rationale and
teaching/research use. Assumptions and background references are optional.
Background references are explicitly **context_only**; declaring a reference
measured does not apply it to calibration, validate its origin or alter physics.
The measured-TSE execution actually consumes its typed dataset through the
existing calibration/holdout pipeline. Dataset units, user-declared synthetic /
measured origin, source reference, optional raw CSV byte hash, every parsed
measurement and all six legacy stages are retained. Original raw CSV bytes are
not newly archived by this envelope; source-file authenticity is not established.

A shared study ID can contain distinct model records. This is common provenance
and grouping, not a joint multimodal optimizer, automatic clinical-problem
translator or a claim that every model has measured/calibrated clinical priors.

## Three distinct kinds of evidence

| Claim | What actually proves it | What is not implied |
|---|---|---|
| Record integrity | Envelope, exact request/payload strings, nested result/candidate hashes, source manifest, summary and dependency-chain checks | Authentic origin or physical correctness |
| Model-reported targets | Original validation values and pass/fail in the stored execution; complete failed/infeasible candidates remain | A clinical certification or a newly selected valid design |
| Current computational replay | Original source/dependency/runtime checks, full new execution, exact full-record identity comparison | Cross-platform numerical equivalence or scanner validation |

The library labels historical model reports and **not yet recomputed** measurements
separately. Reading or importing a checksum-valid record never changes that label
to a scientific replay success. Tests deliberately construct an internally
consistent forged target pass: integrity succeeds, but real computation rejects
it. There is no cryptographic signature or trusted identity authority here.

Source/dependency manifests cover package/API Python plus pyproject/lock files.
Runtime includes Python, NumPy, Pydantic, FastAPI, Uvicorn, FINUFFT and BLAS.
Replaying under changed sources or runtime fails closed; use the recorded source
anchor/environment. There is no silent source migration or numerical tolerance
relaxation. Previously committed evidence remains pinned to its own anchor.

## Lossless records and durable local storage

`mrqlab-scientific-record-1` stores `request_json` and `payload_json` as lossless
JSON **strings**, each with a byte hash. Browser JSON transport cannot rewrite
numeric tokens inside these strings. Thus the old API result hash convention,
including `180.0` versus `180`, remains reproducible without rewriting old models.
Outer metadata uses the existing typed binary64 fingerprint convention. A real
Node parse/stringify roundtrip, idempotent reimport and complete replay are tested.

SQLite stores each complete record and compact listing summary in one record
transaction. Content hashes identify records; the public API has no update/delete
operation. Repeated identical saves/imports retain one original row. Concurrent
append tests confirm the same ID is not duplicated; corrupted stored objects
are rejected when opened and cannot be overwritten by another save. Listing is
explicitly an **unchecked index**; opening verifies the full record.

The default database is `.mrqlab/scientific-records.sqlite3` **inside this project**,
ignored by Git. It does not use a cloud account or a process-memory recipe map.
`MRQLAB_RECORDS_PATH` or CLI `--store` can explicitly choose a database path;
HTTP clients can supply only validated record IDs, not arbitrary filesystem paths.
Portable export lets another supported checkout/store retain the record unchanged.
There is no garbage collection, overwrite, deletion or workspace consolidation.

The API/storage/CLI record limit is 128 MiB; the browser import limit is 64 MiB.
These are serialized-size bounds, not hard process RSS/resource containment.
Preview shapes, finite numbers and lengths are validated before rendering.
Portable file writes are atomic create-only; existing output is never replaced.
The API package now lazily exports `app`, preserving `from mrqlab_api import app`
while avoiding eager application/CLI double imports and their runtime warning.

## API and command-line delivery

| Interface | Meaning |
|---|---|
| `POST /research/records` | Recompute a strict plan, check optional expected execution hash, save and return complete record |
| `GET /research/records` | Paginated local index, optional exact study-ID filter |
| `GET /research/records/{id}` | Open and integrity-check complete historical record |
| `POST /research/records/import` | Integrity-check and idempotently retain a portable record; no computation claim |
| `GET /research/records/{id}/export` | Export complete portable JSON |
| `POST /research/records/{id}/replay` | Re-execute and compare all stages/results/candidates and record identity |

Execution types are `run`, `search`, and `measured_tse`, using the already bounded
runner/schema registry. Unsupported fields, scanner/export options and invalid
model inputs remain rejected. Expected run/search/legacy-study hashes bind a save
initiated from an already displayed result to a fresh matching computation.
Invalid direct requests are rejected without a saved record; scientific target
failures and failed/infeasible search candidates are stored in complete executions.

The [example plan](examples/scientific-record-tse-plan.json) and
[complete example record](examples/scientific-record-tse.json) retain the expected
TSE image-equivalence failure rather than converting integrity into target success.
Its record identity is
`237d1b413645a960d1ebad1b584d8929a304f84071606237398dff79fe79e821`.
An independent CLI process replay matched the complete record exactly.

```sh
python -m mrqlab_api.scientific_records --store /tmp/mrqlab-records.sqlite3 \
  run docs/research/examples/scientific-record-tse-plan.json --output /tmp/new-record.json
python -m mrqlab_api.scientific_records verify /tmp/new-record.json
python -m mrqlab_api.scientific_records --store /tmp/mrqlab-records.sqlite3 \
  replay /tmp/new-record.json --output /tmp/new-replay.json
python -m mrqlab_api.scientific_records --store /tmp/mrqlab-records.sqlite3 list
```

`verify` checks integrity only. `replay` performs the entire calculation. Output
paths must be new. `export ID --output PATH` retrieves a stored portable record.
Use the locked Python environment with the optional FINUFFT extra when that
backend was used. New processes, not merely in-memory repeated calls, are tested.

## Product design and verification

The page reuses the research instrument shell: panel #121b21, controls #26353c,
text #e8f1f4, signal cyan #4fe3eb, target amber #ffb834 and failure #ffb6b6.
Inherited system sans and tabular measurements retain the app's existing identity.
The layout is `saved experiments | question → design → environment → execution → validation`.
Left-aligned record rows open a wider evidence pane; ordered stages represent real
provenance dependencies. There are no synthetic scorecards or prefilled success
states. At narrow widths the list stacks above evidence. The initial empty state
points to the actual research/measured-study save actions or portable import.

Both research and measured-study results have a labelled **recompute and save**
form, requiring a study ID and target rationale. The library shows model history,
integrity, and current replay separately; failed-only searches do not acquire an
invented best design. Their first executable preview is identified explicitly.
Abort/unmount guards reject delayed responses. Edits invalidate stale save status.
Controls are labelled; status/error regions, tables and numeric plot alternatives
reuse the existing accessibility conventions. Full lossless strings survive export.

Full verification: **828 Python passed**, one existing Starlette/httpx warning;
**108 frontend passed** in 15 files; TypeScript and production build passed.
The build adds `/research/records`; artifacts are preserved outside source at
`/private/tmp/mrqlab-scientific-records-2d6e8fa-20261030/out`.
Tracked generated files were restored and newly generated files preserved without
`git clean`; original handoff scratch and notes were not touched.

Actual HTTP/CORS saved, read, exported and idempotently imported three records
under study `codex-platform-records-20261030`: failed-target TSE, MRS search with
an invalid candidate, and the **synthetic** measured-TSE pilot. After a normal API
shutdown/restart, a new process recovered and fully recomputed all three:

| Mode | Record ID | Model-reported result | Replay after restart |
|---|---|---|---|
| TSE run | `a7bf948998f4853a7cc9480f5cd3d56304f28c9e52488e807182a0723f449fee` | FAIL image-equivalence target | exact match |
| MRS search | `1067ce40a1d4004da386124be49f229a01300192896f5aeca1334b48773f404e` | passing selected design; invalid point retained | exact match |
| Measured-TSE synthetic pilot | `bf8102c5a1fb07660b3e36e08fbd249a4740bc65f76ea5017c798d4b91168d30` | calibration/holdout/selection pass | exact match |

Actual browser clicking, visual inspection and native file-picker/download
roundtrip remain **unverified**: a fresh inventory again reported
`The browser access host is unavailable`. Component tests, static generation,
CLI and HTTP evidence do not close that browser boundary. The prior long Safari
control attempt was not repeated; no Codex service/thread lock or user browser
was modified as a workaround.

## Remaining full-platform requirements

This supplies common local persistence/replay for all current declared chains,
not a universal measured-data model or calibrated multimodal clinical optimizer.
Remaining: raw-attachment archive/authentic origin, unit/uncertainty ontologies and
cross-modality measurement bindings, validated clinical target translation,
measured flow/CEST/MRS calibration and the previous physical-fidelity gaps,
cross-record derived-parameter workflows, durable replay receipts, multiuser
collaboration/access controls and backup/migration policy, large streaming
artifacts and hard resource containment, cross-platform numeric replay and actual
browser/file-flow checks. These remain explicit parts of the unfinished goal.
No project-folder relocation or manuscript import was performed.

## Measurement-derived continuation

The [next coverage report](calibrated-radial-coverage.md) adds strict execution
type `calibrated_radial_tse` and CLI `import RECORD`. It consumes a measured-TSE
parent, revalidates the original numerical study and holdout, binds calibrated
T2 in seconds, and runs a budgeted radial pulse grid with a fixed nominal
reconstruction basis at every uncertainty corner. The complete child embeds the
unchanged historical parent; importing it also retains that parent independently.
Its extra parent-record provenance stage does not alter earlier record formats.

Both default candidates pass nominal targets and fail all four corners, so the
master selection remains absent. Full regression is **842 Python / 111 frontend**,
with TS/build, independent complete CLI/evidence replay, empty-store parent/child
import and actual HTTP save/replay verified. The earlier example and historical
parent sources were not regenerated. This closes one TSE cross-record parameter
dependency, while the broader raw-data, uncertainty, multimodal and browser gaps
above remain open.
