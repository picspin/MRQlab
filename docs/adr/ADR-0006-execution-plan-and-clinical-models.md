# ADR-0006: ExecutionPlan as Core Contract and Decoupled Clinical Reality Models

**Date:** 2026-08-17  
**Status:** Accepted  
**Context:** MRQLab v0.2 Clinical Execution Backbone  

## Context & Problem Statement
In v0.1, `SampleSpec`, `ScannerSpec`, and `DisturbanceStack` served as preliminary inputs, while `ExecutionPlan` was a lightweight façade record. As we advance to clinical MRI cases (e.g. Dark-Blood Vessel Wall TSE, Brain T2 TSE, Cardiac bSSFP), three key architectural gaps emerge:
1. **Conflated Reality Model:** Biological tissue properties ($T_1, T_2, T_2^*, \rho$, exchange, diffusion, flow), physiological states (cardiac/respiratory phase, flow waveforms, contrast curves), scanner hardware limits ($B_0/B_1^+$, gradient/slew limits, ADC bandwidth, noise), and physical disturbances (off-resonance, concomitant fields) were partially mixed or forced into a generic `disturbances` container.
2. **Coarse Capability Negotiation:** Engines only declared a flat set of strings (`supports`). However, "supporting" a feature does not guarantee sufficient clinical fidelity (e.g. EPG handles echo trains but lacks true flow dynamics; single-spin Bloch lacks exchange; Floquet requires periodicity).
3. **Weak ExecutionPlan:** Execution planning did not capture pulse compiler partitions, time grids, state layouts, requested observation subsets, or execution fingerprinting for stale state detection and incremental caching.

## Decision
We establish:
1. **Four Orthogonal Domain Models:**
   - `TissueModel`: Microscopic tissue properties ($T_1, T_2, T_2^*, \rho$, multi-pool exchange, diffusion tensor, bulk velocity).
   - `PhysiologyModel`: Dynamic physiological states (cardiac phase, RR interval, respiration, flow waveforms).
   - `ScannerModel`: Hardware parameters, field maps, gradient slew limits, RF limits, ADC bandwidth.
   - `DisturbanceModel` / `DisturbanceStack`: Explicit perturbations deviating from ideal models (e.g., non-ideal slice profile, $B_0/B_1$ inhomogeneity).
2. **Explicit Multi-dimensional Validity Matrix:**
   Engine descriptors define multi-tier validity:
   - `spatial_encoding`: `none` | `limited` | `full`
   - `shaped_rf`: `unsupported` | `approximate` | `exact`
   - `flow`: `unsupported` | `approximate` | `exact`
   - `exchange`: `unsupported` | `multi_pool`
   - `diffusion`: `unsupported` | `isotropic` | `anisotropic`
   - `differentiable`: `bool`
3. **First-Class ExecutionPlan Contract:**
   `ExecutionPlan` serves as the authoritative blueprint holding:
   - `experiment_id`, `fingerprint`
   - `selected_engine`, `representation`, `validity`
   - `requested_observations` (directing exact solver compute)
   - `approximations` & `reasons`
   - `cost_estimate` & `differentiable`
   - `stale_dependencies` (mapping parameter changes to invalidated observations)
