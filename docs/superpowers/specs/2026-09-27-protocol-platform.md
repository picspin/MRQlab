# MRQLab Protocol Platform Specification

**Date:** 2026-09-27

**Status:** Locked for implementation planning

**Source of truth:** `.hermes/plans/2026-09-27_protocol-platform-lock.md` plus `docs/research/mrqlab-physics/MRQLab-full-repo-audit.md`

**Extends:** `docs/superpowers/plans/2026-08-15-experiment-kernel.md`

## 1. Product contract

MRQLab is a research-use-only MRI contrast and protocol engineering platform. It keeps the teaching-focused Explore experience, but it is not a scanner console, diagnostic clinical decision support system, pulse-safety validator, or claim of clinical readiness.

The product has five explicit layers:

1. **Explore** — browser-first teaching, recipes, and low-cost preview.
2. **Protocol Studio** — clinical-question-driven contrast and protocol engineering.
3. **Compute** — deterministic local or hosted execution through providers.
4. **Export** — logical lowering, executable-sequence validation, and later research adapters.
5. **Enterprise Control Plane** — identity, device registration, entitlement, and signed leases without experiment payloads.

The layers must not be collapsed into one anonymous API surface. They share contracts, but they have different responsibilities and safety boundaries.

## 2. Stable kernel and execution profiles

The existing experiment kernel remains the center of the product. This specification extends, rather than replaces, the stable `ExperimentGraph`, `PhysicsOperator`, `StateRepresentation`, `ObjectiveFunction`, and `Observation` contracts.

All execution profiles consume the same immutable resolved contract and emit the same observation/provenance vocabulary:

```text
ExperimentGraph
  + ClinicalProtocolRecipe
  + ScannerProfile
       |
       v
ResolvedExecutionPlan
       |
       +-- Tier 0: browser preview
       +-- Tier 1: in-process NumPy via POST /experiments/run*
       `-- Tier 2: local high-fidelity via POST /jobs and ExecutionProvider
       |
       v
Observation + provenance
```

- **Tier 0 browser preview** is approximate and must label its approximations.
- **Tier 1 in-process NumPy** preserves synchronous `POST /experiments/run` and `POST /experiments/run-from-recipe` behavior.
- **Tier 2 local high-fidelity** is a new asynchronous job/provider path. It does not turn the synchronous experiment routes into GPU RPC.

Capability and entitlement are separate decisions:

- Capability answers whether a provider can execute the resolved plan.
- Entitlement answers whether the user or device may invoke that provider or feature.
- Entitlement enforcement belongs at the execution gateway, never in Bloch, EPG, ssEPG, PDG, or other physics operators.

## 3. Milestone A — Clinical Contract

Milestone A is the first implementation wave. It closes the semantic and provenance loop without adding workers, licensing, Pulseq, or new physics engines.

### 3.1 Exactly two first verticals

Only these verticals become first-class `ClinicalProtocolRecipe` entries in A:

1. **Brain lesion T2/TSE** — target lesion hyperintensity against white-matter reference, with gray matter and CSF as confounders.
2. **Knee cartilage/meniscus PD/T2 TSE** — target cartilage/meniscal pathology against cartilage or meniscus reference, with joint fluid and marrow fat as confounders.

Dixon, TOF, and CEST research mode are parked as A+ candidates. Existing recipes continue to work for compatibility, but they do not receive the new locked clinical-contract claim in A.

### 3.2 Clinical models

Milestone A introduces the following immutable, JSON-ready models:

```text
ClinicalQuestion
TissuePriorSet
Target
Reference
Confounder
ContrastMetric
RobustnessScenario
AcquisitionConstraint
ClinicalProtocolRecipe
ScannerProfile
ParameterState
ObjectiveVector
ResolvedExecutionPlan
```

Required semantics:

- `ClinicalQuestion` identifies anatomy, research question, finding, and intended contrast mechanism. It contains no diagnosis or treatment recommendation.
- `TissuePriorSet` names target, reference, and confounder tissue identifiers and owns their `TissueModel` priors.
- `Target`, `Reference`, and `Confounder` are typed tissue-role references, not duplicate tissue-property containers.
- `ContrastMetric` identifies the compared tissues, metric kind, direction, and weight.
- `RobustnessScenario` declares bounded B0, B1, motion, and relaxation perturbations. Declaring a scenario does not imply that every engine models it.
- `AcquisitionConstraint` is a typed bound with an explicit unit and hard/soft severity.
- `ClinicalProtocolRecipe` binds one clinical question to one tissue prior set, one objective vector, acquisition constraints, robustness scenarios, a scanner profile reference, and an existing experiment recipe id.
- `ScannerProfile` supplies versioned defaults, unit-bearing hardware limits, raster/dead-time values for future lowering, and a stable profile id/version.
- `ParameterState` records one parameter value, explicit unit, provenance source, and one of the exact states `authored | derived | scanner_default | estimated | visual_only | unsupported | stale`.
- `ObjectiveVector` contains multiple named contrast, time, robustness, and safety-proxy terms. It does not perform optimization in A.

Every model rejects non-finite numeric values, ambiguous unitless quantities where a unit is required, duplicate identifiers, dangling target/reference/confounder references, and unsupported vertical identifiers.

### 3.3 ResolvedExecutionPlan

The current `ExecutionPlan` evolves compatibly into immutable `ResolvedExecutionPlan`. The public `ExecutionPlan` name remains as a compatibility alias for existing imports during A.

The resolved plan contains:

- experiment and clinical recipe identifiers;
- selected representation and engine;
- required capabilities and requested observations;
- all execution options and relevant clinical parameters with defaults resolved;
- explicit units for every resolved parameter;
- `ParameterState` and source for every parameter;
- approximations and physics-modeling status;
- scanner profile id/version;
- tissue-prior-set id/version;
- software/version/commit inputs already available to provenance;
- deterministic immutable SHA-256 fingerprint over a canonical JSON payload;
- stale dependency mapping;
- cost estimate and validity report.

The fingerprint excludes transient object identity and dictionary insertion order. Mutating the caller's `ExperimentGraph` after resolution cannot alter an existing plan.

### 3.4 Parameter honesty

Milestone A does not silently connect currently unwired UI controls. The UI must continue to label their actual state, and tests must prove their values are absent from execution payloads:

- ADC bandwidth: `seed · not wired` / `visual_only`.
- Parallel acceleration: `local only · not in execution plan` / `visual_only`.
- Readout width: `local only · not in execution plan` / `visual_only`.
- Partial Fourier: `local only · not in execution plan` / `visual_only`.
- Lego TE/TR/FA and clinical geometry remain disabled or labeled as seed-only wherever the current honesty tests require it.
- Existing editor overlay labels for RF duration/TBW/phase and gradient duration/ramp remain intact.

### 3.5 Documentation truth

`docs/ARCHITECTURE.md` and `docs/PHYSICS.md` must agree that ssEPG and PDG are available in the current research kernel while retaining their bounded roles. The edits must preserve every literal required by:

- `tests/experiment/test_experiment_docs.py`
- `tests/physics/test_physics_docs.py`
- `tests/test_v063_epg_x_super_lorentzian.py`
- `tests/test_v066_cest_pulsed_train.py`

The safety language including `not a clinical`, the `dimensionless teaching gradients` statement, and the CEST imaging `remain unavailable` boundary stays present.

### 3.6 Milestone A acceptance

Milestone A is complete only when:

- both locked verticals resolve to immutable plans with deterministic fingerprints;
- invalid tissue references, duplicate ids, non-finite values, and unknown units fail closed;
- all defaults have explicit source and unit;
- existing synchronous endpoints remain synchronous and backward compatible;
- currently unwired controls remain visibly unwired and absent from payloads;
- architecture and physics documentation agree without breaking docs tests;
- full Python and web test gates pass.

## 4. Milestone B — Executable Sequence

Milestone B is parked until Milestone A is accepted or the human explicitly unlocks it.

The sequence path becomes:

```text
ExperimentGraph
    |
    v
LogicalSequenceIR
    | protocol lowering + ScannerProfile
    v
ExecutableSequenceIR
    | export-state evaluation
    v
ExportIR
    `-- Pulseq adapter later
```

### 4.1 Contracts

- `LogicalSequenceIR` preserves authored protocol intent and can expose the existing `SequenceIR` as a compatibility view.
- `ExecutableSequenceIR` contains shaped RF samples, arbitrary gradient samples, ADC dwell/sample count, explicit units, raster-quantized timing, dead time, ringdown, and lowering provenance.
- `ExportIR` contains deterministic shape libraries and block references suitable for an adapter, without claiming scanner executability.
- Frontend components author logical blocks and clinical parameters. They do not author Pulseq or vendor files.

### 4.2 Export states

Export validation uses these exact ordered states:

```text
SIMULATION_VALID
IR_VALID
EXPORTABLE
TARGET_PROFILE_VALID
HARDWARE_REVIEW_REQUIRED
```

The final state is a mandatory reminder that software validation is not scanner safety approval. A successful Pulseq adapter in a later wave does not imply clinical or hardware readiness.

### 4.3 Milestone B acceptance

- lowering is deterministic and consumes a versioned scanner profile;
- RF, gradient, ADC, raster, dead-time, and ringdown violations fail closed;
- existing eight-channel `SequenceIR` simulation stays compatible;
- export state never exceeds the evidence available;
- no Pulseq authoring UI is added;
- the Pulseq adapter remains a later, separately reviewed task.

## 5. Milestone C — Licensed Local Compute

Milestone C is parked until Milestone B is accepted or the human explicitly unlocks it.

### 5.1 ExecutionProvider

The provider protocol is transport-neutral:

```python
class ExecutionProvider(Protocol):
    descriptor: ProviderDescriptor

    def validate(self, plan: ResolvedExecutionPlan) -> ValidationReport: ...
    def estimate(self, plan: ResolvedExecutionPlan) -> ResourceEstimate: ...
    def submit(self, plan: ResolvedExecutionPlan) -> JobHandle: ...
    def cancel(self, job_id: str) -> None: ...
    def capabilities(self) -> CapabilitySet: ...
```

Provider order is CPU first, then GPU. Tier 1 keeps the in-process NumPy path; Tier 2 introduces a local gateway and worker lifecycle. GPU support is an optional provider/plugin distribution, not a rewrite of `/experiments/run`.

### 5.2 Local job API

The local gateway exposes:

```text
POST /jobs
GET  /jobs/{id}
POST /jobs/{id}/cancel
GET  /jobs/{id}/events
GET  /artifacts/{id}
GET  /v1/capabilities
```

Jobs are idempotent by resolved-plan fingerprint plus provider id. State transitions are explicit: `queued → running → succeeded | failed | cancelled`. Events are append-only. Artifacts are content-addressed and served by opaque id; browser requests never contain arbitrary local paths.

### 5.3 Lease and device contract

- Cloud signing uses Ed25519 with `kid` rotation.
- The control plane keeps the signing private key; the local gateway embeds only trusted public keys.
- Device registration creates a device key pair and binds device id, public-key hash, and a tolerant hardware fingerprint.
- Lease claims include organization, device, product, feature entitlements, limits, software-version bounds, issue/not-before/expiry times, and offline grace.
- A monotonic trusted-time anchor detects material wall-clock rollback.
- Lease verification and entitlement enforcement occur before provider submission.
- Physics packages receive a validated plan and never import licensing code.
- The browser reads capability/lease summaries only. It never receives device private keys, lease signing keys, or long-lived API keys.

The implementation of Ed25519 verification requires an explicitly approved production crypto dependency before Milestone C execution begins.

### 5.4 Localhost security

- Bind loopback only by default.
- Use a strict configured origin allowlist.
- Require a pairing secret on HTTP, SSE, and WebSocket requests.
- Enforce CSRF protection for mutating browser requests.
- Reject arbitrary file paths, Python module names, plugin paths, and shell commands.
- Return only coarse capability, worker, and lease status to the web application.

### 5.5 Milestone C acceptance

- the CPU worker completes, cancels, and emits events/artifacts deterministically;
- unavailable GPU capability fails closed without affecting Tier 1;
- expired, not-yet-valid, wrong-device, wrong-audience, and unentitled leases fail closed;
- offline grace and time rollback behavior are tested;
- CORS, CSRF, pairing, and loopback behavior are tested;
- no licensing import exists under `packages/physics`;
- web capability discovery contains no secret material.

## 6. Immediate honesty outside this plan branch

- PR #52 at `e43f19c` is the chrome v0.76.15 Lego RUN fail-closed seam. Cloud verdict is land; merging remains the human's decision. Pages remains v0.76.14 until merge and deployment.
- After that merge, delivery is Pages-first.
- The optional next honesty seam is silent diffusion off when tissue ADC is empty versus composed `fov_m + epg`; it is not a v0.76.16 collection of UI nits.
- Stop further 0.76.x slider and caption polishing.

These items are documented here and are not implemented on `feature/protocol-platform-plan`.

## 7. Out of scope

The following exclusions are binding across all three milestones unless a later specification explicitly replaces them:

- No monorepo rewrite.
- No license in kernel.
- No GPU-ize `/experiments/run`.
- No SequenceIR = scanner-executable.
- No clinical-ready claim.
- No simultaneous MRS+DCE+CEST-imaging+full PDG+GPU+Pulseq+licensing.
- Do not delete safety disclaimers.
- No lease keys in the browser.
- No FLAIR/MOLLI/MESE engines.
- No restack Compare/Optimize/click-to-place.
- No Pi product landing.
- No shaped-RF designer, arbitrary-gradient designer, License Server, GPU worker, Pulseq adapter, Hybrid restack, N-pool model, MRS, or CEST imaging in Milestone A.

## 8. Sequencing and human gates

1. Execute Milestone A tasks only after the human says `开工`.
2. Review and accept the Milestone A contract before any Milestone B task.
3. Review and accept Milestone B, or explicitly waive that dependency, before any Milestone C task.
4. Obtain human approval for a production Ed25519 dependency before the Milestone C lease-verification task.
5. Preserve docs-only status on the planning branch; product implementation belongs on later execution branches.
