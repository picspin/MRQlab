import type { ResearchRun } from "./research";
export type StudyInput = Record<string, unknown>;
export interface LabStudyRecord {
  schema_version: "mrqlab-study-record-1";
  study_kind: "measured-tse";
  canonicalization: "typed-json-f64-v1";
  request: StudyInput;
  request_json: string;
  request_sha256: string;
  result_sha256: string;
  record_sha256: string;
  sources: { sha256: string; files: Record<string, string> };
  runtime: Record<string, unknown>;
  result: {
    clinical_question: { research_question: string };
    calibration: { tissue_id: string; t2_s: number; t2_std_s: number | null; holdout_max_standardized_residual: number; passed: boolean; reasons: string[] }[];
    candidates: { index: number; design: Record<string, unknown>; executed: boolean; eligible: boolean; worst_psf_rms_voxels?: number; reasons: string[]; scenarios: unknown[] }[];
    selected_index: number | null;
    validation: { calibration_and_holdout_passed: boolean; complete_budgeted_search: boolean; selected_design_passed: boolean };
    targets: Record<string, number>;
    provenance: { estimated_work: number; reserved_work: number; stages: { id: string; input_sha256: string; output_sha256: string; derived_from: string[] }[]; [key: string]: unknown };
    scope: string;
  };
}
export interface LabStudyResponse { record: LabStudyRecord; view: ResearchRun["view"] | null; }
