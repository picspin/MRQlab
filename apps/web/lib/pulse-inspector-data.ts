export interface PulseInspectorData {
  id: string;
  name: string;
  kind: "hard" | "shaped_sinc" | "gaussian" | "custom";
  flipAngleDeg: number;
  phaseDeg: number;
  durationMs: number;
  timeBandwidth: number;
  sliceThicknessMm: number;
  waveformTime: number[]; // ms
  waveformB1: number[]; // a.u. or uT
  freqAxisKhz: number[];
  freqResponseMag: number[];
  spatialAxisMm: number[];
  sliceProfileMz: number[];
  sliceProfileMxy: number[];
  epgTransitionMatrix: number[][]; // 3x3 magnitude of coherence transfer
}

export function generateSincPulseResponse(
  flipAngleDeg: number = 150,
  phaseDeg: number = 90,
  durationMs: number = 2.5,
  sliceThicknessMm: number = 5.0,
  timeBandwidth: number = 4.0
): PulseInspectorData {
  const nTime = 61;
  const waveformTime: number[] = [];
  const waveformB1: number[] = [];
  for (let i = 0; i < nTime; i++) {
    const t = (i / (nTime - 1) - 0.5) * durationMs;
    waveformTime.push(t);
    const x = (t / (durationMs / 2)) * (timeBandwidth / 2);
    const sinc = x === 0 ? 1 : Math.sin(Math.PI * x) / (Math.PI * x);
    // Hanning window
    const win = 0.5 * (1 + Math.cos((2 * Math.PI * i) / (nTime - 1) - Math.PI));
    waveformB1.push(sinc * win * (flipAngleDeg / 180));
  }

  const nFreq = 51;
  const freqAxisKhz: number[] = [];
  const freqResponseMag: number[] = [];
  const bwKhz = timeBandwidth / durationMs;
  for (let i = 0; i < nFreq; i++) {
    const f = (i / (nFreq - 1) - 0.5) * (bwKhz * 3);
    freqAxisKhz.push(f);
    const arg = f / (bwKhz / 2);
    const sinc = arg === 0 ? 1 : Math.sin(Math.PI * arg) / (Math.PI * arg);
    freqResponseMag.push(Math.abs(sinc * Math.sin((flipAngleDeg * Math.PI) / 180)));
  }

  const nZ = 51;
  const spatialAxisMm: number[] = [];
  const sliceProfileMz: number[] = [];
  const sliceProfileMxy: number[] = [];
  for (let i = 0; i < nZ; i++) {
    const z = (i / (nZ - 1) - 0.5) * (sliceThicknessMm * 3);
    spatialAxisMm.push(z);
    const ratio = z / (sliceThicknessMm / 2);
    const sinc = ratio === 0 ? 1 : Math.sin(Math.PI * ratio) / (Math.PI * ratio);
    const theta = Math.asin(Math.max(-1, Math.min(1, sinc * Math.sin((flipAngleDeg * Math.PI) / 180))));
    sliceProfileMz.push(Math.cos(theta));
    sliceProfileMxy.push(Math.abs(Math.sin(theta)));
  }

  const alpha = (flipAngleDeg * Math.PI) / 180;
  const cosA2 = Math.cos(alpha / 2) ** 2;
  const sinA2 = Math.sin(alpha / 2) ** 2;
  const sinA = Math.sin(alpha);
  const epgTransitionMatrix = [
    [cosA2, sinA2, sinA],
    [sinA2, cosA2, sinA],
    [-0.5 * sinA, 0.5 * sinA, Math.cos(alpha)],
  ];

  return {
    id: "refocusing_pulse_1",
    name: "Refocusing Sinc Pulse (RF #2..16)",
    kind: "shaped_sinc",
    flipAngleDeg,
    phaseDeg,
    durationMs,
    timeBandwidth,
    sliceThicknessMm,
    waveformTime,
    waveformB1,
    freqAxisKhz,
    freqResponseMag,
    spatialAxisMm,
    sliceProfileMz,
    sliceProfileMxy,
    epgTransitionMatrix,
  };
}
