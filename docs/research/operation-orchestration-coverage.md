# Operation-level RF / gradient orchestration: first verifiable slice

Starting anchor: `e3a94d9`, branch `herdr/codex-orchestration`. This is a new,
bounded research adapter, using the existing common linked image/vector schema
and scientific-record execution chain. Teaching/research simulation only;
Milestones B/C were explicitly unlocked by the user on 2026-11-05. This adapter
is the first bounded Milestone B slice. No scanner waveform execution or clinical
quality claim follows from a successful run.

## Implemented model and controls

`sequence_operations.py` accepts an ordered list of uniquely identified operations:

| Operation | Editable properties | Model |
|---|---|---|
| `hard_rf` | `flip_deg` [0, 180], `phase_deg` [-180, 180] | Instantaneous Cartesian Rodrigues rotation about a transverse axis |
| `gradient_hold` | `amplitude_mt_m` [-40, 40], `duration_s` [1e-6, .1] | Exact spatial phase evolution during a rectangular x/y gradient, with T1/T2 relaxation |
| `delay` | `duration_s` [1e-6, 1] | Exact free T1/T2 relaxation |

These are research input bounds, not hardware safety limits. Gradient holds have
ideal instantaneous edges; no ramp, slew, PNS, SAR, scanner raster, or export is
implemented. RF and gradient holds cannot overlap. A list defines order without
ambiguous timestamps; hard RF has zero duration. Gradient holds are followed by
zero gradient unless another hold follows. The phase convention is positive
`2*pi*gamma_bar*G*r*dt`, with `gamma_bar=42.57747892e6 Hz/T`, matching the existing
Cartesian Bloch backend. A positive 90-degree x rotation takes equilibrium z to
negative y. Positions are centered voxel indices times FOV/shape; axes are y,x.

Each run starts at thermal equilibrium with authored static tissue proton density,
T1 and T2. State persists through the entire operation list. Complete Cartesian
magnetization after every operation, start/end times, and final magnetization are
retained. Work is bounded by 32 operations, a rectangular 2..16 by 2..16 grid,
1..8 uniquely named tissues, and at most 2 s of total preparation. Every voxel
label must bind to an explicit tissue. Nonfinite values, booleans as numeric
inputs, unknown kinds/fields, duplicate IDs, and extra keys fail validation.

The final transverse state is Fourier transformed into a complete centered
Cartesian snapshot. All samples have the same time: the accumulated preparation
duration. This is a simultaneous ideal snapshot, not an ADC acquisition timeline
or a gradient-generated Cartesian readout. The pair uses
`mrqlab-linked-image-vector-1` unchanged, with adapter
`static-voxel-operations-1`. It retains complete complex arrays, structure/tissue
bindings, source/runtime/input pins, units and normalized encoding coordinates.
The common inverse-transform tolerance remains `1e-12 * max(1, max(abs(image)))`.

The existing common descriptor/edit contract is reused verbatim. Stable semantic
fields such as `operations.excite.flip_deg` or
`operations.encode.amplitude_mt_m` map to exactly one operation property. Axis,
operation kind/ID/order, tissue state, FOV and voxel labels are read-only within
an edited lineage. A new root plan may author these inputs. Capability descriptors
must exactly match the retained adapter inputs before applying any edit; rehashing
a pair cannot introduce arbitrary writable fields. At most eight edits apply
atomically, with coupled duration/work checks after the batch. Duplicate edits,
including duplicates across image/signal views, fail. Neither the input object
nor its parent record is mutated. A gradient-only hold edit can change complex
image phase and the entire signal vector while leaving image magnitude unchanged;
this is tested, not hidden through magnitude normalization.

## Scientific records and compatibility

`operation_sequence` executes a root plan. `edited_operations` uses the shared
`LinkedParentEdits` carrier also used by `edited_tse`: immutable parent identity,
optional portable embedded parent, and common `LinkedEdit` updates. Children
first computationally replay the entire source/runtime-pinned parent, validate
descriptors, then recompute operation physics and both linked views. Before/after
parameter hashes, retained updates, parent replay flag, and seven dependency
stages are preserved. A maximum of three edit generations prevents unbounded
replay. Cross-adapter parents are rejected. Import stores embedded ancestors for
navigation in a fresh local store. Existing HTTP record creation, export/import,
listing and replay and the portable CLI handle this adapter without a new schema.

`validation.passed` and scientific `model_reported_passed` in this adapter report
successful bounded model execution and linked-transform verification only. There
is no clinical/image-quality target or claim that a design was optimized. The
existing TSE API bounds, scientific targets, generation limit, edited plan name,
and rejection behavior remain intact. No shared linked schema, frontend contract,
or existing sequence compose/patch/execution contract was changed.

An executable example is available locally:

```python
from mrqlab_experiment.sequence_operations import operation_sequence_example
from mrqlab_api.scientific_records import create_scientific_record, replay_scientific_record

plan = operation_sequence_example()
parent = create_scientific_record(plan)
child = create_scientific_record({
    'context': plan['context'],
    'execution': {
        'type': 'edited_operations',
        'parent_record_sha256': parent['record_sha256'],
        'parent_record': parent,
        'updates': [
            {'field': 'operations.excite.flip_deg', 'value': 67., 'view': 'image'},
            {'field': 'operations.encode.amplitude_mt_m', 'value': -.04,
             'view': 'signal_vector'},
        ],
    },
})
assert replay_scientific_record(child)['computational_replay_performed']
```

These plans also use the existing `/research/records` API and
`python -m mrqlab_api.scientific_records` CLI. The new run kind is deliberately
restricted to the scientific-plan carrier; the existing `/research/run` kind
union and web research form have not been expanded.

## Verification coverage

`tests/test_sequence_operations.py` retains the original 36 cases and adds four
boundary/physics cases in this follow-up. Independent analytic Rodrigues,
relaxation and two-axis gradient calculations check every final voxel with
absolute tolerance 1e-14. A direct voxel-sum DFT, independent of the production
FFT, checks every complex sample on an odd 3x5 grid at absolute tolerance 1e-13.
No fitted gain or rescaling is used. Ordered gradient/RF noncommutation and a
two-hold spin-echo cancellation check exercise persistent intermediate state.
Every advertised editable property has a mapping test. Other cases cover strict
rejection, coupled limits, unchanged parents, image/signal view equivalence,
gradient-only phase changes, forged capabilities, identity/source/runtime pins,
checksum-consistent forged-parent computational rejection, generation bounds,
HTTP failures without saving children, portable ancestor import, and identical
child replay in a fresh CLI process. Exact pair/input binding and mixed-adapter
lineage rejection before recursive verification are also tested. Existing TSE
and common replay regression tests run alongside them.

## Follow-up verification (2026-11-05)

The actual clean starting HEAD for this follow-up was `6aa885b`, already containing
the initial slice above `e3a94d9`. No reset or duplicate implementation was made.
Accurate summation keeps twenty 0.1 s holds at the declared 2 s boundary.
On the tested Python 3.15 environment, the original validator already accepted
this input because built-in sum uses compensated summation, but the original
trace and snapshot clock reported 2.0000000000000004 s. The validator and clock
now explicitly use math.fsum and agree at 2 s.
An extra 1 microsecond still fails. Root execution and typed edits cover this boundary.
An independent scalar rotation/relaxation calculation checks every voxel after
each step in a phase-varied RF / x-gradient / RF / delay / y-gradient sequence.
HTTP tests prove eight edits save one fully replayable child, while nine edits
return 422 and leave only the unchanged parent in the store.

Fresh validation on the final executable source (Python 3.15.0 and the existing
local dependencies):

| Check | Fresh result |
|---|---|
| Full `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` | **1110 passed**, 1 Starlette deprecation warning, 247.68 s |
| Frontend `npm test` | **18 files, 134 tests passed**, exit 0, 2.41 s |
| `npm run typecheck -- --incremental false` (`tsc --noEmit`) | Exit 0, zero errors |
| Working-tree `git diff --check` and final staged diff check | Passed, zero whitespace errors |

The focused operation/TSE/linked-replay run passed **58 tests**, including all
**40 operation cases**. These are overlapping subsets of the full 1110 count,
not extra full-suite tests. An in-memory load of the original `6aa885b` module
independently reproduced the twenty-hold trace/snapshot clock exceeding 2 s
before the fix. The initial rejection hypothesis was incorrect on Python 3.15;
the confirmed regression is a disagreement between validation and output timing.
No existing test assertion or numerical target was relaxed.

Python ran without writing bytecode or pytest cache. Frontend `npm test` ran
outside the sandbox with approval because its Vitest cache resides in this
worktree, outside the session's writable roots. It completed without EPERM;
no configuration, dependency links, permissions, thresholds, or shared linked
schema files were changed. TypeScript ran with incremental writes disabled.
No browser/manual UI, scanner, or independent full-simulator validation is claimed.
The coverage-only result update after these checks changes no executable source.

## Remaining gaps and review items

- Finite or shaped RF, slice selection, simultaneous RF/gradient evolution,
  gradient ramps and slew, scanner constraints, diffusion, off-resonance, flow,
  exchange, dynamic tissue/contrast biology, multi-pool evolution and uncertainty.
- Physical readout gradients, within-ADC evolution, acquisition trajectories,
  non-Cartesian transforms, 3D, multicoil signals and reconstruction noise models.
  The present Fourier data is a complete static snapshot after preparation.
- Operation insertion/deletion/reordering through edits, loops, branches,
  optimizers and adapters for existing TSE/compose/patch IR. The TSE runner remains
  its established ideal EPG model; this slice does not claim arbitrary TSE waveform
  orchestration or relax its physical validation.
- Product UI for this adapter, measured tissue calibration, independent full
  simulator/scanner comparison, physician/LLM usability, and clinical validation.
- No linked schema change is needed for this slice. Review item: the unchanged
  common validator's unsupported-control error mentions physical gradient waveform
  edits generically. This adapter's declared ideal gradient holds are supported;
  undeclared fields still fail. Any schema/core wording change belongs to a
  separate review, not this round.
- Existing non-Cartesian accuracy gaps, contrast-image target failures and broader
  platform backlog remain. No old target or threshold was lowered or retuned.

B/C activation is the user decision recorded on 2026-11-05, not a claim of
complete executable-sequence or licensed-compute support. No goal-file edits,
other-worktree work, submission material, Magpie changes, pushes, merges or PRs
are included.
