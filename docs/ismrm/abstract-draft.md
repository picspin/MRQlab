# Abstract draft — internal review only

This draft is deliberately limited to evidence in the repository and recorded runs. It is not ready for submission: resolve the mandatory items in `readiness-audit.md` and check the selected meeting's official requirements before final editing. No priority, uniqueness, clinical efficacy, or scanner readiness claim is made.

Title candidates (user to select):

- MRQlab: Traceable MRI Experiment Contracts for Teaching-Oriented Protocol Exploration
- Linking Clinical Intent to Provenance-Bearing MRI Simulation: A Research Software Prototype
- Auditing Parameter Semantics in Brain and Knee TSE Teaching Experiments with MRQlab

Submission year / meeting: [________]

Submission category: [________]

Authors and order: [________]

Affiliations: [________]

Corresponding author and contact: [________]

Keywords: [________]

Funding / disclosures / ethics declarations: [________]

## Purpose

MRI simulation can illustrate magnetization evolution, but interpreting a simulated protocol also requires knowing which tissue assumptions, parameter values, and approximations actually entered the calculation. We developed MRQlab as a research and teaching software prototype linking structured clinical intent to resolved experiment plans and provenance-bearing observations. We assessed contract integrity and examined the correspondence between declared protocol intent and executed calculations.

## Methods

The platform represents sequences, tissue priors, scanner descriptions, objectives, and readouts in an experiment graph. A compiler and capability-selection layer connect this graph to existing Bloch or extended phase graph (EPG) propagation, rather than introducing a new propagation algorithm. Versioned clinical recipes identify target, reference, and confounding tissues. Resolved plans record parameter units, sources, approximations, and canonical fingerprints; observations retain execution provenance. We integrated unit-validation and plan-mutation fixes and ran the complete Python and web verification suites. Brain lesion T2/TSE and knee cartilage/meniscus PD/T2 TSE recipes were evaluated through the local application API. Additional forward runs separately simulated each declared tissue to inspect teaching signal differences. An existing ideal CPMG test compared EPG signals with an independent exponential T2 envelope.

## Results

The integrated revision passed 400 Python tests and 82 web tests; TypeScript checking also passed. Both clinical recipe paths returned successful validation and execution responses with signal, trajectory, and illustrative image observations carrying plan provenance. Separately simulated mean signal differences were 0.212594 a.u. for lesion versus white matter, 0.300535 a.u. for meniscal tear versus meniscus, and 0.086844 a.u. for cartilage versus meniscus. These quantities were diagnostic teaching signal differences, not measured clinical CNR or executed clinical-objective scores. The audit identified mismatches: recipes declared 16 echoes through an unconsumed parameter while the compiled templates used 4 echoes; clinical objective vectors were not evaluated by the default run; and the legacy knee contrast summary compared the first two tissues rather than the declared reference pair. Thus, passing software tests did not establish complete protocol-semantic validity.

## Conclusion

MRQlab demonstrates a traceable organization of teaching MRI experiments around clinical-intent contracts, resolved parameters, and observation provenance. The audit also exposes unresolved links between those contracts and numerical execution. These findings support further development of a research software prototype, while clinical protocol optimization and diagnostic benefit remain unvalidated. Current experiments use teaching gradients and idealized forward models, are not connected to a scanner, and do not establish hardware safety. Executable-sequence and licensed-local-compute milestones remain parked.

## Claim-to-evidence ledger (editorial notes, not abstract body)

| Claim | Repository or run evidence | Boundary |
| --- | --- | --- |
| 400 Python / 82 web and TypeScript pass | `evidence/integration-pytest.txt`, `integration-web.txt`, `integration-tsc.txt` | Test counts are not accuracy estimates or independent scientific samples |
| Both API paths succeed and carry provenance | `*-validation.json`, `*-response.json`, `summary.json` | In-process TestClient; no browser or public service validation |
| 0.212594 / 0.300535 / 0.086844 a.u. | `summary.json` → `diagnostic_pairs_not_objective_scores` | Rounded from separate tissue runs, not objective output or clinical CNR |
| Declared 16 / executed 4 echoes | `*-request.json`, `*-plan.json` parameter states; `templates.py::_echo_count` | Must repair and rerun before treating recipes as intended protocols |
| Ideal CPMG independent reference test | `evidence/targeted.txt` → `test_three_echo_cpmg_train_matches_independent_t2_envelope` | Existing analytic test passed; not validation of the complete vertical scenarios |
| Clinical vectors not evaluated; knee mismatch | `summary.json` graph_objective and legacy pair; `objectives.py` | Results explicitly disclose this gap |
| Clinical / hardware / B/C boundaries | `PHYSICS.md`, `ARCHITECTURE.md`, protocol platform spec; audit | Preserve in all later versions |

Any stronger novelty claim is [待确认：系统性文献对照]. Tissue-prior literature support is [待确认：来源与适用条件]. Independent quantitative validation of the final vertical scenarios is [待确认：修复后参照实验]. Do not replace these placeholders with inferred evidence.
