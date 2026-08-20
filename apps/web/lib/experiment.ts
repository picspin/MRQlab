import { ExperimentGraph, ResultGraph } from "./workbench-types";
export * from "./workbench-types";

export type WorkspaceId = "dashboard" | "editor" | "signal-lab" | "contrast-lab" | "optimization-lab" | "ai-lab";

export const EMPTY_CURSORS = {
  cursorTime: null,
  selectedEvent: null,
  selectedState: null,
  selectedVoxel: null,
  selectedEcho: null,
};
