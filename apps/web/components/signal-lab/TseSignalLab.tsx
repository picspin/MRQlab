"use client";
import { useState } from "react";
import { ResultGraph } from "../../lib/experiment";

export function TseSignalLab({ run }: { run(graph: Record<string, unknown>): Promise<ResultGraph> }) {
  const [angle, setAngle] = useState(180); const [result, setResult] = useState<ResultGraph | null>(null);
  const get = (kind: string) => result?.observations.find(item => item.kind === kind)?.data;
  async function execute() {
    setResult(await run({ preset: "dark-blood-tse", params: { refocusing_flip_angle: angle } }));
  }
  return <section className="signal-lab"><label>Refocusing flip angle
    <input aria-label="Refocusing flip angle" type="range" min="90" max="180" value={angle} onChange={event => setAngle(Number(event.target.value))}/>
    <output>{angle}°</output></label><button onClick={execute}>Run teaching chain</button>
    {result && <div className="causal-chain"><article>EPG states<pre>{JSON.stringify(get("configurations"))}</pre></article>
      <article>Echo train<pre>{JSON.stringify(get("echo_train"))}</pre></article><article>k-space weighting</article>
      <article>Tissue contrast<pre>{JSON.stringify(get("image"))}</pre></article>
      <article>SAR {Number(get("sar")).toFixed(2)}</article></div>}
  </section>;
}
