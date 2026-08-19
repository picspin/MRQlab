# Mission: Movement I (Clinical Reality & Execution Plan Deepening)

Work in `/opt/data/workspace/MRQlab` on branch `feature/clinical-reality-execution-plan`.

## Context & Architecture (ADR-0006 & Clarification v2)
1. In `packages/mrqlab_experiment`:
   - `ExperimentGraph` in `packages/mrqlab_experiment/mrqlab_experiment/models.py`:
     - Accept first-class clinical reality models:
       - `tissue`: Optional `TissueModel | tuple[TissueModel, ...]` as a modern domain model beside `sample: SampleSpec`. If `tissue` is present, `_phantom_from_sample` (or unified `_phantom_from_experiment`) compiles `TissueModel` into `Phantom`.
       - `physiology`: Optional `PhysiologyModel` (default `PhysiologyModel()`).
       - `scanner_model`: Optional `ScannerModel` (hardware limits: slew rate, gradient limits, ADC bandwidth) alongside `scanner: ScannerSpec`.
   - `ExecutionPlan` enhancement in `packages/mrqlab_experiment/mrqlab_experiment/kernel.py`:
     - Add `cost_estimate: float = 0.0` to `ExecutionPlan`.
     - Multi-tier validation checking against `EngineValidity`: if an experiment requests flow, diffusion, or multi-pool exchange from `TissueModel` or `PhysiologyModel` that the selected engine validity declares `unsupported`, fail closed with `unavailable_representation` or `capability_mismatch` in `validate_experiment`.
     - Fingerprint calculation includes the new fields.
     - Full backward compatibility with existing `SampleSpec` / `ScannerSpec` experiments.
   - Public exports in `packages/mrqlab_experiment/mrqlab_experiment/__init__.py`:
     - Export `TissueModel`, `PhysiologyModel`, `ScannerModel`, `DisturbanceModel`.

2. TDD Requirements:
   - Create failing test suite `tests/experiment/test_clinical_reality_deepening.py` covering:
     - `ExperimentGraph` with `tissue`, `physiology`, `scanner_model`.
     - `_phantom_from_sample` converting `TissueModel` into physics `Phantom`.
     - `plan_experiment` producing `ExecutionPlan` with `validity`, `cost_estimate`, `fingerprint`, and capability checks for tissue/physiology features.
     - Unsupported validity features (e.g. flow with non-supporting engine) failing closed as expected.
     - Full backward compatibility with existing `SampleSpec` / `ScannerSpec` experiments.
   - Implement changes cleanly with minimal blast radius.

3. Git & Verification:
   - Run `.venv/bin/python -m pytest tests/ -q`
   - Run `npm test -- --run` in `apps/web`
   - Create clear git commit with author: `Xiaolei <zxl1412@gmail.com>`
