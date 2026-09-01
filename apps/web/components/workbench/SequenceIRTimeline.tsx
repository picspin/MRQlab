"use client";

import React from "react";
import { SequenceBlockKind } from "../../lib/api";
import { SequenceIR, TEACHING_CHANNELS, ChannelName } from "../../lib/sequence-ir";

const LABELS: Record<ChannelName, string> = {
  rf_amp: "RF",
  rf_phase: "φRF",
  gx: "Gx",
  gy: "Gy",
  gz: "Gz",
  adc_gate: "ADC",
  nco_freq: "NCO f",
  nco_phase: "NCO φ",
};

const COLORS: Record<string, string> = {
  rf_amp: "var(--cyan)",
  gx: "#3bf48d",
  gy: "#f59e0b",
  gz: "#c084fc",
  adc_gate: "#fb7185",
};

const BLOCK_KINDS = new Set<SequenceBlockKind>(["excite_sinc", "refocus_sinc", "trap_gx", "trap_gy", "trap_gz", "adc_gate"]);

export function SequenceIRTimeline({
  sequence,
  cursorTimeMs,
  selectedEventKey,
  onSelectEvent,
  onDropBlock,
}: {
  sequence: SequenceIR;
  cursorTimeMs?: number;
  selectedEventKey?: string;
  onSelectEvent?: (channel: string, time: number, value: number, index: number) => void;
  onDropBlock?: (kind: SequenceBlockKind, channel: ChannelName, t0_s: number) => void;
}) {
  const durationMs = sequence.duration * 1000;
  const width = 600;
  const rowH = 36;
  const height = 16 + TEACHING_CHANNELS.length * rowH;

  const xOf = (tSec: number) => 48 + (tSec / Math.max(sequence.duration, 1e-9)) * (width - 60);
  const t0FromX = (x: number) => Math.round(((x - 48) / (width - 60)) * Math.max(sequence.duration, 1e-9) * 10000) / 10000;

  const readDropX = (event: React.DragEvent) => {
    const bag = event as unknown as { offsetX?: number; clientX?: number };
    const native = event.nativeEvent as unknown as { offsetX?: number; clientX?: number };
    const pick = (...vals: Array<number | undefined>) => {
      for (const value of vals) {
        if (typeof value === "number" && Number.isFinite(value) && value !== 0) return value;
      }
      return 0;
    };
    const offsetX = pick(bag.offsetX, native.offsetX);
    if (offsetX) return offsetX;
    const clientX = pick(bag.clientX, event.clientX, native.clientX);
    const svg = (event.currentTarget as Element).closest("svg");
    const rect = svg?.getBoundingClientRect();
    if (rect && rect.width > 0) return ((clientX - rect.left) / rect.width) * width;
    return clientX;
  };

  const dropOnRow = (name: ChannelName, event: React.DragEvent) => {
    event.preventDefault();
    const raw = event.dataTransfer.getData("text/plain") as SequenceBlockKind;
    if (!BLOCK_KINDS.has(raw)) return;
    const t0 = Math.min(Math.max(0, t0FromX(readDropX(event))), sequence.duration);
    onDropBlock?.(raw, name, t0);
  };

  return (
    <div data-testid="sequence-ir-timeline" style={{ width: "100%", height: "100%" }}>
      <div
        data-testid="timeline-duration"
        style={{ fontSize: "10px", color: "#8ea1a8", fontFamily: "monospace", marginBottom: "4px" }}
      >
        {durationMs.toFixed(1)} ms · {sequence.name} · {sequence.metadata?.gradient_units === "mt_m" ? "Gx/Gy/Gz mT/m" : "SequenceIR 5-ch"}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: `${height + 8}px` }}>
        {TEACHING_CHANNELS.map((name, row) => {
          const y0 = 20 + row * rowH;
          const ch = sequence.channels.find((c) => c.name === name);
          const events = ch?.events ?? [];
          const peak = Math.max(1e-6, ...events.map((e) => Math.abs(e.value)), 1);
          return (
            <g key={name} data-testid={`ch-${name}`}
              onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; }}
              onDrop={(event) => dropOnRow(name, event)}>
              <rect x="0" y={y0 - 16} width={width} height={rowH} fill="transparent" />
              <text x="4" y={y0 + 4} fill="#8ea1a8" fontSize="9" fontFamily="monospace">
                {LABELS[name]}
              </text>
              <line x1="48" y1={y0} x2={width - 8} y2={y0} stroke="#25373f" />
              {events.map((ev, i) => {
                const eventKey = `${name}-${i}`;
                const selected = selectedEventKey === eventKey;
                const x = xOf(ev.time);
                const h = (Math.abs(ev.value) / peak) * 14;
                const y = ev.value >= 0 ? y0 - h : y0;
                return (
                  <rect
                    key={`${name}-${i}`}
                    data-testid={`event-${eventKey}`}
                    data-value={ev.value}
                    x={x - 2}
                    y={name === "adc_gate" ? y0 - 8 : y}
                    width={name === "adc_gate" ? 8 : 4}
                    height={name === "adc_gate" ? 16 : Math.max(2, h)}
                    fill={COLORS[name] ?? "var(--cyan)"}
                    opacity={selected ? 1 : 0.9}
                    stroke={selected ? "#fff" : "none"}
                    strokeWidth={selected ? 2 : 0}
                    style={{ cursor: "pointer" }}
                    onClick={() => onSelectEvent?.(name, ev.time, ev.value, i)}
                  />
                );
              })}
            </g>
          );
        })}
        {cursorTimeMs != null && (
          <line
            x1={xOf(cursorTimeMs / 1000)}
            y1={8}
            x2={xOf(cursorTimeMs / 1000)}
            y2={height - 4}
            stroke="var(--cyan)"
            strokeDasharray="3 3"
            strokeWidth="1.2"
          />
        )}
      </svg>
    </div>
  );
}
