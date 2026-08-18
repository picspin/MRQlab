export interface CompareProtocol {
  id: string;
  name: string;
  flipAngleDeg: number;
  teEffMs: number;
  b0T: number;
  echoTrain: number[]; // 16 echoes signal intensity
  targetSignal: number;
  referenceSignal: number;
  contrastDiff: number;
  cnrProxy: number;
  relativeSar: number;
}

export function computeCompareProtocol(
  id: string,
  name: string,
  flipAngleDeg: number,
  teEffMs: number,
  b0T: number = 3.0
): CompareProtocol {
  const etl = 16;
  const echoSpacingMs = 12.5;
  const echoTrain: number[] = [];

  // Approximate multi-echo EPG evolution for Target (MS Lesion: T1 1400, T2 120) & Ref (WM: T1 900, T2 80)
  const t2Lesion = 120;
  const t2Wm = 80;
  const faRad = (flipAngleDeg * Math.PI) / 180;
  const refocusEfficiency = Math.sin(faRad / 2) ** 2;

  for (let i = 1; i <= etl; i++) {
    const t = i * echoSpacingMs;
    // Signal decay modulated by refocusing angle and T2
    const decay = Math.exp(-t / t2Lesion) * (0.3 + 0.7 * refocusEfficiency);
    echoTrain.push(Number(decay.toFixed(3)));
  }

  const targetSignal = Math.exp(-teEffMs / t2Lesion) * refocusEfficiency;
  const referenceSignal = Math.exp(-teEffMs / t2Wm) * refocusEfficiency;
  const contrastDiff = Math.abs(targetSignal - referenceSignal);
  const noiseFloor = 0.05 / Math.sqrt(b0T / 1.5);
  const cnrProxy = Number((contrastDiff / noiseFloor).toFixed(2));
  const relativeSar = Number((etl * (flipAngleDeg / 180) ** 2 * (b0T / 1.5) ** 2).toFixed(1));

  return {
    id,
    name,
    flipAngleDeg,
    teEffMs,
    b0T,
    echoTrain,
    targetSignal: Number(targetSignal.toFixed(3)),
    referenceSignal: Number(referenceSignal.toFixed(3)),
    contrastDiff: Number(contrastDiff.toFixed(3)),
    cnrProxy,
    relativeSar,
  };
}
