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

## Physics engines

| Name | Selection | Best fit |
|---|---|---|
| `bloch` | Default for SE/GRE | Multi-isochromat rotations, relaxation, off-resonance, and spatial phase |
| `epg` | Default for TSE | Classic configuration-state echo trains |
| `spectral` | Explicit request with pools | Independent fat/water chemical shift |

The HTTP request may set `"engine": "bloch" | "epg" | "spectral"`; if omitted, template metadata chooses. See [Physics](docs/PHYSICS.md) for units, assumptions, plugins, and limitations.

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
