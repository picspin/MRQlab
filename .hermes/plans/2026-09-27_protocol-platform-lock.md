# MRQLab Protocol Platform — locked brief (2026-09-27)

Source audit (user): `MRQLab 全仓库架构与实现.md` (1207 lines, Mac Codex audit, no product edits).
Handoff: **Mac local Codex + Superpowers** (`codex exec`, writing-plans then executing-plans). **Not** Codex Cloud one-shot. **Not** Grok ACP `:8318`.
Pi = orch only. No product code on the gateway.

## Product positioning (locked)

Research-use-only **MRI contrast and protocol engineering platform**.

Keep teaching Explore. Do **not** claim diagnostic/clinical-use, scanner control, or hardware-executable sequences.

Suggested product layers (do not collapse into one anonymous FastAPI):

1. **Explore** — browser light interaction, recipes, anonymous OK
2. **Protocol Studio** — clinical-question-driven protocol engineering
3. **Compute** — local/high-fidelity workers (CPU then GPU)
4. **Export** — lowering then Pulseq / vendor research adapters
5. **Enterprise Control Plane** — identity, lease, entitlement (no experiment payload)

Three execution profiles, **same** ExperimentGraph / ResolvedExecutionPlan / Observation / provenance:

- Tier 0 Browser preview
- Tier 1 in-process NumPy (current `/experiments/run*`)
- Tier 2 local high-fidelity (new job/provider, **not** GPU-izing the sync route)

Capability ≠ Entitlement. License lives in the execution gateway, **never** inside Bloch/EPG.

## Keep (do not rewrite)

- Experiment-centered domain (`ExperimentGraph`, five contracts)
- Three-layer IR: Experiment → Sequence → Physics → Observation
- Fail-closed capability negotiation
- Provenance / work cap / engine plugin seam
- Modular monolith (one Python + Next.js) until Phase 4
- Teaching honesty already on main (0.76.14 Pages) + PR #52 Lego fail-closed (OPEN, Cloud land) until user merges

## Do not do (audit §七 + existing workbench locks)

1. Do not rebuild the monorepo
2. Do not put license checks in physics operators
3. Do not turn `POST /experiments/run` into GPU RPC
4. Do not declare current SequenceIR scanner-executable
5. Do not claim clinical-ready because recipes exist
6. Do not simultaneously push MRS, DCE, CEST imaging, full PDG, GPU, Pulseq, and licensing
7. Do not delete current safety disclaimers
8. Do not put lease private keys or long-lived API keys in the browser
9. Do not invent FLAIR/MOLLI/MESE engines
10. Do not restack Compare/Optimize, click-to-place, Hybrid, N-pool, NH/OH atomization
11. Do not stack 0.76.x slider/caption nits
12. Do not land product code on Pi

## Milestones (order locked)

### Milestone A — Clinical Contract (next impl wave)

- 2–3 clinical verticals only (recommended first: Brain lesion T2/TSE; Knee PD/T2 TSE; optional third later: Dixon **or** TOF **or** CEST research mode — pick **two** in the Superpowers plan, not five)
- `ClinicalQuestion → ObjectiveVector → Constraints`
- Every UI parameter has ParameterState: authored | derived | scanner_default | estimated | visual_only | unsupported | stale
- `ResolvedExecutionPlan` immutable + fingerprint
- Fix ARCHITECTURE.md vs PHYSICS.md drift (ssEPG/PDG availability) **without** breaking `test_*docs*` required strings
- Do **not** start License Server, GPU worker, or Pulseq in A

### Milestone B — Executable Sequence (parked until A lock-face closed)

- Shaped RF waveform contract
- Arbitrary gradient waveform contract
- ADC dwell/sample count
- Raster / dead time
- Pulseq export **alpha** after lowering
- Export states: SIMULATION_VALID / IR_VALID / EXPORTABLE / TARGET_PROFILE_VALID / HARDWARE_REVIEW_REQUIRED
- SequenceIR evolves toward LogicalSequenceIR; do not author Pulseq in the frontend

### Milestone C — Licensed Local Compute (parked until B or explicit lock)

- local agent + ExecutionProvider protocol
- CPU/GPU job lifecycle (`POST /jobs`, cancel, events, artifacts)
- Ed25519 lease, device registration, offline grace
- localhost CORS/CSRF/pairing secret
- Web only reads `GET /v1/capabilities`; enforcement on the agent

## Immediate honesty (not Milestone A product)

- PR #52 (`e43f19c`, chrome v0.76.15) Cloud **land** — merge is user's call; Pages still v0.76.14 until merge+deploy
- After merge: Pages-first, then optional one seam: silent diffusion on/off (tissue ADC empty vs compose fov_m+epg). Not a 0.76.16 nit pack
- Stop 0.76.x nits (Jev subtract_now 0.80)

## Codex path

1. writing-plans on Mac `~/src/MRQlab` → `docs/superpowers/plans/YYYY-MM-DD-protocol-platform.md` (+ spec)
   - Skip brainstorming (this brief is the lock)
   - Planning only: no `packages/**` `apps/**` `services/**` product edits
   - TDD checkboxes, exact paths, full code, **no TBD**
   - Branch `feature/protocol-platform-plan`
2. Aftercare: Xiaolei author, picspin SSH push, compare URL, scp to Pi notes
3. executing-plans **only after** user says 开工 / 继续实现 — start Milestone A Task 1, anti-`collab: Wait`

## Author / identity

```
git config user.name Xiaolei
git config user.email zxl1412@gmail.com
GIT_SSH_COMMAND=ssh -i <picspin-or-github-key that answers Hi picspin!> -o IdentitiesOnly=yes
```
