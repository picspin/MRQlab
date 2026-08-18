export type WorkspaceProfile = "clinical" | "physics" | "technical";

export type TopLevelRoute = "explore" | "workbench" | "labs" | "ai_lab";

export type WorkbenchLens = "sequence" | "state" | "acquisition" | "image" | "compare";

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

export interface TissueItem {
  id: string;
  label: string;
  role: "target" | "reference" | "background" | "lumen" | "contrast";
  t1: number;
  t2: number;
  proton_density: number;
}

export interface ClinicalContrastProxy {
  contrast_difference: number;
  signal_ratio: number;
  normalized_cnr_proxy: number;
  tissues: Array<{ id: string; label: string; role: string }>;
}
