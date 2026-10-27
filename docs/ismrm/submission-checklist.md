# ISMRM 2027 Vancouver — submission checklist

User-confirmed deadline: 2026-10-28 23:59 UTC / 2026-10-29 07:59 Beijing. Scope: software / teaching prototype. This checklist does not certify portal compliance or submission.

## Codex completed

- [x] New `ismrm-fix` worktree and `ismrm/fix` branch from `00b72e2`; original worktrees preserved.
- [x] Failure-before/pass-after regressions for all four execution blockers; logs in `evidence/fix-before.txt` and `fix-pytest.txt`.
- [x] Consume declared echo_count; reject conflicting aliases; both recipes execute 16 echoes.
- [x] Default complete named ObjectiveVector evaluation and score / tissue-contrast products.
- [x] Named Knee references and all declared pairs; no first-two-tissue substitution.
- [x] Independent EPG tissue propagation and normalized weighted complex aggregation, with independent-state and API regression checks.
- [x] Complete gates: 409 Python + 82 web = 491 cases; 12 web files; TypeScript exit 0.
- [x] Both API verticals rerun, requests / plans / responses / diagnostics / summary / environment / SVG regenerated.
- [x] Abstract numerical claims replaced using the new summary; meeting filled as ISMRM 2027 Vancouver.
- [x] Constraints and robustness explicitly remain unevaluated; no clinical optimization claim.
- [x] Teaching gradients, no scanner, relative SAR not W/kg, synthetic priors and B/C parked retained.
- [x] No remote Git, PR, public deployment or portal submission actions.

## Figure options — user selects

| Item | Current artifact / source | Caption boundary |
| --- | --- | --- |
| Brain tissue curves | `evidence/brain_lesion_t2_tse.svg` and diagnostic JSON | 16 echoes, 32 ADC samples; synthetic teaching EPG signal, a.u.; no anatomy or clinical CNR |
| Knee tissue curves | `evidence/knee_cartilage_meniscus_pd_t2_tse.svg` and diagnostic JSON | Individual tissues; named tear / meniscus and cartilage / meniscus pairs are now evaluated by API |
| Numeric table | `evidence/summary.json` | Values and objective scores from corrected runs; no constraint satisfaction claim |
| Architecture schematic | Optional, not generated | Must show only validated execution scope; B/C remain parked |

Regenerate from the fix worktree using `/Users/hilbert/work/MRQlab-mainfix/.venv/bin/python docs/ismrm/reproduce.py`. Figures remain editable drafts awaiting final selection and caption approval.

## User-owned fields — intentionally blank

- [x] Meeting: ISMRM 2027 Vancouver.
- [ ] Submission category: [________]
- [ ] Final title: [________]
- [ ] Authors, order, approval and contributions: [________]
- [ ] Affiliations: [________]
- [ ] Corresponding author and contact: [________]
- [ ] Keywords: [________]
- [ ] Funding: [________]
- [ ] Disclosures / conflicts: [________]
- [ ] Ethics information: [________]
- [ ] Final figure / table selection: [________]
- [ ] Demonstration public / private / recording choice and approved link: [________]

## Remaining review and scope limits

- [ ] User checks official category, word / character / figure / anonymity / AI-use and disclosure requirements in the portal.
- [ ] User approves scientific interpretation and metadata, and personally submits.
- [ ] Browser demo / public deployment only if subsequently tested and approved; currently not claimed.

Independent full-scenario physical reference, prior literature support, systematic novelty comparison and clean-environment installation remain unverified. The revised abstract makes no corresponding claims; any stronger clinical or superiority narrative requires additional evidence. Existing ideal CPMG analytic testing and aggregate-consistency testing do not replace such validation. Acquisition constraints and robustness are declarations, not evaluated outcomes. B/C remain parked.
