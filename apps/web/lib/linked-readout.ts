import type { ResearchRun } from "./research";
import type { ScientificResponse } from "./scientific-records";
export interface ComplexVector { real: number[]; imag: number[]; }
export interface LinkedReadout {
  schema_version: "mrqlab-image-signal-pair-1"; pair_sha256: string;
  image: { shape: number[]; axes: string[]; values: ComplexVector; value_unit: string };
  signal_vector: { values: ComplexVector; grid_indices: number[][]; normalized_coordinates: number[][]; coordinate_unit: string; sample_times_s: number[]; time_unit: string; echo_numbers: number[]; timing_model: string };
  structure: { label_to_tissue_id: string[]; origin: string };
  controls: { field: TSEEdit["field"]; tissue_id?: string; value: number | string; unit: string; min?: number; max?: number }[];
}
export interface TSEEdit { field: "rf.refocusing_start_deg" | "rf.refocusing_end_deg" | "timing.tr_s" | "timing.echo_spacing_s" | "encoding.order" | "tissue.concentration_mmol_l"; value: number | string; tissue_id?: string; }
export function linkedRun(response: ScientificResponse): ResearchRun {
  const payload = JSON.parse(response.record.payload_json) as ResearchRun | { run: ResearchRun };
  return "run" in payload ? payload.run : payload;
}
