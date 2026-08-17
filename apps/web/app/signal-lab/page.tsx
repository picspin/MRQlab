"use client";
import { TseSignalLab } from "../../components/signal-lab/TseSignalLab";
import { runExperiment } from "../../lib/api";
export default function SignalLabPage() {
  return <TseSignalLab run={async input => {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}/presets`);
    const presets = (await response.json()).presets;
    const graph = presets.find((item: { name: string }) => item.name === "dark-blood-tse").experiment;
    graph.sequence.params = (input as { params: Record<string, number> }).params;
    graph.engine.options = { epg_kmax: 8, return_configurations: true };
    graph.readout.products = ["signal", "k_trajectory", "image", "configurations", "echo_train", "sar"];
    return runExperiment(graph);
  }}/>;
}
