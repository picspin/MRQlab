# Joint CEST, MT and effective rNOE

Parent: `60fb11b`. Teaching/research homogeneous model; no scanner validation,
clinical quality certification or calibrated biomarker claim. B/C stay parked.

| Existing component | Missing link | This phase |
|---|---|---|
| N-liquid `LiquidPoolSystem`, affine CW/pulsed BM saturation | Separate liquid and two-pool MT models cannot evolve concurrently | Reuse/refactor `liquid_bm_generator`; couple liquid Cartesian states to semisolid longitudinal Z |
| Canonical `super_lorentzian_absorption_rate` | RF attenuation separate from liquid exchange | Concurrent semisolid absorption, exchange and recovery in one affine matrix |
| Family CEST controls/search | No upfield effective rNOE or MT-aware target | Four control spectra, explicit +3.5 amide objective and -3.5 upfield effect, power grid with budgets |

## Model and sources

Four liquid-like pools: water, amide (+3.5 ppm), amine (+2 ppm), effective rNOE
(-3.5 ppm). These have full Mx/My/Mz BM evolution. One semisolid MT pool has only
Z and exchanges longitudinally with water. Water transverse coherence is lost
on entry into the semisolid pool. Detailed balance fixes the reverse rates
from density ratios, retaining thermal equilibrium without RF. No transverse
semisolid state or fictitious hard-RF rotation is added.

This structure is grounded in the original
[combined CEST/MT model](https://pmc.ncbi.nlm.nih.gov/articles/PMC4297271/)
and [five-pool CEST metric study](https://pubmed.ncbi.nlm.nih.gov/27170222/).
The upfield BM pool is a **phenomenological effective transferred-NOE model**,
not a microscopic Solomon dipolar cross-relaxation network or inference of a
molecular NOE rate. Default values are declared teaching parameters, not a
reproduction of a tissue cohort or a patient calibration.

The existing canonical Super-Lorentzian rate is reused with the same units and
quadrature. Its central singularity at exactly zero offset **fails closed**;
there is no offset clamp, rate cap or implicit lineshape replacement. An explicit
Gaussian option permits zero-offset spectra, but represents a different physical
lineshape and is recorded in provenance. Near-zero SL quadrature accuracy and
non-Markovian semisolid effects remain gaps.

The affine generator evolves saturation, exchange and relaxation concurrently.
Pulsed trains explicitly interleave RF and zero-RF propagation; zero-gap trains
match CW. Each offset starts from equilibrium independently. Raw water Mz is
normalized by declared water equilibrium density, without spectrum gain fitting.
An independently executed unsaturated control remains 1 to 1e-11.

## Design, controls, search and replay

```python
from mrqlab_experiment.cest_mt_noe import run_cest_mt_noe, search_cest_power
r = run_cest_mt_noe()
assert run_cest_mt_noe(**r['provenance']['replay']) == r
s = search_cest_power([.5, 1., 2.], offsets_ppm=[-3.5, 3.5],
                      max_rf_energy_uT2_s=10.)
```

[Replayable default result](cest-mt-noe-example.json) contains the clinical
question, all design parameters, full/no-amide/no-rNOE/no-MT spectra, measurements,
explicit target, input/source/state hashes, liquid rates/densities, controls,
duty cycle, duration, work and RF-energy proxies. All controls retain pool
amounts and direct saturation; the named balanced exchange links are disabled.
Contrasts are conditional control differences, not additive isolated effects.

At B0=3 T, B1=1 uT, 1 s CW, default parameter set:

| Metric | Measured value |
|---|---:|
| Amide contrast: Z(no amide exchange)-Z(full), +3.5 ppm | 0.03779744 |
| Effective rNOE contrast at -3.5 ppm | 0.09154506 |
| MT contrast at +3.5 ppm | 0.12135057 |
| Full MTR asymmetry Z(-3.5)-Z(+3.5) | -0.01310938 |

Amide contrast is positive while full MTR asymmetry is negative. The default
passes its explicitly declared teaching amide threshold 0.005; changing the
target to 0.9 reports failure. MTR asymmetry must not be read as pure amide.
The power grid executes every candidate; RF-budget failures are retained and
an all-infeasible grid returns `best=None`. RF is uT²s, not SAR. Duration/work
include all offsets, all four controls and the unsaturated reference. Work is a
conservative matrix-multiply proxy, not runtime or scanner cost.

## Verification and remaining gaps

20 new cases in `tests/experiment/test_cest_mt_noe.py`: independently written
Cartesian ODE integrated with RK4, thermal equilibrium, exact zero-MT regression
to the pre-existing liquid EPG-X path, non-water pool permutation, full replay,
positive controls and misleading asymmetry, explicit lineshape/zero-offset
behavior, CW/pulsed equivalence, recovery gaps, budgets and failed targets.
Existing two-liquid, MT, Super-Lorentzian, and family tests remain active.

A later [Solomon relay extension](solomon-relay-cest-coverage.md) adds a minimal
distance/tau-derived signed pair with chemical-exchange relay. Remaining: full
multi-spin/Redfield coherence and relaxation, generalized semisolid Bloch
models near resonance, measured pool priors, B0/B1 maps, readout transient and
offset recovery ordering, pulsed RF shapes, parameter identifiability/uncertainty,
spatial joint MT/rNOE acquisition/reconstruction, and clinical calibration.
No front-end entry yet; no promotion of the locked protocol catalog. Submission
content was neither authored nor changed.

Full-suite validation: Python **603 passed** (one existing Starlette/httpx
warning); frontend `npm test -- --cache=false` **82 passed** (12 files);
`npx --no-install tsc --noEmit` passed; staged diff whitespace check passed.
