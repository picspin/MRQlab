"use client";
import { createContext, useContext, useMemo, useState } from "react";
import {
  DEFAULT_CURSORS,
  ExecutionState,
  LensCursors,
  TopLevelRoute,
  WorkbenchLens,
  WorkspaceProfile,
} from "../../lib/workbench-types";

type ContextValue = {
  route: TopLevelRoute;
  setRoute(r: TopLevelRoute): void;
  profile: WorkspaceProfile;
  setProfile(p: WorkspaceProfile): void;
  activeLens: WorkbenchLens;
  setActiveLens(l: WorkbenchLens): void;
  executionState: ExecutionState;
  setExecutionState(s: ExecutionState): void;
  cursors: LensCursors;
  setCursors(c: Partial<LensCursors>): void;
  // legacy compat
  workspace: string;
  openWorkspace(id: string): void;
  experiment: any;
  result: any;
  setExperiment(v: any): void;
  setResult(v: any): void;
};

const Context = createContext<ContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [route, setRoute] = useState<TopLevelRoute>("workbench");
  const [profile, setProfile] = useState<WorkspaceProfile>("clinical");
  const [activeLens, setActiveLens] = useState<WorkbenchLens>("sequence");
  const [executionState, setExecutionState] = useState<ExecutionState>("RESULT");
  const [cursors, replaceCursors] = useState<LensCursors>(DEFAULT_CURSORS);
  const [experiment, setExperiment] = useState<any>(null);
  const [result, setResult] = useState<any>(null);

  const value = useMemo(
    () => ({
      route,
      setRoute,
      profile,
      setProfile,
      activeLens,
      setActiveLens,
      executionState,
      setExecutionState,
      cursors,
      setCursors: (next: Partial<LensCursors>) =>
        replaceCursors((curr) => ({ ...curr, ...next })),
      workspace: route,
      openWorkspace: (id: string) => setRoute(id as TopLevelRoute),
      experiment,
      result,
      setExperiment,
      setResult,
    }),
    [route, profile, activeLens, executionState, cursors, experiment, result]
  );

  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useWorkspace() {
  const value = useContext(Context);
  if (!value) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return value;
}
