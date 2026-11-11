# Sampled waveform Bloch and point ADC research adapter

This bounded research adapter connects a declared `LogicalSequenceIR` to the
existing profile-aware lowering and simulates its RF and gradient samples with
persistent static voxel magnetization. Concurrent RF, x/y/z gradient holds,
tissue-specific B0/B1, proton density and T1/T2 enter one rotating-frame Bloch
ODE, integrated by RK4. It exposes complete complex ADC values at individual
sample dwell midpoints and the integrated gradient moment at each sample, with
explicit units. Voxel coordinates cover a single authored 2D plane at `z_m`.
The signal is the unnormalized sum of `Mx + i My`; no gain fit is applied.

Waveform amplitudes are sample-and-hold and change at declared raster edges.
ADC samples are instantaneous points, not finite-duration integration. The
reported gradient moment is `gamma_bar * integral(G dt)` from sequence start;
it is not automatically an encoding coordinate after RF/refocusing. The final
magnetization is a physical-state snapshot, not a reconstructed MR image. This
adapter does not claim an inverse-DFT relationship between the two. The existing
complete Cartesian linked image/vector adapter is unchanged.

A later [bounded sequential Cartesian adapter](waveform-cartesian-coverage.md)
checks the actual gradient moment at every ADC sample before reconstructing and
linking a complex image. It retains the temporal modulation and deliberately
supports only a single RF block without pre/during-RF gradients.

`POST /research/records` accepts `execution.type=waveform_bloch` and typed
`parameters`. Scientific records preserve the question, declared sequence,
tissue labels, numerical settings and optional authored scalar ADC target,
source/runtime pins, full samples, model validation, content hashes and stages.
API/CLI replay uses the same source-bound record mechanism. An omitted target
reports `passed=false`; a target checks only one declared real, imaginary or
magnitude point-signal threshold, in a.u. It is not a clinical target or image
quality certification. A failure remains visible, with no best-candidate or
fallback. A later [finite RF-scale search](waveform-search-coverage.md) reuses
this adapter. Bidirectional image editing and a physical MR image are not
claimed for this adapter.

Preflight bounds include 32 blocks, 4096 combined waveform/ADC samples, a maximum
.2 s sequence, a 2..16 by 2..16 grid and at most two million voxel integration
steps; a budget failure does not coarsen time steps. RF amplitudes are bounded
at 1000 uT solely as a computational input domain, not as a scanner or SAR
limit. Lowering applies the named `research-3t` profile; successful lowering
still requires hardware review and is not scanner authorization. Unsupported RF
carrier frequency and ADC receiver frequency offsets fail closed. A bounded
constant ADC phase offset is supported as described below.

## Independent check and numerical limits

`tests/experiment/test_waveform_bloch.py` compares every complex sample in a
heterogeneous 2x2 fixture against an independently constructed 4x4 affine Bloch
matrix, advanced by scaling-and-squaring Taylor exponentials over independently
enumerated intervals. The fixture includes RF while a spatial gradient is on,
T1/T2, two B0/B1 tissue states, readout gradient and two ADC midpoints. It also
checks the gradient integral, a tighter-step comparison, repeatability, explicit
work failure, unsupported inputs, and scientific API/record computational
replay with both a missing and an authored signal target.

For this fixture's first complex sample, absolute errors versus the independent
reference were approximately `3.69e-7`, `4.55e-9`, `3.77e-10`, and `8.57e-13`
for maximum integration steps of 10, 2, 1, and .2 microseconds respectively.
These values are scenario-specific convergence evidence, not a universal error
bound. The default maximum step is 10 microseconds and the conservative angular
step preflight can further subdivide intervals; it is not an adaptive error
estimator and a passing signal target does not establish numerical convergence.
The user must refine the time step for the actual study.
The optional `substeps_per_interval` setting multiplies the number of steps in
every event interval after its time and angular limits have been applied. A
factor of two therefore halves each actual step, including intervals which
would otherwise already be shorter than `max_step_s`.

On the source-bound aligned worktree, the complete Python suite passed **1167
tests** with one existing Starlette/httpx deprecation warning. The related
waveform, operation and scientific-record tests passed **73 tests**; a separate
fresh CLI process also replayed an exported waveform record successfully.
Frontend files did not change and frontend tests were not rerun in this round.

Remaining work includes finite ADC aperture, RF carrier and receiver frequency
offsets, full 3D volumes and multi-coil reception, measured B0/B1, diffusion,
flow, exchange and contrast dynamics, general pulse/trajectory optimization, explicit
encoding models and reconstructed image linkage, independent scanner/phantom
comparisons, uncertainty and browser-facing entry. This is teaching/research
simulation, not scanner validation or clinical quality certification.

## Constant receiver phase

Each ADC window can declare a constant `phase_offset_rad` in the bounded
research domain `[-1e6, 1e6]` radians. At every dwell midpoint this adapter
returns `sum(Mx + i My) * exp(-i * phase_offset_rad)`. The phase is a receiver
coordinate convention: it does not alter spin evolution, gradient moments,
sampling times or the preflight work budget. Real and imaginary targets apply
to the resulting receiver-frame signal; magnitudes are invariant. Distinct ADC
windows may declare distinct phases. The original sequence and phase are kept
in the replay input and the convention is included in the result provenance.

A Cartesian inverse DFT uses those acquired complex samples directly: varying
phase across samples can change the image and is not automatically corrected.
The test compares the rotated complex samples and reconstructed image against
an independently assembled direct DFT and checks the linked signal/image pair;
a separate record test recomputes a nonzero-phase input. Pulseq describes ADC
phase as a receiver offset and samples at dwell centers ([specification](https://pulseq.github.io/specification.pdf),
[timing](https://pulseq.github.io/pulseq_shapes_and_times.pdf)); this adapter's
explicit sign convention is a project model and has not been compared with a
scanner or external Pulseq interpreter. Receiver frequency, phase modulation,
finite aperture and scanner-specific phase conventions remain unsupported.

For this change, the focused waveform/Bloch/Cartesian/search/lab-derived set
passed **26 tests** and the source-bound full Python suite passed **1202 tests**,
with one existing Starlette/httpx deprecation warning. Frontend files did not
change and frontend tests were not rerun for this backend change.
