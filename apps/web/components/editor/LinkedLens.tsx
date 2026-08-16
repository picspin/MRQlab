"use client";
import { useWorkspace } from "../workspace/WorkspaceProvider";
export function LinkedLens() {
  const { cursors, setCursors } = useWorkspace();
  return <section className="linked-lens">
    <header><label>Experiment time <input aria-label="Experiment time" type="range" min="0" max="100" value={cursors.cursorTime ?? 0} onChange={e => setCursors({ cursorTime: Number(e.target.value) })}/></label></header>
    <article className="system"><b>SYSTEM</b><h2>Sequence timeline</h2></article>
    <article className="physics"><b>PHYSICS</b><h2>Spin / rotating frame</h2></article>
    <article className="state"><b>STATE</b><h2>EPG pathway graph</h2></article>
    <article className="observation"><b>OBSERVATION</b><h2>Signal · k-space · image</h2></article>
  </section>;
}
