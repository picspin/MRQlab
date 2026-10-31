# MRQLab

**From spin to pixel.** MRQLab is an open teaching MRI simulator for medical students, MRI technologists, and medical physics students. It makes MRI visible as a time-dependent stream of RF, gradient, ADC, and oscillator events—not a form containing TR/TE/FOV. It is a web learning instrument, **not** a scanner console.

The product center is an experiment (`ExperimentGraph`), compiled through three IR layers into typed `Observation`s.

## Locked documents

| Document | Role |
|---|---|
| [Experiment kernel spec](docs/superpowers/specs/2026-08-15-experiment-kernel.md) | Locked product and architecture contract |
| [Implementation plan](docs/superpowers/plans/2026-08-15-experiment-kernel.md) | Task-by-task delivery (waves A–H) |
| [ADR directory](docs/adr/) | Five accepted architecture decisions |
| [Architecture](docs/ARCHITECTURE.md) | Public experiment-kernel narrative |
| [Physics](docs/PHYSICS.md) | Representation / operator split and capability matrix |
| [Roadmap](docs/ROADMAP.md) | v0.1 hold line and later waves |
| [Contributing](CONTRIBUTING.md) | One seam per PR; ablation gate |
| [ADR-0007](docs/adr/ADR-0007-pr-ablation-gate.md) | Feature PRs must ablate new modules |
| [Agent tool schemas](docs/agent-tools/) | Offline JSON Schema tools over `ExperimentGraph` |

## Monorepo

| Path | Responsibility |
|---|---|
| `apps/web` | Next.js/TypeScript workspace shell (Explore, Editor, Signal Lab) |
| `services/api` | FastAPI boundary: canonical `/experiments/*` plus `/simulate` compatibility |
| `packages/mrqlab_experiment` | Experiment kernel façade (first home; `core/` is the later rename) |
| `packages/sequence-ir` | Shared Pydantic MR Event Graph and SE/TSE/GRE builders |
| `packages/physics` | Shipped NumPy-first microkernel with Bloch, EPG, spectral, and plugin descriptors |
| `packages/recon` | Cartesian FFT adapter and NUFFT seam |
| `docs` | Spec, plan, ADRs, architecture, and roadmap |

## Canonical API

- `POST /experiments/validate` and `POST /experiments/run` are the canonical experiment endpoints. They accept an `ExperimentGraph` and return a `ResultGraph`.
- `POST /simulate` remains a compatibility adapter. It builds an implicit experiment and calls the same application service.
- `GET /presets` feeds clinical-first Explore cards.
- `POST /sequences/build`, `GET /engines`, and `GET /health` are unchanged.

## Research design and replay workspace

Open `/research` from the Research navigation entry with the local API running.
This connects twelve research chains to editable designs, bounded simulation,
finite candidate comparison, explicit validation and complete JSON records:

| Research chain | Evidence and current fidelity |
|---|---|
| TSE image/PSF | Per-echo periodic EPG, complete ideal Cartesian line timeline, tissue PSFs |
| Non-Cartesian inverse | Exact-DFT CGLS reference for small radial/stack-of-stars grids, unscaled amplitude and residual diagnostics |
| Echo-resolved radial TSE | Known two-curve EPG temporal basis, complex inverse, separate component/image targets and constrained pulse search |
| Pulsatile/causal DIR | Pressure-driven rigid-pipe Womersley flow, moving finite-RF spins and causal preparation interruption |
| Flow / encoded EPI | Persistent moving spins, finite slice RF, bipolar moments, actual point-ADC k-space/images and explicit partial/aliased-pair failures |
| Signed Solomon CEST/MT relay | Distance/tau-derived donor-to-bridge cross-relaxation, bridge-to-water exchange and signed control contrasts |
| Finite-memory CEST/MT | Complex finite-RF Green-function convolution, retained phase/gap history, regular zero offset and separate full-trace convergence/contrast gates |
| PRESS volume fitting | Ideal coherence-path selection, finite RF, complex 3D quadrature and independent RF/grid/FOV target checks |
| Quantum-relaxed MRS / TR | Local Lindblad density evolution during finite RF/ADC/recovery, trace-constrained periodic preparation, independent finer RF sample and explicit T1/saturation failures |
| Flow/slice/gating | Persistent spins on prescribed through-plane trajectories, finite RF/Gz, known-trigger retrospective timing |
| Joint CEST/MT/rNOE | Coupled liquid and semisolid pools, effective upfield rNOE, named exchange-off controls |
| MRS basis fit | Small-spin density matrix, finite RF/J coupling, complex full-readout fit and mismatch validation |

The [measured-input TSE study](docs/research/lab-measurement-study-coverage.md)
is available at `/research/lab-study`: explicit-origin CSV → T2 calibration →
independent acquisition holdout → EPG/image/PSF candidate comparison at uncertainty
corners → target validation → atomic local-file record and full computational
replay. Only T2 is calibrated; T1/PD and clinical transfer remain authored or
unvalidated. Its included example is clearly synthetic.

`POST /research/run` and `/research/search` are separate bounded research APIs.
A result records its exact replay request, source fingerprint, runtime, targets
and result hash; search records retain every candidate and the selected result.
A changed source requires the matching code anchor and a restarted API. These
research experiments do not extend the two locked Milestone A protocols or
unlock Milestones B/C. A selected executable candidate may fail its target.

The shared [local scientific-record library](docs/research/scientific-records-coverage.md)
is available at `/research/records`. Research and measured-study outputs can
recompute and save a source-pinned immutable record under a study ID. Integrity,
historical model targets and current full computational replay are distinct.
The project-local `.mrqlab/scientific-records.sqlite3` database survives API
restarts and is ignored by Git; full records can be exported/imported or managed
with `python -m mrqlab_api.scientific_records`. Background references are context
only and do not silently calibrate a model. Actual browser native JSON download,
file-chooser import and complete replay are verified for the finite-memory CEST
run, quantum-MRS search and shared record flow; the remaining modality/CSV browser coverage is open.
CLI and HTTP persistence/replay are also checked.

A measured-TSE record can now derive a
[radial TSE uncertainty study](docs/research/calibrated-radial-coverage.md):
revalidate its original measurements, bind calibrated T2 by tissue/component,
then compare pulse candidates while keeping the nominal inverse basis fixed at
all sample uncertainty corners. The synthetic example passes nominal targets
but fails every corner; no candidate is selected. The portable child embeds its
unchanged parent and supports full CLI/API computational replay.

The [data-navigated extension](docs/research/navigator-radial-coverage.md) explicitly
adds six echoes and 33-point center-sampled spokes. Within the measured intervals,
it estimates two global T2 curves from raw center samples, checks withheld echoes,
then reconstructs unrestricted complex component maps. The synthetic 140°→110°
candidate passes all five local scenarios; a residual-limit failure excludes the
180° candidate. This is not voxel T2 mapping or a general noisy-data guarantee.

The [flow-EPI extension](docs/research/flow-epi-coverage.md) propagates actual
gradient phase and relaxation through the readout. It retains interrupted ADC
prefixes and distinguishes images, complete opposite-sign pairs, gradient-moment
references and instantaneous flow. Its default DIR targets fail; no failed-only
search acquires an invented best design. The supplied pressure/phantom are authored.

The [finite-memory CEST extension](docs/research/cest-memory-coverage.md) uses a
time-domain generalized Bloch semisolid model with the signed Solomon relay.
It retains shaped RF, complex phase and whole pulse/gap history, including zero
offset. The canonical singular absorption-rate model remains unchanged. Default
numerical refinement passes while its relay target fails; a higher-power point
passes contrast targets but fails refinement. No search candidate qualifies.
Independent augmented Bloch references, full CLI/HTTP and native browser JSON
replay preserve these failures. Molecular priors remain authored.

The [quantum-MRS extension](docs/research/quantum-mrs-coverage.md) replaces scalar
relaxation within its separate homogeneous entry with independent-spin Lindblad
baths and a complete finite-RF/ADC/recovery TR channel. A fully recovered basis
biases the periodic synthetic sample by about 60.5%; a wrong-T1 basis can fit
well and still misestimate amounts. The finite TR search retains a weak-signal
failure and an acquisition-overlap failure, selecting .30 s only within this
authored grid and its explicit signal/numerical gates. This quantum chain is not
yet coupled to the separate three-dimensional PRESS localization model.

See [research workspace evidence and gaps](docs/research/research-workbench-coverage.md).
All accuracy statements apply to declared teaching models; there is no scanner
validation, clinical image-quality certification or clinical concentration
calibration. The full platform goal remains subject to the documented gaps.

## Physics engines

| Name | Selection | Best fit |
|---|---|---|
| `bloch` | Default for SE/GRE | Multi-isochromat rotations, relaxation, off-resonance, and spatial phase |
| `epg` | Default for TSE | Classic configuration-state echo trains |
| `spectral` | Explicit request with pools | Independent fat/water chemical shift |
| `hybrid` | `shaped_rf` + `configuration_states` | Teaching stitch: Bloch owns RF spans, EPG owns evolution; not ssEPG |

The HTTP request may set `"engine": "bloch" | "epg" | "spectral" | "hybrid"`; if omitted, template metadata chooses. See [Physics](docs/PHYSICS.md) for units, assumptions, plugins, and limitations.

## Quickstart

Python 3.11+ and Node 20+ are recommended.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest
uvicorn mrqlab_api.main:app --app-dir services/api --reload
```

Because the packages are intentionally kept in monorepo source roots, development without an editable install can use the supplied Make target (`make api`). API docs are at `http://localhost:8000/docs`.

```bash
cd apps/web
npm install
npm run dev
# http://localhost:3000
```

The browser gracefully shows an offline state when the API is absent. Set `NEXT_PUBLIC_API_URL` only when the API is elsewhere.

## Philosophy and safety boundary

A sequence compiles to channel-specific, time/value events. The experiment kernel selects a representation, wraps a kernel-owned `SimulationEngine` façade for the shipped Bloch, EPG, or spectral backend, samples it under ADC gates, and sends Cartesian data through the recon adapter. External engines contribute state-backend descriptors; scheduling, work caps, ADC/NCO handling, and result assembly remain in the microkernel. Engine-specific details do not leak into sequence or HTTP contracts.

MRQLab does **not** control or connect to real hardware. MaRCoS, Red Pitaya, acquisition services, scanner control, pulse safety validation, clinical decision-making, and diagnostic use are intentionally out of scope. No secrets or cloud credentials belong in this repository.


The research radial inverse also has an optional pinned FINUFFT backend
(`uv sync --locked --extra dev --extra noncartesian`). Choose FINUFFT / CGLS in
the Research page; the exact DFT reference remains available. See the
[accuracy, replay and failure evidence](docs/research/fast-noncartesian-coverage.md)
before interpreting image or residual targets. Large radial conditioning and
noisy/coil/trajectory-calibrated reconstruction remain open research gaps.


Research also includes **Pulsatile / causal DIR**: pressure-driven rigid-pipe
Womersley flow, finite slice RF and causal trigger interruption. Scheduled and
completed cycles are shown separately; default failed targets remain visible.
See [physical assumptions, independent checks and replay](docs/research/pulsatile-causal-dir-coverage.md).


**CEST / Solomon relay** adds a signed dipolar proton-pair model with an explicit
labile bridge to water. Molecular parameters remain priors; design search varies
saturation pulse parameters. Negative contrasts and failed targets are retained.
See [independent checks, replay and model gaps](docs/research/solomon-relay-cest-coverage.md).
