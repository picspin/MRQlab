export type WorkspaceProfile = "clinical" | "physics" | "technical";

export type TopLevelRoute = "explore" | "workbench" | "labs" | "ai_lab";

export type WorkbenchLens = "sequence" | "state" | "acquisition" | "image" | "compare" | "optimize";

export type ExecutionState = "CLEAN" | "DIRTY" | "READY" | "RUNNING" | "RESULT" | "STALE";

export interface LensCursors {
  cursorTime: number;
  selectedEvent: string | null;
  selectedState: string | null;
  selectedVoxel: [number, number] | null;
  selectedEcho: number | null;
  selectedTissueId: string | null;
}

export const DEFAULT_CURSORS: LensCursors = {
  cursorTime: 0.0,
  selectedEvent: null,
  selectedState: null,
  selectedVoxel: null,
  selectedEcho: null,
  selectedTissueId: null,
};

export interface Observation {
  id: string;
  kind: string;
  data: any;
  derived_from?: string[];
}

export interface ExperimentGraph {
  schema_version: "1.0";
  id: string;
  name: string;
  intent?: "teaching" | "clinical_contrast" | "physics" | "custom";
  nodes?: Array<{ id: string; kind: string; label: string; parameters: Record<string, unknown> }>;
  edges?: Array<{ source: string; target: string; kind: string }>;
  sequence: {
    template: {
      ref: string;
      parameters: Record<string, any>;
    };
  };
  sample: {
    tissues: Array<{
      id: string;
      t1: number;
      t2: number;
      proton_density: number;
    }>;
  };
  scanner: {
    b0_t: number;
  };
  engine: {
    target_representation?: string;
  };
  objective?: Record<string, unknown> | null;
  readout: {
    products: string[];
  };
  constraints: Record<string, any>;
  disturbances: any;
  provenance: Record<string, any>;
}

export interface ResultGraph {
  schema_version: "1.0";
  experiment_id: string;
  execution_plan?: {
    fingerprint?: string;
    selected_engine?: string;
    cost_estimate_ms?: number;
  };
  observations: Observation[];
  provenance?: Record<string, any>;
}
