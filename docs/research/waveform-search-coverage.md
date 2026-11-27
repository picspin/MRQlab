# Finite RF waveform optimization with replay

`waveform_search` searches an explicit grid of up to eight scales applied to
one named, authored RF block in a `WaveformBlochPlan`. It retains all other
sequence blocks and tissue values, apart from explicitly declared shared B0
shifts and B1 scale factors. The caller declares one to four finite scenarios,
including a nominal `(0 Hz, 1)` scenario, a point-ADC signal target, an
absolute complex-signal refinement tolerance in a.u., and total work budget.
Every candidate is evaluated at the authored integration setting and again with
twice the number of integration substeps in **each** event interval. This halves
the actual step in every interval, even if angular limits or event timing already
forced smaller steps than the authored maximum. Both runs must pass the target; the maximum
absolute complex difference across **all** ADC samples must be at most the
refinement tolerance. Failure in any scenario makes the candidate ineligible.

Among eligible candidates, the selection minimizes `sum(B1_uT**2 * raster_s)`
for the edited RF block, with original candidate order breaking ties. This is
an RF energy proxy in uT²·s, not absolute power or SAR. The grid and scenarios
are authored finite samples: selection is not a continuous, global, robust
worst-case, scanner-safe, or clinical optimum. B0 is shifted uniformly and B1
scaled uniformly across the declared tissues; there are no field maps or
uncertainty distributions. The result must not be interpreted as measured
biology or a prescription. An eligible candidate still has no phantom or
scanner verification.

The complete grid is preflighted before any spin integration. If its estimated
voxel steps exceed `max_total_work`, the whole request fails before integration
and no steps are coarsened. Invalid candidates remain in the result with their
reasons and cannot win; executable candidates retain the full coarse and
refined simulations, their target outcomes and differences for each scenario.
If none pass there is no selected candidate or fallback preview. Work estimates
are checked again against actual runs. The prior single-run per-call limit
continues to apply independently. No adaptive error bound is implied by
agreement of two step sizes.

`POST /research/records` accepts `execution.type=waveform_search` with a
`WaveformSearch` `parameters` object. The immutable scientific record stores
question, full search input, every result and rejection, selected index,
source/runtime pins, hashes and stages. A record replay recomputes the whole
finite grid under the pinned sources/runtime. The preview uses the first
explicitly named scenario of the selected candidate, and identifies that
scenario; if there is no eligible candidate it contains no signal curves.
The complete complex traces for every scenario remain in the retained result.

## Reproducible synthetic case

The exact request is constructed by `request()` in
`tests/experiment/test_waveform_search.py` using the finite-RF 2x2 teaching
fixture in `test_waveform_bloch.py`. For an ADC magnitude target of at least
0.3 a.u., the nominal scenario and a +20 Hz B0 / 0.8 B1 scenario, with scales
`[0, .5, 1, 2]`, the result is:

| RF scale | Nominal refined magnitude | Perturbed refined magnitude | Eligible |
|---:|---:|---:|:---|
| 0 | 0 | 0 | no |
| 0.5 | 0.2103598276 | 0.1683359763 | no |
| 1 | 0.4199503328 | 0.3362778635 | yes |
| 2 | 0.8337636800 | 0.6694087844 | yes |

The minimum eligible scale is **1**, with edited-block energy proxy
`0.00675 uT²·s`; total work is **29,760 voxel steps**. The largest coarse/fine
complex-sample difference among the scale-1 scenarios is approximately
`4.14e-10 a.u.`, below the authored `1e-7` tolerance. These figures are fixture
results, not calibrated scanner signals or universal accuracy bounds.

Tests cover all candidates, deterministic replay, both outcomes of the target,
refinement rejection, genuine doubled substeps even when the angular bound
dominates, a fine-only pass rejected when the coarse run fails,
invalid input, the all-failed case, exact work accounting, API recording and
computational replay. A monkeypatched integration function proves an over-budget
grid is rejected before any spin evolution. [The sampled Bloch/ADC coverage](waveform-bloch-adc-coverage.md)
describes the independent numerical reference and its remaining physical gaps.

The full source-bound Python suite passed **1175 tests** with one existing
Starlette/httpx deprecation warning. A separate CLI process replayed the full
search record and produced an identical record. No frontend files changed in
this round; frontend tests were not rerun.

Remaining: arbitrary multi-parameter waveform edits, calibrated measurements,
dynamic tissue models and contrast biology, B0/B1 spatial maps, image encoding
and reconstruction, ADC aperture, optimizers beyond finite grids, uncertainty,
independent external data/phantoms, and a physician/agent-facing workflow.
