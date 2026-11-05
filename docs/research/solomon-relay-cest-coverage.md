# Distance/tau-derived Solomon relay in joint CEST/MT

Parent `75dcbaa`; entry `cest_solomon.run_cest_solomon`, research API kind
`cest_solomon`, Research page **CEST / Solomon relay**. Research/teaching only;
no scanner/clinical quality certification, molecular-cohort fit, submission
material or Milestone B/C promotion. The previous effective rNOE pool remains
available as a distinct model.

## Mechanism, rates and supported assumptions

A non-exchangeable donor at -3.5 ppm couples to a labile bridge at +1 ppm via
signed Solomon longitudinal cross-relaxation. The bridge chemically exchanges
with water. **Donor↔water chemical exchange is identically zero.** Amide/amine
CEST and longitudinal semisolid MT evolve in the same affine system.
The two-step physical pathway is motivated by the primary
[chemical-exchange-relayed NOE study](https://pmc.ncbi.nlm.nih.gov/articles/PMC9817467/).
That paper's phenomenological simulation and phantom results are not reproduced
or used as a calibration here.

For an isotropically tumbling proton pair, the implementation uses
`J(ω)=τc/[1+(ωτc)²]`, in seconds, and SI dipolar angular coupling
`b=(μ0/4π)γ²ℏ/r³`. With `d=b²/10`, transition rates are:

- `W0=d J(ωI-ωS)`, `W2=6d J(ωI+ωS)`;
- `W1I=1.5d J(ωI)`, `W1S=1.5d J(ωS)`;
- `ρI=W0+W2+2W1I`, `ρS=W0+W2+2W1S`, `σ=W2-W0`.

The signed pair relaxation convention and homonuclear spectral-density limit
follow the [Xplor-NIH relaxation-matrix documentation](https://bit.niddk.nih.gov/xplor-nih/doc/current/xplor/node491.html).
Here γ and all ω are rad/s units; the code restores the SI magnetic prefactor.
It records the conventional approximation `μ0/4π=1e-7`,
`ℏ=1.054571817e-34 J·s`, frequencies, b, all four transition rates, ρ and σ.

For equilibrium deviations, `dδZI/dt=-ρI δZI-σ δZS`, and conversely for S.
The affine thermal source includes both self and cross terms. This is **not**
a one-way positive exchange rate or a negative chemical exchange rate. Rapid
motion gives σ/ρ→+1/2; slow motion gives σ/ρ→-1. The resulting conditional water
contrast may reverse sign, and is never clipped or gain-fitted.

The model is high-temperature, high-field, Markov/secular and longitudinal-pair
based. Supported inputs: B0 0.05–20 T, distance 0.1–2 nm, τc 1 ps–1 µs, chemical
shifts within ±100 ppm, plus the declared weak-fluctuation guard `b τc≤0.05`.
These are implementation bounds, not proof of physical accuracy throughout that
parameter box. Two one-to-one paired proton densities must be equal; unequal
pool multiplicities require another model. The default pair density is 0.02
**per water equilibrium density of 1**, not a fraction of the total pool sum.

Authored background T1/T2 remain explicit in the liquid-system record. Dipolar
spin-flip transverse decay `ρ/2` is added, but dipolar pure dephasing and full
Redfield cross-correlated coherences are **not derived**. Thus this is a minimal
mechanistic relay, not a complete molecular spin-diffusion simulation. The water,
amide, amine, bridge and donor defaults are synthetic teaching priors.

## Controls, MT boundary and optimization semantics

Five spectra retain the same equilibrium pool densities:

| Spectrum | Disabled component | Interpretation |
|---|---|---|
| full | none | All couplings concurrent |
| no_cross | σ only; retain self ρ and spin-flip R2 | Conditional cross-relaxation effect, not a newly realizable molecule |
| no_bridge_exchange | balanced bridge↔water rates | Disconnect the relay; also changes bridge direct CEST |
| no_amide | balanced amide↔water rates | Conditional amide exchange effect |
| no_mt | balanced semisolid↔water rates | Conditional MT effect |

No-cross minus full water Z at the donor resonance is the relay contrast.
No-amide minus full at +3.5 ppm is the amide contrast. Both must exceed 0.005
by default. These control differences are conditional and need not add to the
full spectrum. They are not calibrated biomarker concentrations.

The canonical Super-Lorentzian MT rate is reused. **Zero offset still fails
closed**, without clamping or a finite rate replacement. Choosing Gaussian is
an explicit different lineshape, permitting a finite zero-offset demonstration.
A generalized near-resonance semisolid model remains absent.

Each offset/control starts at equilibrium; CW and rectangular pulsed trains
interleave the same joint generator with zero-RF recovery. Offset history,
shaped saturation RF, readout transients, spatial B0/B1 and image reconstruction
remain outside this model. RF energy is µT²s, not SAR. Duration and matrix-work
proxies include all controls and the unsaturated reference; budgets are checked
before each exponential. They are not native RSS, execution-time or scanner limits.

The **design search varies saturation pulse parameters only**: B1, saturation
or pulse/gap timing and pulse count/mode. Molecular distance, τc, pair density
and exchange properties remain fixed priors; candidate patches changing them
are rejected by this API search. Separate runs allow molecular sensitivity
comparisons. A grid-selected feasible design can still fail its reported targets;
this is not clinical protocol selection.

## Reproducible evidence and measured outcomes

The [saved evidence](examples/solomon-cest-evidence.json) contains full spectra,
controls, rates, state hashes, all pulse candidates, molecular sensitivity runs,
CW/pulsed comparisons, bridge-disconnected and doubled-distance cases, zero-offset
failure and explicitly selected Gaussian. It includes source/dependency and
runtime manifests plus a reproduction-script hash.

```sh
uv sync --locked --extra dev --extra noncartesian
python scripts/verify_solomon_cest.py --output /tmp/solomon-cest-replay.json \
  --verify docs/research/examples/solomon-cest-evidence.json
```

The output path must be new. Independent-process recomputation matched every
portable JSON field exactly. The initial verifier compared in-memory pool tuples
to JSON lists and falsely rejected an otherwise numerically identical run; it
now normalizes to the portable JSON representation. A real subprocess regression
checks both complete roundtrip and rejection of tampered spectra.

At B0=3 T, distance=0.25 nm, B1=1 µT and 1 s CW:

| τc (s) | σ (s⁻¹) | Donor relay contrast | Teaching targets |
|---:|---:|---:|---|
| 1e-10 | +0.113144 | -0.00120443 | FAIL |
| 1e-9 | +0.158108 | -0.00163547 | FAIL |
| 1e-8 | -2.279072 | +0.02270754 | PASS |

The default amide contrast is 0.03701203 and unsaturated water is
0.99999999999917. With bridge exchange disabled, the water cross-relaxation
contrast is exactly 0 in the saved run. Doubling distance reduces all dipolar
rates by exactly 64 within floating-point tolerance; full nonlinear CEST
contrast itself need not follow a sixth-power law.

At fixed τc=1e-8 and the same molecular priors, pulse candidates give:

| B1 (µT) | Relay contrast | Amide contrast | Targets |
|---:|---:|---:|---|
| 0.1 | 0.00217452 | 0.01256130 | FAIL |
| 1 | 0.02270754 | 0.03701203 | PASS |
| 2 | 0.01812260 | 0.01683762 | PASS |

The finite grid selects 1 µT for maximum relay contrast; failed 0.1 µT remains
in the record. This synthetic result is not a biological optimum.

## Verification and remaining requirements

Independent checks: four-state bidirectional population transition network
versus the Solomon sum/difference eigenmodes (max error **2.50e-16**), a separately
coded complete Cartesian RK4 ODE, no-RF thermal equilibrium, zero-pair regression
to the existing joint CEST/MT generator, liquid-pool permutation, PSD/equal-density
guards, distance/fast/slow limits, relay disconnection, signed target failure,
CW/zero-gap equivalence, recovery gaps, budgets and explicit lineshape failure.
The model pins its imported direct physics sources and rejects recording after
a live source change. API replay additionally pins the project source; environment
and all source hashes are preserved by the evidence harness.

Full Python **746 passed**, one existing Starlette/httpx warning; frontend **98
passed** in 14 files; TypeScript and production build pass. Production browser
verified actual model execution, failed signed contrast, pulse-only candidate
comparison, result-hash replay and complete candidate-hash replay. Native JSON
file download/re-import was not retested. The protocol catalog remains locked
at two Milestone A entries.

Remaining: full microscopic multi-spin/Redfield coherence and relaxation,
unequal pair multiplicities and spin diffusion, generalized semisolid MT near
resonance, measured molecular priors and identifiability/uncertainty, shaped
pulses and offset/readout history, spatial joint MT/NOE acquisition/reconstruction
and clinical calibration. The overall lab-to-clinical research platform goal
remains active. Historical example records retain their original source anchors.
