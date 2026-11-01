import type { ResearchRequest, ResearchSearch, ResearchRun } from "./research";
import type { StudyInput } from "./lab-study";
export type ScientificExecution = ({ type: "run" } & ResearchRequest) | ({ type: "search" } & ResearchSearch["replay_search"]) | { type: "measured_tse"; study: StudyInput } | { type: "measured_flow"; study: import("./flow-study").FlowStudyInput } | { type: "edited_tse"; parent_record_sha256: string; parent_record?: ScientificRecord; updates: import("./linked-readout").LinkedEdit[] } | { type: "calibrated_radial_tse"; parent_record_sha256: string; parent_record?: ScientificRecord; study: Record<string, unknown> } | { type: "agentic_inference"; parent_record_sha256: string; parent_record?: ScientificRecord; reference_tissue_id?: string };
export interface ScientificPlan {
  context: { study_id: string; research_question: string; target_rationale: string; assumptions?: string; intended_use?: "teaching" | "research" };
  execution: ScientificExecution; expected_execution_hash?: string;
}
export interface ScientificSummary {
  study_id: string; research_question: string; mode: string; kind: string; selected_index: number | null;
  model_reported_passed: boolean; parent_record_sha256?: string; candidate_count: number; input_origins: string[]; scope: string;
  parent_pair_sha256?: string; inference_sha256?: string;
  candidates?: { index: number; executable: boolean; model_reported_passed: boolean; reason?: unknown; reasons?: string[]; validation?: Record<string, unknown> }[];
}
export interface ScientificRecord {
  schema_version: "mrqlab-scientific-record-1"; record_sha256: string; request_json: string; payload_json: string;
  request_sha256: string; payload_sha256: string; api_source_hash: string;
  sources: { sha256: string; files: Record<string, string> }; runtime: Record<string, unknown>;
  summary: ScientificSummary; stages: { stage: string; parents: string[]; value_sha256: string; sha256: string }[];
}
export interface ScientificResponse {
  record: ScientificRecord; verification: { integrity_passed: boolean; computational_replay_performed: boolean }; view: ResearchRun["view"] | null;
}
export interface ScientificList {
  total: number; offset: number; limit: number;
  records: { record_sha256: string; created_ns: number; bytes: number; summary: ScientificSummary; integrity_checked: false; computational_replay_performed: false }[];
}
export interface ScientificReplay {
  integrity_passed: boolean; computational_replay_performed: boolean; record_sha256: string; payload_sha256: string; summary: ScientificSummary;
}
