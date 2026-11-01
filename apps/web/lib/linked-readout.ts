import type { ResearchRun } from "./research";
import type { ScientificResponse } from "./scientific-records";
export interface ComplexVector { real: number[]; imag: number[]; }
export interface LinkedEdit { field: string; value: number | string; tissue_id?: string; view?: "image" | "signal_vector"; }
export type LinkedControl = { field: string; tissue_id?: string; value: number | string; unit: string } & (
  { kind: "number"; min: number; max: number; choices?: never } |
  { kind: "category"; choices: string[]; min?: never; max?: never }
);
export interface LinkedReadout {
  schema_version: "mrqlab-linked-image-vector-1"; canonicalization: "typed-json-f64-v1"; pair_sha256: string;
  image: { id: string; shape: number[]; axes: string[]; index_unit: "voxel"; flatten_order: "C"; values: ComplexVector; value_unit: string; display?: string };
  signal_vector: { id: string; axis: "acquisition_sample"; value_unit: string; complex_convention: "real + i*imag"; values: ComplexVector; grid_indices: number[][]; grid_index_axes: string[]; normalized_coordinates: number[][]; coordinate_unit: "cycles/voxel"; sample_times_s: number[]; time_unit: "s"; extensions?: Record<string, unknown>; timing_model?: string };
  structure: { shape: number[]; label_grid: number[][] | number[][][]; label_to_tissue_id: string[]; origin: string };
  controls: LinkedControl[];
  provenance: { adapter: string; source_sha256: string; inputs_sha256: string; runtime: Record<string, unknown>; origin: string; source_refs: { tissue_id: string; source_ref: string; origin: string; state: Record<string, unknown> }[] };
  links: { source: string; target: string; transform: string; normalization?: string }[];
  scope: string;
}
/** Legacy TSE adapter name; validation uses bound common descriptors on the server. */
export type TSEEdit = LinkedEdit;
export function linkedRun(response: ScientificResponse): ResearchRun {
  const payload = JSON.parse(response.record.payload_json) as ResearchRun | { run: ResearchRun };
  return "run" in payload ? payload.run : payload;
}
