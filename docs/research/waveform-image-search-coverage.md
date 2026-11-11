# Waveform RF search against a sequential Cartesian image target

`waveform_image_search` connects the single-RF sequential Cartesian waveform
adapter to a finite RF-scale search. The caller supplies a complete base plan,
its explicit reconstructed tissue-magnitude-difference target, one named RF
block, up to eight RF scales, up to four authored B0/B1 scenarios including the
nominal case, separate absolute signal/image refinement tolerances in a.u., and
a total voxel-step budget. The sole RF block is scaled; gradients, timing,
labels, declared image target and optional point-ADC target remain fixed.
Scenario B0 shifts and B1 scale factors apply uniformly to all authored tissues;
they are not measured maps or a distribution of patient variability.

Every candidate is evaluated at the authored integration setting and with
exactly twice as many substeps in each event interval for each scenario. The
maximum difference across all complex ADC samples and all complex reconstructed
pixels must satisfy their respective unchanged tolerances. The declared image
and optional point-signal targets must pass in both runs of every scenario.
Only eligible candidates participate in selection, which minimizes the edited
RF block's `sum(B1_uT² * raster_s)` with original order breaking ties. This
finite-grid value is an energy proxy, not SAR, and no continuous optimum,
clinical decision, or hardware safety follows. If no candidate passes, there
is no selected image or fallback preview. Scale zero is retained as an
inexecutable candidate because the Cartesian adapter requires nonzero RF.

Before any spin integration, the adapter independently sums every piecewise
constant gradient hold at each ADC midpoint and verifies the complete Cartesian
trajectory; the full candidate/scenario/refinement work is also preflighted.
A wrong trajectory or aggregate work-budget excess fails without integrating a
candidate. During each run the simulated time and gradient moments are checked
against the independent trajectory preflight. Candidate failures, numerical
outputs, target outcomes, estimated work and eligibility remain in the result.
The budget counts voxel integration steps, not all Python/native memory or
preflight costs; it is not hard OS resource containment.

`POST /research/records` accepts `execution.type=waveform_image_search`.
The record retains the original question, all candidates and scenarios, full
complex images and signal vectors, linked pairs, source/runtime pins, target
results, work and selection. Integrity checks bind each scenario's retained
inputs to its authored candidate, verify linked image/signal data, recompute
image and signal target measurements, check both refinement differences,
aggregate work, eligibility and selection, and ensure a selected preview
matches the corresponding result. A no-selection record has no fallback image
or curve. For candidates declared inexecutable, integrity checks their recorded
state but do not independently rerun their rejection; computational replay is
required to re-establish it. Full computational replay recomputes the grid under the original
source/runtime; integrity alone is not authenticity or physical validation.

## Reproducible teaching case

`request()` in `tests/experiment/test_waveform_image_search.py` constructs the
2×2 synthetic sequential-ADC case from `test_waveform_cartesian.py`. Its image
target is a target-minus-reference mean magnitude difference of at least
`0.01 a.u.`; the two scenarios are nominal and a uniform `+20 Hz` B0 shift
with `0.8` B1 multiplier. Both signal and image refinement thresholds are
`1e-6 a.u.`. With scales `[0, 0.1, 0.5, 1]`:

| RF scale | Nominal refined difference (a.u.) | Perturbed refined difference (a.u.) | Outcome |
|---:|---:|---:|:---|
| 0 | — | — | Not executable: nonzero RF required |
| 0.1 | 0.00485835 | 0.00386011 | Target fails |
| 0.5 | 0.02427769 | 0.01929340 | Eligible; selected |
| 1 | 0.04846744 | 0.03854207 | Eligible |

The selected edited-block energy proxy is `0.0016875 uT²·s`; all eligible and
ineligible executable calculations consume **124,920 voxel steps**. For the
selected nominal candidate, maximum complex signal/image differences between
the two refinements are approximately `1.58e-9` and `1.55e-9 a.u.`. An
independent affine Bloch matrix exponential and direct inverse DFT check its
nominal image target to absolute tolerance `1e-9 a.u.`. This is a synthetic
small-grid result, not a universal reconstruction or numerical error bound.

Tests also cover a fine-only target pass, optional signal-target failure,
image-refinement failure, an all-failed grid, trajectory and budget preflight
with spin integration monkeypatched to fail if called, full record replay, and
rehashed inconsistent target, refinement and preview fields. No front-end
control, general waveform optimization, measured contrast biology, scanner
validation or clinical quality certification is claimed. The underlying
[Cartesian adapter](waveform-cartesian-coverage.md) documents its one-RF,
no-pre/during-RF-gradient and point-ADC restrictions.

The source-bound full Python suite passed **1192 tests** with one existing
Starlette/httpx deprecation warning. The focused waveform/search/edit set
passed **25 tests**, and a separate CLI process reproduced the complete
image-search record identically. No frontend files changed; frontend tests were
not rerun in this round.
