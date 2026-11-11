# Sequential waveform ADC to Cartesian image

`waveform_cartesian` connects the sampled-waveform Bloch model to a complete
2D Cartesian point-ADC reconstruction. The user provides the waveform, tissue
labels and acquisition-order centered `[ky, kx]` grid indices. The adapter
requires a complete, unique grid with one ADC sample per grid point; exactly
one nonzero RF block; and no nonzero gradients before or during that RF block.
Subsequent gradients are integrated from the sequence start. These restrictions
make that integral meaningful for the one transverse coherence pathway in this
bounded adapter; shaped slice selection, refocusing and multi-path coherence
are not supported. Unsupported cases fail rather than receive misleading
trajectory coordinates.

The Bloch convention uses positive phase `+2π gamma_bar ∫G·r dt`, while the
centered forward DFT uses negative phase. Thus an observed `(kx, ky)` gradient
moment must match `(-(ix-nx//2)/FOV, -(iy-ny//2)/FOV)` in cycles/m for each
claimed index; the z moment must be zero. The user-declared absolute tolerance
is capped at `1e-3 cycles/m` and all actual and expected moments and the maximum
error are retained. A mismatch is an error, not a gridding or gain-fitting step.
The inverse DFT acts on the *actual acquired sequential samples*, not on the
final spin snapshot. T1/T2, B0 and B1 influence the Bloch signals, and temporal
modulation is retained. ADC samples remain instantaneous dwell midpoints.

The result contains a full complex reconstructed image and complete complex
signal vector in acquisition order, with real sample times. They also use the
existing linked image/vector schema and source/runtime/input pins. Its inverse
DFT integrity check proves the algebraic image/signal relationship only: it
cannot prove that temporally distinct data are a static object, that the
acquisition physics are independently correct, or that an image is clinically
accurate. Record integrity checks require the pair and compare the retained
image, magnitude preview, complex samples, times, grid indices and curves
against it. The controls described below are exposed identically to both
views. No generic LLM or doctor usability claim is made.

## Bounded semantic edits

`edited_waveform_cartesian` accepts one to eight typed edits from the image or
signal-vector view. RF waveforms with at most 32 samples expose each sample's
amplitude (uT) and phase (rad). Larger RF waveforms remain readable but expose
no partial RF sample controls. Each named tissue exposes proton density, T1, T2,
B0 and B1 within explicitly declared research bounds. The unchanged parent
pair supplies the adapter-owned control descriptors; input fingerprint,
descriptor equality and pair integrity are checked before an atomic edit.
Duplicate or out-of-bounds edits, unbound tissue IDs and forged capabilities
fail closed. Gradients, geometry, label grid, acquisition order, numerical
settings and the declared image and signal targets are read-only in an edit.

The parent is computationally replayed first, then the edited inputs are fully
lowered, simulated, trajectory-checked, reconstructed and target-checked. A
child embeds its parent and records both parameter fingerprints, typed edits,
results and source/runtime pins. Both views produce identical numerical results
for the same edit; the parent is not mutated. Up to three same-adapter edit
generations are supported, with mixed lineages rejected. These are semantic API
controls over a synthetic study, not a verified clinical UI or an LLM agent.

In the 2×2 fixture, setting all three RF samples from 15 to 0.1 uT changes the
target/reference magnitude difference from `0.0484674` to `0.000323898 a.u.`;
the unchanged 0.01 a.u. image target then fails. Both image and signal views
produce this same failed result; no target is relaxed or fallback selected.

An optional authored image target compares the mean reconstructed **magnitude**
in two declared synthetic label regions using `ge` or `le`. If a waveform point
signal target is also supplied, both must pass. With no image target, validation
reports false; it never invents a target. These are research model targets, not
patient images, diagnoses, or clinical validation. `POST /research/records`
accepts `execution.type=waveform_cartesian`; it retains the full sequence,
labels, acquisition order, linked result, optional targets, validation, hashes,
source/runtime manifest and supports computational replay.

## Independent validation

`tests/experiment/test_waveform_cartesian.py` constructs a 2×2 synthetic tissue
plane, finite RF and explicit x/y gradient waveforms producing four sequential
ADC grid points. An independently assembled affine Bloch matrix, advanced by a
scaling-and-squaring Taylor matrix exponential and independently evaluated
T2/phase evolution, predicts each complex ADC sample. A separate direct inverse
DFT checks every reconstructed complex voxel. In this fixture, maximum signal
error with 0.5 microsecond maximum integration step is about `2.53e-10 a.u.`;
the maximum gradient-moment mismatch is `1.78e-15 cycles/m`. Halving the
maximum step from 1 to 0.5 microseconds reduces error by more than a factor of
four. Compared with an independent simultaneous-first-sample reference, the
sequential image differs by up to `0.0017154 a.u.` because of the authored T2
modulation. The target/reference magnitude difference is `0.0484674 a.u.`;
the authored 0.01 a.u. threshold passes. The run uses 13,340 voxel steps.
These results apply to this synthetic fixture, not a universal accuracy bound.

Tests reject incomplete/duplicate grids, incorrect trajectory mapping,
pre/during-RF nonzero gradients and unbound target tissues, and preserve failed
or absent targets. They check API output and source-bound computational replay.
At the preceding `fe4dd5b` anchor, the source-bound Python suite passed **1180 tests**, with one existing
Starlette/httpx deprecation warning; the focused waveform and linked-readout
set passed **21 tests**. A separate fresh CLI process replayed the complete
image/signal record identically. Frontend files were unchanged and frontend
tests were not rerun in this round.

After adding the bounded parent/child edit contract, the full source-bound
Python suite passed **1186 tests** with the same warning. The focused
waveform, operation and linked-edit set passed **54 tests**. A fresh CLI
process recomputed an edited child and its embedded parent and returned an
identical record. Frontend tests were not rerun because no frontend changed.

Remaining work includes realistic RF slice selection, multiple RF/refocusing
and coherence pathways, finite ADC aperture, coils, motion/flow/diffusion,
non-Cartesian trajectories, realistic B0/B1 maps, measured input, uncertainty,
image-objective optimization and general waveform/gradient control, as well as external
phantom/scanner evaluation. This is teaching/research software, not scanner
validation or clinical quality certification.
