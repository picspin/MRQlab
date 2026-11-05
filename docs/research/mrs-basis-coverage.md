# Density-matrix MRS basis and full-readout fitting

Parent: `5b660ab`. Research/teaching only; no scanner validation, clinical
quality certification or clinical concentration calibration. B/C stay parked.

| Existing component | Missing link | Extension |
|---|---|---|
| `SpectralBackend`: independent singlets; ideal hard RF | No J-coupled spin system or finite-RF Hamiltonian | 1–3 spin-1/2 density matrices, isotropic/secular J, finite sinc RF with simultaneous chemical shift/J/position-dependent gradient |
| `family_execution`: ideal PRESS slab intersection | No RF bandwidth/chemical-shift response | Explicit two-refocuser teaching timings and x/y/z pulse gradient response at a declared spatial point; **not** a converged PRESS spatial integral |
| `peak_integrals`: fixed windows and water ratios | No full basis fit or mismatch diagnostic | Full complex FID least squares, nonnegative real basis amounts, explicit phase/frequency grid, residual/rank/condition and water reference |

The density-matrix basis method follows the principle in
[FSL-MRS simulation documentation](https://open.oxcin.ox.ac.uk/pages/fsl/fsl_mrs/simulation.html)
and the original [localized spectroscopy simulation study](https://pubmed.ncbi.nlm.nih.gov/18789736/).
No external library/basis data were copied and no phantom/scanner agreement with
those systems is asserted. Numerical tests are independent internal references.

## Model and calibration boundary

Hamiltonian: `2*pi*sum(f_i Iz_i) + 2*pi*sum(J_ij I_i dot I_j)` by default;
secular `Iz_i Iz_j` is an explicit option. Finite sinc RF, its phase, slice
position frequency shift and chemical shift/J evolve concurrently using
Hermitian eigendecomposition. Free FID is evaluated exactly in the eigenbasis.
The internal unitary/state checks retain Hermiticity and trace.

The three finite RF centers are excitation, TE/4, 3TE/4, with observation at TE
relative to excitation center; pulse extents must fit. The three physical slice
gradients act on x/y/z at a specified spatial point. No crusher, coherence-pathway
filter, phase-cycle selection or converged 3D spatial sum is implemented: it is
not a validated PRESS sequence. Chemical shift affects finite-pulse response.
Relaxation is a declared scalar `exp(-(echo_time+t)/T2)` envelope, not a full
quantum relaxation superoperator; no T1/TR preparation correction is inferred.

The default basis has teaching NAA/Cr/Cho singlets and one **synthetic AB pair**,
not a real lactate/glutamate model or a validated metabolite J library. Chemical
shifts are explicit Hz values (-343.6/-213.3/-190.3 and -300/-270 Hz), with
synthetic J=7 Hz. Each system starts with unit total longitudinal polarization.
Fitted amounts are relative signal amounts per normalized spin system, not
molarity. A separately simulated matched water singlet (T2=.2 s) provides a
relative signal reference. No tissue water content, proton stoichiometry,
receiver gain, in-vivo relaxation or concentration calibration is supplied.

## Full fit, target, search and replay

```python
from mrqlab_experiment.mrs_basis import run_mrs_basis, search_mrs_echo
r = run_mrs_basis()
r2 = run_mrs_basis(**r['provenance']['replay'])
assert r2['provenance'] == r['provenance']
s = search_mrs_echo([.001, .02, .04], noise_std=1e-5)
```

The fit uses every complex readout sample. By Parseval this is full-spectrum
least squares; no individual peak window/integration or gain correction is
used. All active subsets are enumerated (at most six basis columns); real
nonnegative amounts and an explicit finite common phase/frequency grid are
fitted. Rank deficiency/condition >1e10 fails; reported condition is conditional
on the fixed basis, not a confidence interval or parameter-identifiability
certificate. Known synthetic truth is used only in post-fit validation/search.

Default: TE 30 ms, 512 points, 0.5 ms dwell, 1 ms RF, 64 RF samples, synthetic
amounts `[.02,.015,.01,.008]`. Nyquist checks conservatively bound possible
Hamiltonian transitions. Simulation and fit-work proxies share the declared
budget; dimensions, samples and phase/frequency grid are bounded.

| Basis used to fit J=7 Hz sample | Max relative amount error | Full-readout relative residual | Target 5% |
|---|---:|---:|---|
| Matching J=7 | 4.44e-16 | 4.31e-16 | PASS (closed synthetic model) |
| J omitted (0 Hz) | 0.8096173 | 0.1442479 | FAIL |

The tiny matched-model error is an algebraic synthetic recovery check,
**not clinical accuracy**. Omission of J is not repaired by calibration or hidden
normalization. Seeded complex noise, a 0.15 rad phase and 2 Hz shift are also
recovered within the declared teaching target when their grids include the true
values. A wrong grid/basis may fail. Echo search executes every candidate;
overlapping pulse timings remain explicitly infeasible.

Provenance retains full replay parameters, source/basis/signal hashes, finite RF
hashes, per-simulation timings/work, fixed basis convention and water reference.
The result retains complex signal, complete basis, fitted prediction and truth.

## Verification and remaining gaps

16 added cases test spin commutators/unitarity, an independent analytic secular
AB doublet, finite RF sample convergence, off-resonance bandwidth, outside-slice
response, J-mismatch failure, full-FID active subsets/zero amount, rank failure,
phase/frequency/noise recovery and replay, invalid designs and budgets.

Missing: validated molecular spin library, full quantum relaxation/T1 preparation,
macromolecule/lipid/background models, drift/baseline/lineshape joint fitting,
uncertainty and robust model selection, crushers/coherence pathway selection,
spatially converged finite-RF PRESS/STEAM localization, water-content/proton-count
correction, scanner/phantom comparison and clinical concentration calibration.
Frontend/API exposure is the next phase; the locked clinical catalog is intact.
No submission content was authored or changed.

Full-suite validation: Python **619 passed** (one existing Starlette/httpx
warning); frontend `npm test -- --cache=false` **82 passed** (12 files);
`npx --no-install tsc --noEmit` passed; staged diff whitespace check passed.
