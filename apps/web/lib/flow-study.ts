export interface FlowDataset {
  origin: "measured" | "synthetic"; source_ref: string;
  raw_csv_base64?: string; raw_file_sha256?: string;
  measurements: Record<string, unknown>[];
}
export interface FlowStudyInput {
  research_question: string; target_rationale: string; dataset: FlowDataset;
  [key: string]: unknown;
}
export interface FlowStudyResult {
  calibration: { passed: boolean; reasons: string[]; coefficients_pa_m: number[] | null; std_pa_m: number[] | null;
    calibration_reduced_chi2: number | null; holdout_max_standardized_residual: number | null; holdout_reduced_chi2: number | null };
  validation: { calibration_and_holdout_passed: boolean; complete_budget_reserved: boolean; selected_design_passed: boolean };
  selected_index: number | null; preview_index: number | null;
  candidates: { index: number; design: { inversion_time_s: number }; executed: boolean; eligible: boolean; reasons: string[];
    scenarios: { completed: boolean; numerical_refinement_passed?: boolean; max_observation_refinement_error?: number | null; passed: boolean }[] }[];
  provenance: { input_origin: string; source_ref: string; raw_file_sha256: string | null; estimated_work: number; reserved_work: number };
}
