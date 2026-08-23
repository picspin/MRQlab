"use client";

import React from "react";
import { SequenceBlock, SequenceBlockKind } from "../../lib/api";

const CATALOG: Array<{ kind: SequenceBlockKind; label: string; channel: string }> = [
  { kind: "excite_sinc", label: "Excite sinc", channel: "RF" },
  { kind: "refocus_sinc", label: "Refocus sinc", channel: "RF" },
  { kind: "trap_gx", label: "Trap Gx", channel: "Gx" },
  { kind: "trap_gy", label: "Trap Gy", channel: "Gy" },
  { kind: "trap_gz", label: "Trap Gz", channel: "Gz" },
  { kind: "adc_gate", label: "ADC gate", channel: "ADC" },
];

export function SequenceLego({ blocks, selectedId, onPlace, onMove, onSelect, onDelete }: {
  blocks: SequenceBlock[];
  selectedId?: string;
  onPlace: (kind: SequenceBlockKind) => void;
  onMove: (id: string, t0_s: number) => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  return <section data-testid="sequence-lego" style={{ padding: 8, borderBottom: "1px solid #34464d" }}>
    <div style={{ fontSize: 10, color: "#8ea1a8", marginBottom: 6 }}>TEACHING BLOCKS · click to place · 0.1 ms grid</div>
    <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
      {CATALOG.map((item) => <button key={item.kind} data-testid={`catalog-${item.kind}`} onClick={() => onPlace(item.kind)}
        title={`Place on ${item.channel}`}>{item.label}</button>)}
    </div>
    {blocks.map((block) => <div key={block.id} data-testid={`block-${block.id}`} onClick={() => onSelect(block.id)}
      style={{ marginTop: 6, padding: 4, border: selectedId === block.id ? "1px solid var(--cyan)" : "1px solid #34464d" }}>
      <b>{block.kind}</b>{" @ "}
      <input aria-label={`time ${block.id}`} type="number" min="0" step="0.1" value={block.t0_s * 1000}
        onClick={(event) => event.stopPropagation()}
        onChange={(event) => onMove(block.id, Math.round(Number(event.target.value) * 10) / 10000)} /> ms
      {selectedId === block.id && <button onClick={(event) => { event.stopPropagation(); onDelete(block.id); }}>Delete selected block</button>}
    </div>)}
  </section>;
}
