"use client";
import { createContext, useContext, useMemo, useState } from "react";
import { EMPTY_CURSORS, ExperimentGraph, LensCursors, ResultGraph, WorkspaceId } from "../../lib/experiment";

type ContextValue = {
  workspace: WorkspaceId; experiment: ExperimentGraph | null; result: ResultGraph | null;
  cursors: LensCursors; openWorkspace(id: WorkspaceId): void;
  setExperiment(value: ExperimentGraph | null): void; setResult(value: ResultGraph | null): void;
  setCursors(value: Partial<LensCursors>): void;
};
const Context = createContext<ContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [workspace, openWorkspace] = useState<WorkspaceId>("dashboard");
  const [experiment, setExperiment] = useState<ExperimentGraph | null>(null);
  const [result, setResult] = useState<ResultGraph | null>(null);
  const [cursors, replaceCursors] = useState(EMPTY_CURSORS);
  const value = useMemo(() => ({
    workspace, experiment, result, cursors, openWorkspace, setExperiment, setResult,
    setCursors: (next: Partial<LensCursors>) => replaceCursors(current => ({ ...current, ...next })),
  }), [workspace, experiment, result, cursors]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useWorkspace() {
  const value = useContext(Context);
  if (!value) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return value;
}
