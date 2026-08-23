import { ExperimentGraph, ResultGraph } from "./workbench-types";
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export async function listPresets(): Promise<Array<{ name: string; experiment: ExperimentGraph }>> {
  const response = await fetch(`${BASE}/presets`);
  if (!response.ok) throw new Error(`presets failed: ${response.status}`);
  return (await response.json()).presets;
}

export async function runExperiment(graph: ExperimentGraph): Promise<ResultGraph> {
  const response = await fetch(`${BASE}/experiments/run`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(graph),
  });
  if (!response.ok) throw new Error(`experiment run failed: ${await response.text()}`);
  return response.json();
}

export async function runExperimentFromRecipe(
  recipeId: string,
  params: Record<string, number> = {},
): Promise<ResultGraph> {
  const response = await fetch(`${BASE}/experiments/run-from-recipe`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ recipe_id: recipeId, params }),
  });
  if (!response.ok) throw new Error(`experiment run failed: ${await response.text()}`);
  return response.json();
}

export interface TissueSignalResponse {
  tissues: Array<{ id: string; label: string; role: string }>;
  signals: Record<string, number>;
  contrast_difference: number;
  normalized_cnr_proxy: number;
  signal_ratio: number;
}

export async function fetchTissueSignal(params: {
  experiment?: ExperimentGraph;
  recipe_id?: string;
  params?: Record<string, any>;
}): Promise<TissueSignalResponse> {
  const response = await fetch(`${BASE}/tissue-signal`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!response.ok) throw new Error(`tissue-signal failed: ${await response.text()}`);
  return response.json();
}

export async function saveCustomRecipe(id: string, experiment: ExperimentGraph): Promise<{ status: string; id: string }> {
  const response = await fetch(`${BASE}/recipes/custom`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ id, experiment }),
  });
  if (!response.ok) throw new Error(`save custom recipe failed: ${await response.text()}`);
  return response.json();
}

export async function getCustomRecipe(id: string): Promise<{ id: string; experiment: ExperimentGraph }> {
  const response = await fetch(`${BASE}/recipes/custom/${id}`);
  if (!response.ok) throw new Error(`get custom recipe failed: ${response.status}`);
  return response.json();
}

export interface GradientValidationResult {
  is_valid: boolean;
  violations: string[];
  actual_slew_rate: number;
  actual_amplitude: number;
}

export async function validateGradient(params: {
  amplitude_mt_m: number;
  duration_ms: number;
  ramp_time_ms: number;
  channel?: "Gx" | "Gy" | "Gz";
}): Promise<GradientValidationResult> {
  const response = await fetch(`${BASE}/gradients/validate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ grad: params }),
  });
  if (!response.ok) throw new Error(`gradient validation failed: ${await response.text()}`);
  return response.json();
}

export async function fetchDiffusionWaveform(params: {
  g_max_mt_m: number;
  delta_small_ms: number;
  delta_big_ms: number;
}): Promise<{ time_ms: number[]; gradient_mt_m: number[]; b_value_s_mm2: number }> {
  const response = await fetch(`${BASE}/diffusion/waveform`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!response.ok) throw new Error(`diffusion waveform failed: ${await response.text()}`);
  return response.json();
}

export type TrajectoryType = "cartesian" | "radial" | "spiral" | "stack_of_stars";
export type FillOrder = "sequential_ky" | "centric_ky" | "echo_train_centric" | "epi";

export interface TrajectorySpec {
  trajectory_type: TrajectoryType;
  matrix_size?: number;
  num_spokes_or_interleaves?: number;
  points_per_arm?: number;
  num_slices?: number;
  acceleration_factor?: number;
  fill_order?: FillOrder;
}

export interface TrajectoryPayload {
  trajectory_type: TrajectoryType;
  total_points: number;
  kx: number[];
  ky: number[];
  kz: number[];
  density_compensation_available: boolean;
  fill_order?: FillOrder | null;
  declared_approximate?: boolean;
  honesty?: string;
}

export interface ReconDemoPayload {
  matrix: number;
  trajectory_type: TrajectoryType;
  acceleration_factor: number;
  nrmse: number;
  phantom: number[][];
  recon: number[][];
  preview: { kx: number[]; ky: number[]; total_points: number; preview_stride: number };
  fill_order?: FillOrder | null;
  declared_approximate?: boolean;
  honesty?: string;
}

export async function generateTrajectory(spec: TrajectorySpec): Promise<TrajectoryPayload> {
  const response = await fetch(`${BASE}/trajectories/generate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(spec),
  });
  if (!response.ok) throw new Error(`trajectory generate failed: ${await response.text()}`);
  return response.json();
}

export async function fetchReconDemo(spec: TrajectorySpec): Promise<ReconDemoPayload> {
  const response = await fetch(`${BASE}/recon/demo`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(spec),
  });
  if (!response.ok) throw new Error(`recon demo failed: ${await response.text()}`);
  return response.json();
}

export type OptimizeMode = "max_contrast" | "balanced_sar" | "min_sar";

export interface OptimizeGoal {
  mode: OptimizeMode;
  max_sar_budget: number;
  min_cnr_proxy: number;
  target_t2_ms?: number;
  reference_t2_ms?: number;
  echo_train_length?: number;
  current_fa_deg?: number;
  current_te_ms?: number;
}

export interface ParetoPoint {
  flip_angle: number;
  te_eff: number;
  contrast: number;
  cnr_proxy: number;
  relative_sar: number;
  score: number;
  is_feasible: boolean;
  is_dominated?: boolean;
  label?: string | null;
}

export interface OptimizeAnalysis {
  pareto_frontier: ParetoPoint[];
  candidates: ParetoPoint[];
  optimal_candidate: ParetoPoint;
  sensitivities: Array<{ parameter: string; d_cnr: number; d_sar: number }>;
  grid_size: number;
}

export async function fetchPareto(goal: OptimizeGoal): Promise<OptimizeAnalysis> {
  const response = await fetch(`${BASE}/optimize/pareto`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(goal),
  });
  if (!response.ok) throw new Error(`optimize pareto failed: ${await response.text()}`);
  return response.json();
}

export interface ProtocolSpec {
  id: string;
  name: string;
  flip_angle_deg: number;
  te_eff_ms: number;
  b0_t?: number;
  echo_train_length?: number;
  echo_spacing_ms?: number;
  target_t2_ms?: number;
  reference_t2_ms?: number;
}

export interface CompareProtocol {
  id: string;
  name: string;
  flip_angle_deg: number;
  te_eff_ms: number;
  b0_t: number;
  echo_train: number[];
  target_signal: number;
  reference_signal: number;
  contrast_diff: number;
  cnr_proxy: number;
  relative_sar: number;
}

export interface CompareAnalysis {
  protocol_a: CompareProtocol;
  protocol_b: CompareProtocol;
  delta: { contrast_pct: number; cnr_delta: number; sar_delta: number };
}

export async function fetchCompare(req: {
  protocol_a: ProtocolSpec;
  protocol_b: ProtocolSpec;
}): Promise<CompareAnalysis> {
  const response = await fetch(`${BASE}/compare/protocols`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!response.ok) throw new Error(`compare protocols failed: ${await response.text()}`);
  return response.json();
}

export interface CockpitTissue {
  id: string;
  name?: string;
  t1: number;
  t2: number;
  t2s?: number;
  pd: number;
}

export interface CockpitSignalAnalysis {
  seq_type: "TSE" | "GRE" | "SE";
  fa_deg: number;
  te_ms: number;
  tr_ms: number;
  is_gre: boolean;
  refocus_eff: number;
  relative_sar: number;
  delta_signal: number;
  cnr_proxy: number;
  tissues: Array<{ id: string; name: string; intensity: number }>;
  signals: Record<string, number>;
}

export async function fetchCockpitSignals(req: {
  seq_type: "TSE" | "GRE" | "SE";
  fa_deg: number;
  te_ms: number;
  tr_ms: number;
  echo_train_length?: number;
  tissues: CockpitTissue[];
}): Promise<CockpitSignalAnalysis> {
  const response = await fetch(`${BASE}/cockpit/signals`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!response.ok) throw new Error(`cockpit signals failed: ${await response.text()}`);
  return response.json();
}

export interface PulseInspectAnalysis {
  id: string;
  name: string;
  kind: "hard" | "shaped_sinc" | "gaussian" | "custom";
  flip_angle_deg: number;
  phase_deg: number;
  duration_ms: number;
  time_bandwidth: number;
  slice_thickness_mm: number;
  waveform_time: number[];
  waveform_b1: number[];
  freq_axis_khz: number[];
  freq_response_mag: number[];
  spatial_axis_mm: number[];
  slice_profile_mz: number[];
  slice_profile_mxy: number[];
  epg_transition_matrix: number[][];
  peak_b1: number;
  bw_khz: number;
}

export async function fetchPulseInspect(req: {
  flip_angle_deg?: number;
  phase_deg?: number;
  duration_ms?: number;
  slice_thickness_mm?: number;
  time_bandwidth?: number;
}): Promise<PulseInspectAnalysis> {
  const response = await fetch(`${BASE}/pulse/inspect`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!response.ok) throw new Error(`pulse inspect failed: ${await response.text()}`);
  return response.json();
}

export async function buildSequence(req: {
  template: "SE" | "TSE" | "GRE";
  params?: Record<string, number>;
}): Promise<import("./sequence-ir").SequenceIR> {
  const response = await fetch(`${BASE}/sequences/build`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!response.ok) throw new Error(`sequence build failed: ${await response.text()}`);
  return response.json();
}

export async function patchSequence(req: {
  ir: import("./sequence-ir").SequenceIR;
  event: { channel: "rf_amp" | "gx" | "gy" | "gz"; index: number };
  patch: Record<string, number | string>;
}): Promise<import("./sequence-ir").SequenceIR> {
  const response = await fetch(`${BASE}/sequences/patch`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!response.ok) throw new Error(`sequence patch failed: ${await response.text()}`);
  return response.json();
}

