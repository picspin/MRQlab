# Abstract draft — ISMRM 2027 Vancouver

Software / teaching prototype scope; revised after execution repairs. Ready for author editing and portal formatting; user-owned fields and final scientific approval remain pending. No submission has been made.

Title: MRQlab: Traceable MRI Experiment Contracts for Teaching-Oriented Protocol Exploration

Submission year / meeting: ISMRM 2027 Vancouver

Submission category: [________]

Authors and order: [________]

Affiliations: [________]

Corresponding author and contact: [________]

Keywords: [________]

Funding / disclosures / ethics declarations: [________]

## Purpose

MRI simulation can illustrate magnetization evolution, but interpreting a simulated protocol also requires knowing which tissue assumptions, parameter values, and approximations entered the calculation. We developed MRQlab as a research and teaching software prototype linking structured clinical intent to resolved experiment plans and provenance-bearing observations. We assessed software contract integrity and repaired discrepancies between declared protocol intent and executed calculations.

## Methods

The platform represents sequences, synthetic tissue priors, scanner descriptions, objectives, and readouts in an experiment graph. Compilation and capability selection connect the graph to existing propagation methods. Clinical recipes identify target, reference, and confounding tissues; resolved plans record parameter units, sources, approximations, and canonical fingerprints. We added regression tests before repairing echo-count consumption, default named objective evaluation, reference-tissue selection, and multi-tissue extended phase graph (EPG) aggregation. Each tissue is propagated independently and complex signals are averaged with normalized weights. The teaching recipes use equal weights. Brain lesion T2/TSE and knee cartilage/meniscus PD/T2 TSE recipes were run through the local application API. Complete Python and web suites and TypeScript checks were run. An existing ideal CPMG test provides an independent exponential relaxation reference, while separate tissue runs check aggregate consistency.

## Results

The repaired revision passed 409 Python tests and 82 web tests; TypeScript checking passed. Both recipe paths returned successful validation and execution responses, with provenance-bearing signal, trajectory, illustrative image, named tissue contrast, and objective-score observations. Each recipe declared and executed 16 echoes, producing 32 ADC samples. Executed mean signal differences were 0.193220 a.u. for lesion versus white matter, 0.089169 a.u. for meniscal tear versus meniscus, and 0.024743 a.u. for cartilage versus meniscus. These are synthetic teaching signal differences. The objective combines declared named metrics and weights; its normalized contrast proxy uses a fixed assumed noise denominator rather than measured clinical noise. Aggregate API signals matched the complex average of independent tissue runs. Acquisition constraints and robustness scenarios remain declarations without evaluated satisfaction.

## Conclusion

MRQlab links teaching MRI experiment contracts to explicit numerical execution and inspectable provenance. Regression-driven repairs aligned declared echoes, named tissue comparisons, objective evaluation, and multi-tissue aggregation. Clinical protocol optimization, diagnostic benefit, and anatomical image fidelity remain unvalidated. The prototype uses teaching gradients and idealized models, is not connected to a scanner, and does not establish hardware safety; relative SAR is not W/kg. Executable-sequence and licensed-local-compute milestones remain parked.

## Evidence ledger — exclude from portal abstract

| Claim | Evidence | Boundary |
| --- | --- | --- |
| 409 Python / 82 web, TypeScript pass | `evidence/fix-pytest.txt`, `fix-web.txt`, `fix-tsc.txt` | Software tests, not independent clinical samples |
| 16 echoes / 32 samples and named differences | `evidence/summary.json`, requests, plans, API responses | Rounded to six decimal places; synthetic priors |
| Default vector and aggregate execution | `tests/ismrm/test_execution_gaps.py`, API responses | No constraint solver or optimization search |
| Ideal CPMG reference | full Python suite: `test_three_echo_cpmg_train_matches_independent_t2_envelope` | Does not independently validate full vertical scenarios |

No priority or superiority claim. Prior literature support, systematic comparisons, clean-environment replay and browser demonstration remain unverified and are not claimed. Final meeting format, title, metadata and figures require user review.
