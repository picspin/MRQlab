# ADR-0004: Disturbance Stack Replaces a Sole Reality Slider

**Status:** Accepted
**Date:** 2026-08-15

## Context

A scalar Reality Slider cannot identify which physical assumptions were added, reproduce them, or explain why an experiment needs a different representation.

## Decision

Reality is represented by an ordered, typed `DisturbanceStack`. Each disturbance has an identity, kind, domain, enabled state, parameters, and required capabilities. The UI slider may map deterministically to curated stack presets but is not the domain model.

The stack vocabulary covers noise, B0/B1 maps, gradient imperfections, motion, flow, diffusion, exchange, susceptibility, coil sensitivity, ADC imperfection, and slice profile. v0.1 implements schema, validation, slider mapping, and selection explanation only.

Adding a disturbance may trigger engine reselection: ideal TSE uses EPG; slice profile recommends ssEPG; exchange recommends EPG-X/hybrid; spatial B0 recommends PDG. If the required representation is unavailable, validation fails explicitly rather than running incomplete physics.

## Consequences

- Reality settings become reproducible experiment data.
- Representation complexity becomes teachable and explainable.
- Disturbance physics can arrive independently behind capability checks.

