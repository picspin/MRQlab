# Mada Symphony Score: Wave I — v0.4 Optimize Lens & Pareto Frontier

**Goal**: Deliver v0.4 Optimize Lens (`optimize` lens on Workbench) featuring objective-driven multi-parameter optimization, sensitivity gradients, and Pareto frontier (Contrast vs SAR trade-off) with 0-token verification.

## Movement 1: Contract & Type System Tuning (Oboe / Opus-GLM)
- Expand `WorkbenchLens` in `workbench-types.ts` to include `"optimize"`.
- Define `OptimizationObjective` (`target_cnr`, `max_sar_budget`, `weight_contrast`, `weight_sar`).
- Define `OptimizationResult` (`pareto_points`, `optimal_point`, `sensitivity_matrix`).
- Build `optimize-engine.ts` with analytical Pareto curve generator across TSE Flip Angle (100°–180°) and TE (40ms–160ms).

## Movement 2: UI Implementation (Violin I / Grok-4.6 - Lead Coder)
- Create `OptimizeLensView.tsx`:
  - Visual 2D Pareto Frontier scatter/curve: SAR Load vs $\Delta\text{Signal}$ / CNR Proxy.
  - Interactive Goal Dial: "Maximize Contrast", "Balanced / Low SAR", "Fast / Cool".
  - One-click "Apply Optimal to Protocol A" button.
  - Parameter Sensitivity Heatmap / Bars ($\partial\text{CNR}/\partial\text{FA}$, $\partial\text{SAR}/\partial\text{FA}$).
- Integrate `optimize` button into `WorkbenchCockpit.tsx` Lens bay and active lens switch.

## Movement 3: 0-Token Deterministic Verification (Snare Drum / Vitest + Pytest)
- Add comprehensive test cases in `apps/web/tests/vertical-slice-workbench.test.tsx` verifying:
  - Switching to `optimize` lens.
  - Pareto curve calculation & optimal point search under SAR constraint.
  - Applying optimal parameters updates Cockpit sliders.
- Run full test suite: `npm test && uv run pytest`.

## Movement 4: Git Branch & Push (Finale)
- Commit and push to `feature/web-optimize-lens-pareto`.
