import { ExperimentGraph, ResultGraph } from "./experiment";
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
