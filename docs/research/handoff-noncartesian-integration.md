# Non-Cartesian handoff integration (2026-10-29)

The Claude handoff `e1574a8` is based on `9664125`, whereas the continuing
project line already reaches `87c0287` with FINUFFT, moving/pulsatile flow,
CEST/Solomon, MRS and research/study interfaces. Its two-file verification
change is carried forward without a merge or replacement of the newer line.
The historical branch and its untracked `.pi/` and handoff notes stay intact.
No inherited manuscript directory is copied into the current project.

The historical checkout was independently revalidated using its recorded shared
Python environment: **568 passed**, frontend **82 passed**, TypeScript passed.
Four larger-grid tests were adapted into the current suite: 2D iteration stop,
3D work exhaustion, 48×48 memory rejection, and 32×32 family-chain replay.
The strict original image NRMSE target **1e-6** is retained, and its failure is
asserted. Exploratory .15/.05 comparison thresholds from the handoff are not
promoted to evidence of high-precision recovery.

The missing table cell was measured on the historical handoff checkout, with its
own explicit PYTHONPATH and verified source path, on the same label phantom and
acquisition: 3D 32×32 gridding NRMSE **0.5425621821984188**. The current checkout
yields **0.5425557035** after the radial +0.5 Nyquist endpoint-wrap fix in `663ae68`.
Reproduce with:

```python
import numpy as np
from mrqlab_recon.trajectories import _make_nema_like_phantom
from mrqlab_experiment.spatial_imaging import run_spatial_imaging
p=(_make_nema_like_phantom(32)>.4).astype(int)
labels=np.stack([p,1-p,np.roll(p,2,0)])
r=run_spatial_imaging('noncartesian',labels,encoding='stack_of_stars',
    spokes=48,points=32,reconstruction='gridding',max_work=10_000_000_000)
print(r['quality']['nrmse'])
```

This completes that handoff measurement gap. It does not resolve conditioning,
noise/coil/trajectory calibration or echo-weighted non-Cartesian TSE. The later
[FINUFFT coverage](fast-noncartesian-coverage.md) remains a distinct implementation
with its own measured limits. The next physics priority is spatially integrated,
coherence-selected MRS, retaining the incomplete full-platform requirements.
Current-line full verification after adapting the four cases: **750 Python tests
passed** (one existing Starlette/httpx warning). Frontend source is unchanged
from the previously verified 98-test anchor. No push/PR/merge or B/C unlock occurs; teaching/research only.

The two handoff inconsistencies are resolved explicitly in this continuing
record: the historical 16×16 3D chain stops at **data_residual**, with
**converged=true**, as its footnote states (the table's `max_work*` was a typo).
Historical untracked state is **both** `.pi/` and `HANDOFF-TO-CODEX.md`; neither
is staged, removed or treated as project source. The handoff changes verification
only: no solver, gain fit, recalibration, regularizer or reference-image change.
Exact-DFT CGLS here is distinct from the later optional FINUFFT implementation.
