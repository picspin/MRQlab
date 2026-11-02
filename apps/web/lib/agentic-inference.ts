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
  // The payload is untyped JSON at this boundary. Every field the render consumers read is checked here,
  // so a malformed value is rejected before return rather than crashing a render consumer afterwards.
  const raw = inference as unknown as Record<string, any>;
  const check = (ok: boolean) => { if (!ok) throw new Error("记录载荷缺少推断渲染所需的比例结构。"); };
  // Plain (non-array) objects only: arrays pass typeof "object" and would otherwise satisfy map checks vacuously.
  const plainObject = (value: unknown): boolean => !!value && typeof value === "object" && !Array.isArray(value);
  const finite = (value: unknown): boolean => typeof value === "number" && Number.isFinite(value);
  const numberOrNull = (value: unknown): boolean => value === null || finite(value);
  const numberArray = (value: unknown): boolean => Array.isArray(value) && value.every(finite);
  const mapOf = (value: unknown, valid: (entry: unknown) => boolean): boolean => plainObject(value) && Object.values(value as object).every(valid);
  const fieldsFinite = (value: unknown, fields: string[]): boolean => plainObject(value) && fields.every(field => finite((value as Record<string, unknown>)[field]));
  const echoBinValid = (entry: unknown): boolean => plainObject(entry)
    && finite((entry as Record<string, unknown>).echo) && finite((entry as Record<string, unknown>).sample_count)
    && ((entry as Record<string, unknown>).rank === undefined || finite((entry as Record<string, unknown>).rank))
    && ((entry as Record<string, unknown>).nullity === undefined || finite((entry as Record<string, unknown>).nullity))
    && ((entry as Record<string, unknown>).absolute_amplitude_identified === undefined || typeof (entry as Record<string, unknown>).absolute_amplitude_identified === "boolean")
    && ((entry as Record<string, unknown>).relative_residual === undefined || finite((entry as Record<string, unknown>).relative_residual));

  const { proportions, ingestion, validation, source, reference, unavailable } = raw;
  check(typeof raw.scope === "string" && typeof raw.inference_sha256 === "string");
  check(plainObject(proportions) && plainObject(proportions.structure) && plainObject(proportions.image_signal) && plainObject(proportions.acquisition));
  check(plainObject(ingestion) && numberArray(ingestion.echo_ids) && Array.isArray(ingestion.echo_bins) && ingestion.echo_bins.every(echoBinValid));
  check(plainObject(validation) && typeof validation.passed === "boolean" && typeof validation.scope === "string"
    && mapOf(validation.checks, entry => typeof entry === "boolean"));
  check(plainObject(source) && typeof source.pair_sha256 === "string" && Array.isArray(source.tissue_ids) && source.tissue_ids.every((tissue: unknown) => typeof tissue === "string"));
  check(plainObject(reference) && typeof reference.tissue_id === "string" && typeof reference.definition === "string");
  check(Array.isArray(unavailable) && unavailable.every(item => plainObject(item) && typeof item.item === "string" && typeof item.reason === "string"));
  // Per-tissue proportions for every declared tissue, with the numeric fields the table reads.
  check((source.tissue_ids as string[]).every(tissue => fieldsFinite(proportions.structure[tissue], ["voxel_count", "voxel_fraction"])
    && fieldsFinite(proportions.image_signal[tissue], ["energy_fraction", "magnitude_fraction"])));

  const acquisition = proportions.acquisition;
  check(typeof acquisition.available === "boolean");
  if (acquisition.available) {
    check(mapOf(acquisition.coefficients, numberArray) && mapOf(acquisition.contrast_vs_reference, numberArray)
      && mapOf(acquisition.relative_contrast_strength, finite)
      && mapOf(acquisition.apparent_relative_contrast_decay_s, numberOrNull)
      && mapOf(acquisition.decay_fit_residual, numberOrNull)
      && mapOf(acquisition.absolute_dc_echo, entry => mapOf(entry, finite))
      && plainObject(acquisition.identifiability) && typeof acquisition.identifiability.gauge === "string");
  } else {
    check(acquisition.reason === null || typeof acquisition.reason === "string");
  }
  return inference;
}
export const percentage = (value: number) => `${(value * 100).toPrecision(5)}%`;
export const decimal = (value: number | null) => value === null ? "不可识别" : value.toPrecision(5);
