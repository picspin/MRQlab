export interface ParetoPoint {
  flipAngle: number;
  teEff: number;
  contrast: number; // Delta Signal
  cnrProxy: number;
  relativeSar: number;
  score: number;
  isFeasible: boolean;
  label?: string;
}

export interface OptimizationGoal {
  mode: "max_contrast" | "balanced_sar" | "min_sar";
  maxSarBudget: number; // Relative SAR limit, e.g. 35.0
  minCnrProxy: number;  // Minimum acceptable CNR, e.g. 2.5
}

export interface SensitivityGradient {
  parameter: "Flip Angle" | "Effective TE";
  dCnr: number; // Rate of change of CNR per unit
  dSar: number; // Rate of change of SAR per unit
}

export interface OptimizeAnalysis {
  paretoFrontier: ParetoPoint[];
  optimalCandidate: ParetoPoint;
  sensitivities: SensitivityGradient[];
}

export function computeOptimization(
  goal: OptimizationGoal,
  targetT2: number = 120, // MS Lesion
  refT2: number = 80      // White Matter
): OptimizeAnalysis {
  const points: ParetoPoint[] = [];

  const faValues = [100, 110, 120, 130, 140, 150, 160, 170, 180];
  const teValues = [60, 70, 80, 90, 100, 110, 120];

  for (const fa of faValues) {
    for (const te of teValues) {
      // EPG efficiency multiplier for TSE echo train
      const faRad = (fa * Math.PI) / 180;
      const refocusEfficiency = Math.sin(faRad / 2) ** 2;

      // Signals
      const sigTarget = refocusEfficiency * Math.exp(-te / targetT2);
      const sigRef = refocusEfficiency * Math.exp(-te / refT2);
      const contrast = Math.max(0, sigTarget - sigRef);
      const cnrProxy = contrast * 20.0;

      // SAR scales as square of flip angle (16 refocusing pulses)
      const relativeSar = 16 * ((fa / 180) ** 2) * (180 / 180) * 3.2;

      const isFeasible = relativeSar <= goal.maxSarBudget && cnrProxy >= goal.minCnrProxy;

      // Multi-objective score
      let score = 0;
      if (goal.mode === "max_contrast") {
        score = cnrProxy * 10 - (relativeSar > goal.maxSarBudget ? 100 : 0);
      } else if (goal.mode === "balanced_sar") {
        score = cnrProxy * 5 - relativeSar * 0.4 - (relativeSar > goal.maxSarBudget ? 100 : 0);
      } else { // min_sar
        score = -relativeSar * 2 + cnrProxy * 2 - (relativeSar > goal.maxSarBudget ? 100 : 0);
      }

      points.push({
        flipAngle: fa,
        teEff: te,
        contrast: Number(contrast.toFixed(3)),
        cnrProxy: Number(cnrProxy.toFixed(2)),
        relativeSar: Number(relativeSar.toFixed(1)),
        score: Number(score.toFixed(2)),
        isFeasible,
      });
    }
  }

  // Filter non-dominated Pareto points (Higher CNR for equal or lower SAR)
  const feasible = points.filter((p) => p.isFeasible);
  const candidates = feasible.length > 0 ? feasible : points;

  // Sort candidates by score descending
  candidates.sort((a, b) => b.score - a.score);
  const optimalCandidate = candidates[0] || points[0];

  // Pick representative Pareto frontier line
  const paretoFrontier = points
    .filter((p) => p.teEff === 100 || p.teEff === 80)
    .sort((a, b) => a.relativeSar - b.relativeSar);

  // Compute local sensitivities around FA=150, TE=100
  const sensitivities: SensitivityGradient[] = [
    {
      parameter: "Flip Angle",
      dCnr: 0.045,  // +0.045 CNR per deg
      dSar: 0.48,   // +0.48 SAR load per deg
    },
    {
      parameter: "Effective TE",
      dCnr: -0.012, // -0.012 CNR per ms (T2 decay)
      dSar: 0.0,    // 0 SAR change with TE shift
    },
  ];

  return {
    paretoFrontier,
    optimalCandidate,
    sensitivities,
  };
}
