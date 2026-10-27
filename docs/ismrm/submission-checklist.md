# Figure plan and submission checklist

## Key figures and tables

All commands below run from the integration worktree root, using the Python environment described in README. Figures show the current audited implementation, including the echo-parameter mismatch; they must be regenerated after fixes. These are editable, local drafts, not approved publication figures.

| Item | Content and source | Generation command | Current status / required caption |
| --- | --- | --- | --- |
| Figure 1 | Brain per-tissue diagnostic signal; `evidence/brain_lesion_t2_tse-diagnostic.json` | `$PYTHON docs/ismrm/reproduce.py` → `evidence/brain_lesion_t2_tse.svg` | Generated. ADC sample index, a.u.; idealized EPG, teaching gradients, actual 4 echoes; not lesion imaging, clinical CNR, or patient data |
| Figure 2 | Knee per-tissue diagnostic signal; `evidence/knee_cartilage_meniscus_pd_t2_tse-diagnostic.json` | `$PYTHON docs/ismrm/reproduce.py` → `evidence/knee_cartilage_meniscus_pd_t2_tse.svg` | Generated. Separate cartilage / tear / meniscus / fluid / fat forward runs; not an anatomical reconstruction or executed ObjectiveVector |
| Table 1 | Both scene parameters, means, named pair differences and provenance; `evidence/summary.json` and `*-plan.json` | `$PYTHON docs/ismrm/reproduce.py` regenerates source; `$PYTHON -m json.tool docs/ismrm/evidence/summary.json` displays values | Draft values in audit section 3. Final typesetting pending; keep input echo_count distinct from derived echoes and API fingerprint distinct from direct plan |
| Figure 3 (optional) | ExperimentGraph → resolved plan → compiler / EPG → Observation provenance; `ARCHITECTURE.md`, `resolution.py`, `observations.py` | No artifact generated; manual schematic pending | Do not imply clinical objectives, robustness evaluation, B/C, scanner export or optimization are executed |
| Figure 4 (optional) | Independent reference error / parameter sensitivity for final corrected verticals | No data or generation command yet: [待确认] | Unverified. Must design and run experiment before adding a Results panel |

`PYTHON=/Users/hilbert/work/MRQlab-mainfix/.venv/bin/python` for the observed environment. Full repeatable command with an alternate output directory is in README. Figure source files and generating code are retained locally. A final figure legend must explain model assumptions, sampling, units, comparisons, and the distinction between simulated signal and clinical evidence.

## Completed locally

- [x] Dedicated integration worktree and branch from 3239a65.
- [x] Combined fixes f678cbf and 3bdc1da in independent integration commit 3d69943.
- [x] Full gates: 400 Python + 82 web tests; TypeScript exit 0.
- [x] Two actual A vertical API runs, complete input / plan / output archives and source import assertion.
- [x] Separate tissue diagnostics explicitly distinguished from clinical objective evaluation.
- [x] Offline reproduction script, gate script, observed versions, logs and draft SVG figures.
- [x] Limitations retained in abstract and audit; B/C stay parked.
- [x] No push, fetch, gh, PR action, public deployment or portal submission.

## Mandatory scientific and software closure

- [ ] Fix or explicitly narrow the submission's claims around echo parameter semantics; demonstrate failure-before/pass-after regression and rerun all evidence.
- [ ] Resolve the multi-tissue EPG and named objective / reference behavior for any retained clinical-protocol claim. Declared robustness and acquisition constraints must not be reported as evaluated without actual runs.
- [ ] Independent quantitative reference and error report for the final scenarios; distinguish ideal CPMG unit test from end-to-end scientific validation.
- [ ] Record defensible tissue-prior sources and applicability; identify synthetic assumptions.
- [ ] Resolve contradictory advanced-engine availability wording in existing documents without deleting safety boundaries.
- [ ] Systematic literature / software comparison; no “first” / “only” claim without evidence.
- [ ] Clean-environment installation and replay, separate from the verified reuse of local dependencies.
- [ ] Freeze final code revision, environment and regenerated figure / numeric ledger together.

## User-owned decisions and fields — intentionally blank

- [ ] Meeting edition / submission year: [________]
- [ ] Submission category and scope: [________]
- [ ] Chosen title: [________]
- [ ] Authors, order, approval and contributions: [________]
- [ ] Affiliations: [________]
- [ ] Corresponding author / contact: [________]
- [ ] Keywords: [________]
- [ ] Funding, conflicts and any required ethics declarations: [________]
- [ ] Figure selection and final graphic approval: [________]
- [ ] Public demonstration / recording decision and approved link: [________]
- [ ] Additional scientific validation scope: [________]
- [ ] B/C decision if separately requested: [________] (currently parked; no unlock assumed)

## Final checks after user choices

- [ ] Check selected meeting's official word / character / figure / anonymity / disclosure / AI-use requirements and deadline; not checked in this offline audit.
- [ ] Browser demo and A-contract-to-UI correspondence if an interactive demo is claimed; currently unverified.
- [ ] Match all abstract numbers against the final archived run and all figure captions against their generating commands.
- [ ] Preserve research-use-only, teaching-gradient, no-scanner, unvalidated clinical outcomes and B/C boundaries after final edits.
- [ ] User reviews and approves scientific interpretation and all metadata.
- [ ] User personally performs any ISMRM portal submission. This agent does not submit.
