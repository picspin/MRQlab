"use client";

import React from "react";

export interface SlabStackViewProps {
  sliceCount: number;
  sliceThickMm: number;
  sliceGapMm: number;
  isInterleaved: boolean;
  cursorIndex: number;
  onSelect?: (index: number) => void;
}

export function SlabStackView({
  sliceCount,
  sliceThickMm,
  sliceGapMm,
  isInterleaved,
  cursorIndex,
  onSelect,
}: SlabStackViewProps) {
  const n = Math.max(1, Math.round(sliceCount));
  const extentMm = n * sliceThickMm + Math.max(0, n - 1) * sliceGapMm;
  const scale = 180 / Math.max(extentMm, 1e-6);

  return (
    <div data-testid="slab-stack-view" style={{ display: "flex", flexDirection: "column", height: "100%", gap: "6px" }}>
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "stretch",
          background: "#030608",
          border: "1px solid #1e2c33",
          borderRadius: "3px",
          padding: "8px 10px",
          minHeight: "140px",
        }}
      >
        {Array.from({ length: n }).map((_, i) => {
          const isEven = i % 2 === 1;
          const isCur = cursorIndex === i;
          const color = isInterleaved ? (isEven ? "var(--amber)" : "var(--cyan)") : "#38bdf8";
          return (
            <React.Fragment key={i}>
              <button
                type="button"
                data-testid={`slab-slice-${i}`}
                data-thick-mm={sliceThickMm}
                onClick={() => onSelect?.(i)}
                style={{
                  display: "block",
                  width: "100%",
                  height: `${Math.max(4, sliceThickMm * scale)}px`,
                  backgroundColor: color,
                  opacity: isCur ? 1 : 0.45,
                  border: isCur ? "1px solid #fff" : "1px solid transparent",
                  borderRadius: "2px",
                  cursor: "pointer",
                  padding: 0,
                }}
                aria-label={`slice ${i + 1}`}
              />
              {i < n - 1 && (
                <div
                  data-testid={`slab-gap-${i}`}
                  data-gap-mm={sliceGapMm}
                  style={{ height: `${Math.max(2, sliceGapMm * scale)}px`, background: "transparent" }}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>
      <div style={{ fontSize: "10px", color: "#8ea1a8", display: "flex", justifyContent: "space-between", fontFamily: "monospace" }}>
        <span data-testid="slab-extent">{extentMm.toFixed(1)}mm</span>
        <span>
          Slice #{cursorIndex + 1} / {n} · {sliceThickMm}mm / gap {sliceGapMm}mm
        </span>
      </div>
    </div>
  );
}
