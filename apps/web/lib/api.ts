import { ExperimentGraph, ResultGraph } from "./workbench-types";
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export async function listPresets(): Promise<Array<{ name: string; experiment: ExperimentGraph }>> {
  const response = await fetch(`${BASE}/presets`);
  if (!response.ok) throw new Error(`presets failed: ${response.status}`);
  return (await response.json()).presets;
}

export async function runExperiment(graph: ExperimentGraph): Promise<ResultGraph> {
  const response = await fetch(`${BASE}/experiments/run`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(graph),
  });
  if (!response.ok) throw new Error(`experiment run failed: ${await response.text()}`);
  return response.json();
}

export interface TissueSignalResponse {
  tissues: Array<{ id: string; label: string; role: string }>;
  signals: Record<string, number>;
  contrast_difference: number;
  normalized_cnr_proxy: number;
  signal_ratio: number;
}

export async function fetchTissueSignal(params: {
  experiment?: ExperimentGraph;
  recipe_id?: string;
  params?: Record<string, any>;
}): Promise<TissueSignalResponse> {
  const response = await fetch(`${BASE}/tissue-signal`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!response.ok) throw new Error(`tissue-signal failed: ${await response.text()}`);
  return response.json();
}

export async function saveCustomRecipe(id: string, experiment: ExperimentGraph): Promise<{ status: string; id: string }> {
  const response = await fetch(`${BASE}/recipes/custom`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ id, experiment }),
  });
  if (!response.ok) throw new Error(`save custom recipe failed: ${await response.text()}`);
  return response.json();
}

export async function getCustomRecipe(id: string): Promise<{ id: string; experiment: ExperimentGraph }> {
  const response = await fetch(`${BASE}/recipes/custom/${id}`);
  if (!response.ok) throw new Error(`get custom recipe failed: ${response.status}`);
  return response.json();
}

