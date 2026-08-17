export type WorkspaceId = "dashboard" | "editor" | "signal-lab" | "contrast-lab" | "optimization-lab" | "ai-lab";
export type LensCursors = {
  cursorTime: number | null;
  selectedEvent: string | null;
  selectedState: string | null;
  selectedVoxel: [number, number, number] | null;
  selectedEcho: number | null;
};
export type ExperimentGraph = {
  schema_version: "1.0"; id: string; name: string;
  intent: "teaching" | "clinical_contrast" | "physics" | "custom";
  nodes: Array<{ id: string; kind: string; label: string; parameters: Record<string, unknown> }>;
  edges: Array<{ source: string; target: string; kind: string }>;
  sequence: Record<string, unknown>; sample: Record<string, unknown>;
  scanner: Record<string, unknown>; engine: Record<string, unknown>;
  objective: Record<string, unknown> | null; readout: { products: string[] };
  constraints: { max_work: number; matrix: number };
  disturbances: { items: Array<Record<string, unknown>> };
  provenance: { seed: number; tags: string[] };
};
export type Observation = { id: string; kind: string; data: unknown; derived_from: string[] };
export type ResultGraph = { schema_version: "1.0"; experiment_id: string; observations: Observation[] };
export const EMPTY_CURSORS: LensCursors = {
  cursorTime: null, selectedEvent: null, selectedState: null,
  selectedVoxel: null, selectedEcho: null,
};
