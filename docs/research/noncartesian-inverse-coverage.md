# Non-Cartesian iterative inverse

Parent anchor: `dac373b` (542 Python / 82 frontend tests). Research/teaching only;
no scanner validation or clinical quality certification. Milestones B/C remain
parked. No hardware/export/licensing boundary is changed.

| Existing component | Missing link | Added evidence |
|---|---|---|
| `spatial.py:radial_acquire` uses true discrete Fourier sums, Cartesian kz | `radial_reconstruct` only local density-normalized linear splatting | `noncartesian.py:RadialFourierOperator` with exactly paired complex forward/adjoint |
| `spatial_imaging.py:run_spatial_imaging` connects tissue simulation and image quality | No actual iterative inverse, convergence/budget diagnostics | Explicit `reconstruction='cgls'`, strict default image NRMSE threshold 1e-6, solver diagnostics and replay |
| Baseline gridding tests quantify approximate phantom recovery | No complex phase/amplitude or adjoint tests | Inner-product identity, direct acquisition equality, absolute complex recovery, undersampling and stop failures |

## Method and replay

CGLS minimizes `||A x - b||²`, starting from zero, with no gain fit, density
rescaling, regularizer, image prior or reference image inside the solver. A is
an unnormalized centered exact discrete Fourier sum with xy in cycles/pixel.
3D uses a centered unnormalized Cartesian kz FFT, whose adjoint is `nz * IFFT`.
The original gridding path and its thresholds remain available for comparison.
This is a small-grid exact-DFT iterative reference, **not a fast NUFFT**. The
linear-operator/adjoint and iterative-inverse distinction follows the
[SigPy iterative-method documentation](https://sigpy.readthedocs.io/en/latest/guide_iter.html);
no SigPy dependency or implementation is imported.

```python
from mrqlab_experiment.spatial_imaging import run_spatial_imaging
r = run_spatial_imaging('noncartesian', labels, encoding='radial',
    spokes=48, points=32, reconstruction='cgls', max_work=10_000_000_000)
r2 = run_spatial_imaging(**r['provenance']['replay'])
assert r2['provenance'] == r['provenance']
```

For 3D labels choose `encoding='stack_of_stars'`. Solver outputs retain measured
relative data residual, residual history, iterations, stop reason, convergence,
actual multiply-term work proxy and conservative allocation estimate. Memory is
checked before allocating the Fourier basis. Work includes basis generation,
every forward/adjoint, and a fresh final measured residual. The experiment adds
acquisition work to inverse work. Historical physical-family provenance is also
retained; this work proxy is not wall time, SAR or scanner cost.

The historical experiment default work budget is still 100 million; callers
requesting a long iterative solve must explicitly supply a larger budget. Work
or iteration exhaustion returns finite current estimates and a diagnostic, never
a claim of convergence. Too little work for initialization/validation, invalid
coordinates/data, or too much basis memory fail before the solve. Default memory
cap is 128 MiB. No matrix is silently coarsened to satisfy a budget.

## Measured acceptance

Fixed 16×16 two-class labels from `_make_nema_like_phantom(16) > .4`, existing
TSE tissue simulation, 48 spokes × 32 samples. 3D stacks `[p, 1-p, roll(p,2,0)]`.
Both methods use identical absolute complex samples; errors have no amplitude
correction. CGLS tolerance 1e-12, maximum 1500 iterations, work budget 10 billion.

| Encoding | Gridding image NRMSE | CGLS image NRMSE | CGLS iterations | Measured relative data residual | Combined work |
|---|---:|---:|---:|---:|---:|
| Radial 2D | 0.4203077153 | 4.9218e-10 | 956 | 9.6615e-13 | 753,988,096 |
| Stack of stars 3D | 0.4180542001 | 2.5672e-10 | 989 | 8.4874e-13 | 2,342,175,744 |

Allocation estimates: 25,395,200 and 25,853,952 bytes. Platform-dependent rounding
may change iteration count; tests use explicit tolerances instead of requiring
these exact counts. Independent complex-valued 2D/3D phantoms with spatial phase
and non-unit amplitude pass unscaled image NRMSE 1e-6. Odd 17×17 and odd/even kz
verify acquisition and adjoint conventions. A 2-spoke example reaches tiny data
residual while failing image NRMSE 0.1: convergence is **not identifiability**.

Tests: `tests/experiment/test_noncartesian_inverse.py` (22 cases). Existing
Cartesian, gridding, PSF and sequence-family tests remain active.

## Remaining gaps

Follow-up: [fast FINUFFT plans and verified limits](fast-noncartesian-coverage.md)
add a matrix-free path while preserving this independent reference.
Preconditioning, noise models/regularization selection,
coil sensitivity/parallel imaging, off-resonance, gradient imperfections,
trajectory calibration and non-Cartesian TSE echo-dependent signal weighting
remain absent. Strong finite-grid conditioning limits recovery outside the
measured small-grid regime; the measured 1e-10 errors are not universal or
clinical guarantees. No frontend entry is added in this phase. Submission files
were not edited; existing inherited `docs/ismrm` history is not new project work.

## Full validation

- Existing shared Python environment, this worktree's pytest paths:
  `python -m pytest tests/ -q`: **564 passed**, one existing Starlette/httpx warning.
- `apps/web`: `npm test -- --cache=false`: **82 passed** (12 files).
- `npx --no-install tsc --noEmit`: passed. Dependencies reused by ignored symlink.
- Staged diff whitespace check: passed; only the four implementation/test/report files.

## Handoff verification carried forward

The two-file verification-only change `e1574a8` (parent `9664125`) was independently
revalidated at **568 Python / 82 frontend** and adapted to the continuing project
in `34e871e` without changing the solver. The original 1e-6 image target remains
strict; none of the 32×32 CGLS cases below establishes that target.

| Encoding | Gridding image NRMSE | CGLS image NRMSE | CGLS iterations | Stop | Data residual | Combined work |
|---|---:|---:|---:|---|---:|---:|
| Radial 2D 32×32 | 0.5456350016 | 0.00891436989 | 1500 | max_iterations | 8.5340e-7 | 4,731,031,552 |
| Stack of stars 3D 32×32 | **0.5425621821984188** | 0.01049566741 | 1055 | max_work | 1.8914e-6 | 9,993,191,424 |

The missing gridding cell was reproduced in both the original handoff and the
current checkout; [commands, source boundaries and corrections](handoff-noncartesian-integration.md)
are recorded separately. CGLS columns reproduce the handoff measurements. The
16×16 3D stop is `data_residual` / `converged=true`, following the handoff footnote.
The exact-DFT reference remains unregularized with no gain fit or calibration.
The later fast NUFFT path has its own independent report and is not attributed
to this Claude handoff. Original `.pi/` and `HANDOFF-TO-CODEX.md` stay untracked
and intact in their historical checkout; no `git clean` was used.
