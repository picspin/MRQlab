/** Human review layer for the bounded agent acquisition-signal inference. */
export interface AgenticTissueProportion {
  voxel_count: number; voxel_fraction: number;
}
export interface AgenticImageProportion {
  energy: number; energy_fraction: number; magnitude: number; magnitude_fraction: number;
}
export interface AgenticEchoBin {
  echo: number; sample_count: number; mean_time_s: number; kspace_energy: number;
  rank?: number; nullity?: number; absolute_amplitude_identified?: boolean; relative_residual?: number;
}
export interface AgenticAcquisition {
  available: boolean; reason: string | null; echo_ids: number[]; echo_bins: AgenticEchoBin[];
  coefficients: Record<string, number[]>;
  contrast_vs_reference: Record<string, number[]>;
  relative_contrast_strength: Record<string, number>;
  apparent_relative_contrast_decay_s: Record<string, number | null>;
  decay_fit_residual: Record<string, number | null>;
  absolute_dc_echo: Record<string, Record<string, number>>;
  identifiability: { gauge: string; common_mode: string; per_tissue_absolute_amplitudes: string; per_tissue_t2: string };
}
export interface AgenticModality {
  id: string; label: string; kind: string; shape: number[]; axes: string[]; values: number[];
  value_unit: string; min: number; max: number; basis: string; note: string;
}
export interface AgenticInference {
  schema_version: "mrqlab-agentic-tissue-inference-1"; canonicalization: "typed-json-f64-v1";
  source: {
    pair_sha256: string; linked_schema_version: string; adapter: string; origin: string;
    source_sha256: string; inputs_sha256: string; runtime: Record<string, unknown>;
    image_id: string; signal_id: string; shape: number[]; axes: string[]; tissue_ids: string[];
    structure_origin: string; linked_scope: string;
  };
  ingestion: {
    sample_count: number; voxel_count: number; complete_unique_grid_indices: true;
    signal_energy: number; image_energy: number; parseval_signal_energy: number; parseval_image_energy: number;
    parseval_relative_error: number; transform_max_absolute_error: number;
    echo_ids: number[]; echo_times_s: number[]; echo_bins: AgenticEchoBin[];
  };
  proportions: {
    structure: Record<string, AgenticTissueProportion>;
    image_signal: Record<string, AgenticImageProportion>;
    acquisition: AgenticAcquisition;
  };
  reference: { tissue_id: string; definition: string };
  modalities: AgenticModality[];
  unavailable: { item: string; reason: string }[];
  validation: {
    passed: boolean; checks: Record<string, boolean>;
    tolerances: Record<string, number>; scope: string;
  };
  limits: { max_samples: number; max_tissues: number; max_echoes: number };
  scope: string;
  inference_sha256: string;
}
export interface AgenticRecordLike { record: { payload_json: string; summary: { mode: string } } }

/** Retains the exact computed inference; rejects a record from another execution mode or one whose payload cannot be rendered. */
export function agenticInference(response: AgenticRecordLike): AgenticInference {
  if (response.record.summary.mode !== "agentic_inference") throw new Error("当前记录不是 agentic 信号推断。");
  const payload = JSON.parse(response.record.payload_json) as { inference?: AgenticInference };
  const inference = payload?.inference;
  if (!inference || inference.schema_version !== "mrqlab-agentic-tissue-inference-1") throw new Error("记录缺少可识别的 agentic 推断载荷。");
  const object = (value: unknown) => !!value && typeof value === "object";
  const proportions = inference.proportions;
  if (!object(proportions) || !object(proportions.structure) || !object(proportions.image_signal)
    || !object(inference.ingestion) || !Array.isArray(inference.ingestion.echo_ids) || !Array.isArray(inference.ingestion.echo_bins)
    || !object(inference.validation) || typeof inference.validation.passed !== "boolean" || !object(inference.validation.checks)
    || !object(inference.source) || !Array.isArray(inference.source.tissue_ids)
    || !object(inference.reference) || typeof inference.reference.tissue_id !== "string"
    || !Array.isArray(inference.unavailable)) throw new Error("记录载荷缺少推断渲染所需的比例结构。");
  if (!inference.source.tissue_ids.every(tissue => object(proportions.structure[tissue]) && typeof proportions.structure[tissue].voxel_fraction === "number"
    && object(proportions.image_signal[tissue]) && typeof proportions.image_signal[tissue].energy_fraction === "number")) throw new Error("记录载荷缺少推断渲染所需的比例结构。");
  const acquisition = proportions.acquisition;
  if (acquisition?.available === true && (!object(acquisition.coefficients) || !object(acquisition.contrast_vs_reference)
    || !object(acquisition.relative_contrast_strength) || !object(acquisition.apparent_relative_contrast_decay_s)
    || !object(acquisition.decay_fit_residual) || !object(acquisition.absolute_dc_echo)
    || typeof acquisition.identifiability?.gauge !== "string")) throw new Error("记录载荷缺少推断渲染所需的比例结构。");
  // Nested entries are checked down to their rendered type, so a malformed value is rejected here
  // rather than crashing a render consumer after this function has returned.
  const finiteNumber = (value: unknown) => typeof value === "number" && Number.isFinite(value);
  const numberArrays = (map: unknown) => object(map) && Object.values(map as Record<string, unknown>).every(values => Array.isArray(values) && values.every(finiteNumber));
  const echoBinValid = (entry: unknown) => object(entry) && finiteNumber((entry as AgenticEchoBin).echo) && finiteNumber((entry as AgenticEchoBin).sample_count);
  if (!inference.ingestion.echo_bins.every(echoBinValid)) throw new Error("记录载荷缺少推断渲染所需的比例结构。");
  if (acquisition?.available === true && (!numberArrays(acquisition.coefficients) || !numberArrays(acquisition.contrast_vs_reference)
    || !Array.isArray(acquisition.echo_bins) || !acquisition.echo_bins.every(echoBinValid))) throw new Error("记录载荷缺少推断渲染所需的比例结构。");
  if (!inference.unavailable.every(item => object(item) && typeof (item as { item?: unknown }).item === "string" && typeof (item as { reason?: unknown }).reason === "string")) throw new Error("记录载荷缺少推断渲染所需的比例结构。");
  return inference;
}
export const percentage = (value: number) => `${(value * 100).toPrecision(5)}%`;
export const decimal = (value: number | null) => value === null ? "不可识别" : value.toPrecision(5);
