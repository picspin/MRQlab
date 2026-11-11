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
against it. Controls are deliberately empty: both views are readable but this
adapter does **not** yet implement bidirectional waveform editing. No generic
LLM or doctor usability claim is made.

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
The source-bound Python suite passed **1180 tests**, with one existing
Starlette/httpx deprecation warning; the focused waveform and linked-readout
set passed **21 tests**. A separate fresh CLI process replayed the complete
image/signal record identically. Frontend files were unchanged and frontend
tests were not rerun in this round.

Remaining work includes realistic RF slice selection, multiple RF/refocusing
and coherence pathways, finite ADC aperture, coils, motion/flow/diffusion,
non-Cartesian trajectories, realistic B0/B1 maps, measured input, uncertainty,
image-objective optimization and bidirectional control, as well as external
phantom/scanner evaluation. This is teaching/research software, not scanner
validation or clinical quality certification.
