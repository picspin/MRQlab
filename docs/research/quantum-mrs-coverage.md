# Quantum-relaxed MRS and complete TR replay

This continuation of `7fef144` adds research kind `mrs_quantum` and the twelfth
research entry, **MRS / quantum TR**. It addresses the previous scalar-T2 and
equilibrium-reset limitations with explicit small-spin density evolution and a
complete repeated acquisition channel. The existing scalar-relaxation MRS and
three-dimensional PRESS entries retain their own physics and historical records.
The new quantum chain is homogeneous and is **not yet coupled to 3D PRESS**.

## Physical model and boundaries

The finite Hamiltonian retains chemical shifts, isotropic J and complex RF
concurrently. The new physics helper constructs column-major Liouvillians:
`L vec(rho) = vec(-i[H,rho] + sum D[C](rho))`, with
`D[C](rho) = C rho C† - (C†C rho + rho C†C)/2`.
Each spin has independent raising/lowering rates `(1+p)/(2*T1)` and
`(1-p)/(2*T1)`, and pure-dephasing collapse operator
`sqrt(2*(1/T2-1/(2*T1))) * Iz`. Inputs with `T2 > 2*T1` are rejected;
negative rates are never clipped to make a model executable.

This phenomenological local bath specifies the relaxation of multi-spin orders
rather than applying one scalar signal envelope. It is distinct from molecular
Redfield or correlated dipolar relaxation. The distinction between empirical
T1/T2 models, Lindblad dynamics and molecular relaxation is also documented in
the primary [Spinach relaxation guide](https://spindynamics.org/wiki/index.php?title=Relaxation_theory_parameters).
For density/operator and evolution conventions see
[Bengs and Levitt, SpinDynamica](https://pmc.ncbi.nlm.nih.gov/articles/PMC6001486/).
No external code, metabolite library or spectra are imported.

The initial bath product is a unit-trace positive density with the same authored
polarization `p=.01` on every spin. This product commutes with the declared
chemical-shift/isotropic-J Hamiltonian, so it is stationary under the free local
bath. Polarization is not derived from a temperature/B0 model, and this is not
a general interacting Gibbs-state thermalization model. Full density matrices,
including the identity population, propagate without renormalization, Hermitian
repair, eigenvalue/sign clipping, fitted signal gain or a scalar T2 envelope.

The fixed runner uses two authored systems: a singlet at -213.3 Hz with
`T1=1.1 s, T2=.15 s`; and synthetic AB at [-300,-270] Hz, 7-Hz isotropic J,
`T1=[.7,1.7] s, T2=[.08,.18] s`. These are signal-weight examples, not named
validated metabolites or clinical concentrations. The bath/Hamiltonian helpers
support one to three spin-1/2 nuclei; a three-spin channel is independently tested.
The fitting runner does not claim a larger molecular library.

## Finite RF, readout and physical repetition

A sinc-envelope excitation is followed by two 180-degree y-phase refocusers.
Pulse starts are 0, TE/4 and 3TE/4; the echo is at `TE + RF_duration/2` from
preparation start. This entry has homogeneous RF and no spatial gradients,
coherence-path projection or crusher localization. All generated coherences
contribute to the complex signal. It is not a PRESS volume calculation.

Each RF hold exponentiates the complete dissipative generator, including J and
relaxation during the RF itself. Free evolution, every point-ADC dwell and the
post-readout recovery use the corresponding complete quantum channel. The
matrix exponential uses the existing norm-scaled Taylor/squaring helper.
Independent analytic/ODE checks below test its convention and numerical results.
The basis uses 32 RF samples, an independent synthetic sample uses 64, and a
128-sample reference checks sample RF refinement. A separate 32→64 comparison
checks the basis at its own fixed molecular/preparation priors, including for
mismatch controls. No sample is generated from the fitting matrix itself.

Default TE is .03 s, RF duration .001 s, and the 256 ADC points have .0005-s
dwell. The first sample is at .0305 s; the final sample is at .1580 s. The last
dwell ends at **.1585 s**. At TR=.6 s the recovery lasts **.4415 s**.
TR must include the entire ADC interval; there is no silent overlap/truncation.

At ADC end an explicit ideal CPTP dephasing channel removes all off-diagonals
in the product-Iz basis. This models independent-spin dephasing and also removes
zero-quantum off-diagonals. It is not the same as a spatial crusher that only
dephases total coherence order, nor a simulated hardware spoiler. That difference
is a remaining physical limitation, not an inferred scanner property.

The complete TR channel composes finite RF, echo evolution, full ADC duration,
dephasing and remaining recovery. The periodic state solves its trace-constrained
fixed point, retaining its condition number and residual. It is not a reset to
equilibrium before each pulse. An explicitly propagated equilibrium-start dummy
history is also kept. `finite_dummies` instead uses exactly the specified number
of cycles, including zero, and does not claim periodic return. Ill-conditioned
or nonunique periodic solutions fail closed. The periodic solution is checked
against 512 explicit cycle iterations in an independent regression.

Detection is `trace(rho*(Ix+iIy)) / trace(rho_eq*Iz)` summed over the system's
spins. The fixed authored equilibrium normalization is recorded per system.
Nonnegative real signal weights are fitted over the entire complex FID using the
existing active-subset solver. There is no extra amplitude/gain calibration;
the fitted weights are not molarity or water-calibrated concentrations.

Every executed RF boundary, free interval endpoint, ADC dwell, dephasing and
recovery endpoint contributes to trace/Hermiticity/positivity checks and a full
state-history hash. Records retain times, stage labels, longitudinal/transverse
trajectories, start/echo/end/equilibrium/periodic densities, dummy trajectories,
the cycle hash, exact bath rates and spin/RF specifications. Replay recomputes
all states rather than trusting a sampled display trace.

## Targets, optimization and preserved failures

The unchanged study targets are maximum known-synthetic amount error ≤.05,
full-complex-FID residual ≤.02, separate basis/sample RF differences ≤.002,
physical-state/fixed-point/periodic-return errors ≤1e-10, and **each component's
FID norm at least .2 of its fully recovered reference**. That reference starts
from equilibrium and uses the same RF, molecular priors and readout. It is not
a gain fit or measured SNR guarantee. A low-amplitude noiseless signal can still
recover known weights, so amount error alone would be an insufficient TR target.

| TR (s) | Minimum retained component norm | Amount error | Maximum RF difference | Outcome |
|---|---:|---:|---:|---|
| .18 | .1239166322 | .0001369712 | .0001496390 | FAIL retained signal |
| .30 | .2117922124 | .0001169213 | .0001236776 | PASS; selected finite point |
| .60, default | .3956856538 | .0000929760 | .0001050205 | PASS |
| .10 | — | — | — | infeasible: complete acquisition ends at .1585 s |

The search permits only TE, TR, RF duration and excitation flip changes. It
cannot vary the preparation, bath/J priors, basis assumptions, resolution,
budgets or targets. Its objective is minimum TR among candidates passing every
declared gate. The .30-s selection is conditional on this authored noiseless
model and finite grid; it is not a global or clinical optimum. Failed-only
equilibrium-basis searches retain `best: null`.

At default TR, recovered weights are `[.02000129155,.00800074381]` for authored
`[.02,.008]`; residual is `.00004287946`. The same periodic sample fit with a
fully recovered basis gives `[.00791652635,.00315926481]`, **.6050918985** maximum
weight error and **.03354924146** residual: FAIL. Doubling only basis T1 gives
**.7851670354** weight error despite residual **.00401184097**: FAIL. A good
residual does not demonstrate correct quantification. Setting basis J to zero
gives **.5369140388** weight error and **.1447430184** residual: FAIL. These
controls retain their independent RF checks and use the same sample and targets.
A strict RF target of 1e-6 also fails rather than being relaxed.

Default full-path physical-state error is `1.607602959670827e-13`, periodic return
error `1.6497914321032898e-13`, and minimum density eigenvalue about .247921.
Finite-zero/one/eight-dummy cases retain their actual initial states and approach
the periodic solution; a nonperiodic cycle-return difference is not labelled a
failed periodic solve. The complete workflow plans/charges **610,777,088** work
proxy units and estimates peak **6,856,704 bytes**, under explicit 1.5-billion /
128-MiB allowances. These are conservative planning proxies, not measured RSS,
wall time, OS hard containment, SAR or scanner limits. Budget preflight reserves
every basis/sample/reference simulation before allocating channels.

## Independent physical and numerical checks

* Single-spin detuned T1/T2 evolution matches closed diagonal/coherence formulas;
  driven finite-RF dynamics match a separately diagonalized affine Bloch system.
* An entangled two-spin density propagated with zero Hamiltonian matches an
  independently assembled thermal amplitude-damping plus dephasing Kraus map.
* A nontrivial driven coupled channel has a positive Choi matrix and preserves
  trace on all matrix units. Correlated `Ix(a) Iz(b)` decays at `R2(a)+R1(b)`,
  demonstrating why a universal scalar envelope would give a different result.
* A three-spin bath preserves a positive unit-trace density with isotropic J.
* Independent affine Bloch hard-pulse/TR-cycle references give maximum FID errors
  `4.58455478e-7`, `4.58456062e-8`, `4.58471917e-9` at RF durations
  1e-6/1e-7/1e-8 seconds. The finite sequence approaches its declared hard limit.
* A direct Hilbert-space coupled density ODE, without vectorization/channel
  construction, converges to the Liouvillian result. RK4 errors for 128/256/512
  steps are `9.55408643e-10`, `5.97012506e-11`, `3.73087203e-12` (about 16×).

## Records, actual browser and regression

The committed [plan](examples/quantum-mrs-plan.json),
[evidence](examples/quantum-mrs-evidence.json) and
[verification script](../../scripts/verify_quantum_mrs.py) preserve complete
complex FIDs/bases/predictions, failures, independent references, full-run/state
hashes and all inputs/source/runtime/script identities. Evidence is **1,827,796
bytes**; the complete scientific search record is **2,643,889 bytes**, generated
outside source at `/private/tmp/mrqlab-quantum-mrs-7fef144/complete-record.json`.

* Record: `c9ad8e7e2e8bf56c607c0df7204d06a29cf40ce33a6918684beeb2eacbaa319a`.
* Payload: `1c0fe8f0b49bf84a332dc4c064bee24f3b7510478887b3f8599d118473ed9c9d`.

Use fresh output paths in the locked Python environment:

```sh
.venv/bin/python scripts/verify_quantum_mrs.py \
  --output /private/tmp/quantum-mrs-new-evidence.json \
  --record-output /private/tmp/quantum-mrs-new-record.json \
  --verify docs/research/examples/quantum-mrs-evidence.json
.venv/bin/python -m mrqlab_api.scientific_records replay \
  /private/tmp/quantum-mrs-new-record.json \
  --output /private/tmp/quantum-mrs-new-replayed-record.json
```

An independent script execution, new generic CLI process and actual HTTP
create/read/full replay match the entire record and its selected index, retaining
the failed signal point and infeasible timing point. Historical examples were
not regenerated. The API uses a temporary isolated SQLite store for this proof.

Actual in-app browser testing verified default run/replay, explicit equilibrium-
basis failure, edit-clears-old-results, all four search points and the .30-s
selection. A **7,261,721-byte** native research download was reimported through
the actual file chooser; all candidates/selection recomputed to search hash
`8f5da3cee26923bd975d45c070e23e5f1ec97faffb58054e6a63db21d81f34ef`.
The selected result hash is
`529118ae4c52d4274a1aff3646a09b7c192774db228df863d69127d3de6a30e2`.

The browser then recomputed/saved study `browser-quantum-tr-mrs`, followed the
actual record link, natively exported/imported the complete search record and
fully recomputed it, retaining the original selected, failed and infeasible
points. Record ID:
`e1124d589c73ea30019371c1867f4864f85691fc3d8a4a36bf9348d144156f07`;
payload `74a3dc16507a3a81c76c95793fba9709341d624e77055826a05d8fabc67694b1`.
Its context and explicit browser request differ from the CLI plan, so these
record/payload identities are deliberately distinct. Integrity, historical
targets and current computational replay remain separately displayed. Captured
browser console has no error messages. Native files and actual screenshots
(`browser-equilibrium-failure.jpg`, `browser-search.jpg`,
`browser-record-replay-proof.jpg`) remain in the temporary evidence directory.

Full regression: **930 Python passed**, one existing Starlette warning;
**116 frontend passed** in 16 files; TypeScript and production build passed.
React review retained controlled inputs, abort/stale-result handling, labelled
basis selection, numeric alternatives and backend-only physics. Generated static
output is preserved outside source, not committed.

Still missing: coupling this quantum preparation/relaxation to 3D PRESS and real
crusher/phase cycles, calibrated molecular/Redfield relaxation and metabolite
libraries, realistic field/receive/noise models, measured spectra with uncertainty,
water/macromolecule/baseline modeling and clinical concentration calibration.
The other lab-to-clinical platform gaps remain active. No submission import,
push, PR, merge, router change, folder relocation or B/C unlock occurred.
