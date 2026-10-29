# Research workbench: design and acceptance plan

Parent anchor `d292956`. The new research entry connects browser design controls
through bounded API requests to the five committed research chains, finite grid
search, explicit validation and source-pinned replay. Existing locked clinical
protocols and milestones B/C retain their contracts. Teaching/research use only.

Design uses the existing instrument shell: deep panel #121b21, metal #26353c,
trace cyan #4fe3eb, text #e8f1f4, budget/target amber #ffb834 and failure #e67979.
System sans text follows the current app; numeric outputs use tabular figures.
Left-aligned controls sit beside a larger trace/image viewport. Genuine phases
(question/design, simulation, validation, replay) form the evidence sequence.
The memorable element is the measured signal/image; no decorative hero or
invented result appears before a real backend run. At narrow widths controls
stack above measurements. Visible focus, labelled controls, status/error live
regions and table alternatives accompany plots.

Review against the brief: generic scorecards would hide the physical model and
its failure conditions, so measurements occupy one instrument surface and the
validation table reports pass/fail separately from solver convergence. Parameter
search selects a finite-grid candidate but cannot promote it to clinical quality.
Only backend measurements are plotted; browser code does no MRI simulation.
JSON export/import and a source-pinned replay request preserve every run.


## Implemented interfaces and contract

- `/research` renders five real backend chains. Controls include editable design
  JSON and two-class 2D/3D phantom labels; there is no browser MRI surrogate.
- `POST /research/run`: strict per-chain models, bounded grids/partitions,
  work/memory/duration/RF-sample limits, invalid-design 422 and pinned-source 409.
- `POST /research/search`: at most four fully validated candidates; every
  feasible candidate retains its full run; invalid physical designs retain a
  reason. Execution feasibility and target validation are separate.
- Run/source hashes, actual target values, full complex data and exact replay
  inputs are retained. Search has its own pinned replay request and hash over
  **all** candidate outcomes, including selection. Export includes this record.
- The API fingerprints loaded code at startup and rejects execution if source
  files subsequently change. It cannot label old imported Python code with a
  fingerprint from newly edited files. Python/NumPy versions are recorded.
- JSON import checks type/source fields and displays no measurement before the
  backend executes. Editing controls clears old measurements; aborted or stale
  responses cannot overwrite a newer design. Errors do not fabricate results.
- Shared-scale images preserve absolute amplitude comparisons; 3D previews show
  the center slice and exports retain the whole volume. Curves have numeric
  table alternatives. Server-side complex results retain real/imag components.

## Browser and production verification

Real browser → local API → physics → rendered measurements was checked for all
five chains. Default TSE has image NRMSE 0.269555 and PSF prediction error
1.8261e-16: expected reference inequality remains visible. Radial candidate
spokes 2/24/48 yield image errors 0.12775 / 0.00019971 / 2.6192e-11 with respective
failed/failed/passed targets; replay of the entire comparison matched its hash.
Flow reports blood max |Mz| 0.39872 and wall min |Mz| 0.58160 against 0.1/0.7:
the default fails. CEST displays all four control spectra and negative MTR
asymmetry alongside positive amide difference. Matched MRS reports full-fit
residual 4.3052e-16; its synthetic calibration boundary is visible.

The initial browser download-event observation timed out; it is not evidence of
a completed native download. Export now attaches its download anchor to the DOM
and defers object-URL revocation for WebKit. A frontend regression reads the
exported Blob and checks all candidates/replay fields; import tests then execute
the pinned request and compare results. Native download/file-picker roundtrip
remains a browser verification gap until observed successfully.

`next build` produced the `/research` static route (8.26 kB page, 95.5 kB initial
JS) and completed static generation of all nine pages. React review checked
controlled labelled inputs, source-independent rendering, abort/generation guards,
unmount cleanup, numeric alternatives, focus styles and bounded response sizes.
The default narrow IAB viewport showed the stacked research layout and wrapped
navigation without clipping the validation table.

## Remaining platform gaps

The research seams still use separate parameter/result conventions rather than
a single universal scientific experiment schema. Imported lab measurement files,
measurement uncertainty, reproducible environment manifests, calibrated priors
and multi-stage project persistence are incomplete. Grid searches use declared
synthetic truth/controls; they are not patient-driven protocol recommendations.
Physics-specific remaining gaps are recorded in the four preceding coverage
reports: fast large-grid NUFFT, realistic pulsatile/3D motion and prospective
gating, microscopic NOE/generalized semisolid response, validated molecular MRS
basis and spatially converged localization. These are outstanding requirements
of the broader platform goal, not completed capabilities.

The two locked protocol entries and Milestones B/C were not changed. No push,
PR, merge, submission writing or hardware execution was performed.

## Full validation and artifact handling

- Python: **641 passed**, one existing Starlette/httpx deprecation warning.
- Frontend: **90 passed**, 13 files (8 new research-page cases).
- TypeScript and production `next build`: passed.
- Export Blob content, delayed WebKit URL release and pinned import/replay have
  frontend regression coverage; native download/picker verification is still open.
- The repository historically tracks `apps/web/out`. Build output was preserved
  outside the source checkout at
  `/private/tmp/mrqlab-research-build-d292956-20261028`; the tracked baseline output
  was restored so a generated asset refresh is not mixed into the source anchor.
- The staged source/report diff passes whitespace checks. No shared dependency
  installs or changes to another worktree were needed.


## Eighth entry: PRESS volume fitting

The continuing line adds `mrs_press` / **PRESS / volume fit** alongside the
original MRS chain. The labelled basis selector exposes volume integration and
center-point mismatch control; numerical RF/grid/FOV and leakage targets are
visible alongside amount/fit errors. Only pulse TE and RF duration can vary in
its API search. Full complex 3D maps remain in run/export records, with center
z-plane magnitude previews. See [PRESS coverage](press-volume-coverage.md).

Full suite: **770 Python / 99 frontend**, TS and production build passed. Actual
HTTP/CORS and complete run/search hash replay were checked. The current browser
control host was unavailable and Safari control timed out, so this entry's real
browser clicking/visual inspection remains an explicit gap. Tests and a static
build are not presented as having closed that gap or native download/re-import.
