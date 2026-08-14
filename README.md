# MRQLab

**From spin to pixel.** MRQLab is an open teaching MRI simulator for medical students, MRI technologists, and medical physics students. It makes MRI visible as a time-dependent stream of RF, gradient, ADC, and oscillator events—not a form containing TR/TE/FOV. It is a web learning instrument, **not** a scanner console.

## Monorepo

| Path | Responsibility |
|---|---|
| `apps/web` | Next.js/TypeScript instrument UI |
| `services/api` | FastAPI simulation boundary |
| `packages/sequence-ir` | Shared Pydantic MR Event Graph and SE/TSE/GRE builders |
| `packages/physics` | Stable simulation interface, Bloch MVP, future engine registry |
| `packages/recon` | Cartesian FFT adapter and NUFFT seam |
| `docs` | Architecture and roadmap decisions |

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

A sequence compiles to channel-specific, time/value events. The API selects a `SimulationEngine`; the MVP Bloch engine evolves a small spin system, samples it under ADC gates, and sends Cartesian data through the recon adapter. Engine-specific details do not leak into sequence or HTTP contracts.

MRQLab does **not** control or connect to real hardware. MaRCoS, Red Pitaya, acquisition services, scanner control, pulse safety validation, clinical decision-making, and diagnostic use are intentionally out of scope. No secrets or cloud credentials belong in this repository.

See [architecture](docs/ARCHITECTURE.md) and [roadmap](docs/ROADMAP.md).
