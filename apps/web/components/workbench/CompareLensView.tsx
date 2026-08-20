"use client";

import React, { useId } from "react";
import { CompareProtocol } from "../../lib/compare-engine";

interface CompareLensViewProps {
  protoA: CompareProtocol;
  protoB: CompareProtocol;
}

export const CompareLensView: React.FC<CompareLensViewProps> = ({
  protoA,
  protoB,
}) => {
  const maskId = useId();

  // Metrics diff
  const deltaContrastDiff =
    ((protoB.contrastDiff - protoA.contrastDiff) / (protoA.contrastDiff || 1)) * 100;
  const sarDifference = protoB.relativeSar - protoA.relativeSar;

  return (
    <div
      data-testid="compare-lens"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "1.25rem",
        height: "100%",
        color: "#d1dde2",
        fontSize: "0.875rem",
        width: "100%",
      }}
    >
      {/* 1. Protocol Comparison Badges */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr auto 1fr",
          alignItems: "center",
          gap: "1rem",
          backgroundColor: "#101618",
          padding: "0.875rem 1.25rem",
          borderRadius: "8px",
          border: "2px solid #2e3b40",
          boxShadow: "inset 0 2px 6px rgba(0,0,0,0.6)",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <span
            style={{
              fontSize: "0.75rem",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--cyan)",
              fontWeight: 800,
            }}
          >
            PROTOCOL A: {protoA.name}
          </span>
          <span style={{ color: "#ffffff", fontSize: "0.95rem", fontWeight: 700 }}>
            FA {protoA.flipAngleDeg}° · TE {protoA.teEffMs}ms · {protoA.b0T}T
          </span>
        </div>

        <div
          style={{
            fontSize: "0.85rem",
            fontWeight: 900,
            color: "#6b828c",
            padding: "0.3rem 0.6rem",
            backgroundColor: "#070b0c",
            borderRadius: "4px",
            border: "1px solid #243035",
          }}
        >
          VS
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", textAlign: "right" }}>
          <span
            style={{
              fontSize: "0.75rem",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--amber)",
              fontWeight: 800,
            }}
          >
            PROTOCOL B: {protoB.name}
          </span>
          <span style={{ color: "#ffffff", fontSize: "0.95rem", fontWeight: 700 }}>
            FA {protoB.flipAngleDeg}° · TE {protoB.teEffMs}ms · {protoB.b0T}T
          </span>
        </div>
      </div>

      {/* 2. Oscilloscope CRT Comparison Display */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "0.5rem",
          backgroundColor: "var(--bg-crt)",
          border: "2px solid #273439",
          borderRadius: "8px",
          padding: "1rem",
          boxShadow: "inset 0 0 16px rgba(0,0,0,0.8)",
          position: "relative",
          backgroundImage:
            "linear-gradient(var(--graticule) 1px, transparent 1px), linear-gradient(90deg, var(--graticule) 1px, transparent 1px)",
          backgroundSize: "20px 20px",
        }}
      >
        <div style={{ display: "flex", justifySelf: "stretch", justifyContent: "space-between", alignItems: "center" }}>
          <span
            style={{
              fontSize: "0.75rem",
              fontWeight: 800,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "#8da1aa",
            }}
          >
            ECHO TRAIN DECAY DYNAMICS (ETL=16)
          </span>
          <span style={{ fontSize: "0.75rem", fontFamily: "monospace" }}>
            <span style={{ color: "var(--cyan)", fontWeight: "bold" }}>― Proto A</span>
            &nbsp;&nbsp;
            <span style={{ color: "var(--amber)", fontWeight: "bold" }}>― Proto B</span>
          </span>
        </div>

        {/* SVG Dynamic Scope Curves */}
        <div style={{ height: "180px", width: "100%", position: "relative" }}>
          <svg width="100%" height="100%" viewBox="0 0 500 180" preserveAspectRatio="none">
            <defs>
              <clipPath id={maskId}>
                <rect x="0" y="0" width="500" height="180" />
              </clipPath>
            </defs>

            {/* Target Tissue Decay Curves */}
            <path
              d={protoA.echoTrain
                .map((sig, i) => `${i === 0 ? "M" : "L"} ${30 + i * 28} ${160 - sig * 140}`)
                .join(" ")}
              fill="none"
              stroke="var(--cyan)"
              strokeWidth="2.5"
              style={{ filter: "drop-shadow(0 0 4px var(--cyan-glow))" }}
            />
            <path
              d={protoB.echoTrain
                .map((sig, i) => `${i === 0 ? "M" : "L"} ${30 + i * 28} ${160 - sig * 140}`)
                .join(" ")}
              fill="none"
              stroke="var(--amber)"
              strokeWidth="2.5"
              strokeDasharray="4 2"
              style={{ filter: "drop-shadow(0 0 4px var(--amber-glow))" }}
            />

            {/* Echo Echo Points */}
            {protoA.echoTrain.map((sig, i) => (
              <circle
                key={`a-${i}`}
                cx={30 + i * 28}
                cy={160 - sig * 140}
                r="3"
                fill="var(--cyan)"
              />
            ))}
            {protoB.echoTrain.map((sig, i) => (
              <circle
                key={`b-${i}`}
                cx={30 + i * 28}
                cy={160 - sig * 140}
                r="3"
                fill="var(--amber)"
              />
            ))}
          </svg>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: "0.75rem",
            color: "#6b828c",
            fontFamily: "monospace",
          }}
        >
          <span>Echo 1 (12.5ms)</span>
          <span>Echo 8 (100ms)</span>
          <span>Echo 16 (200ms)</span>
        </div>
      </div>

      {/* 3. Physical Metric Array Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: "0.875rem",
        }}
      >
        {/* Metric 1: Delta Signal */}
        <div
          style={{
            backgroundColor: "#101618",
            border: "1px solid #2d3b40",
            borderRadius: "6px",
            padding: "0.875rem",
            boxShadow: "inset 0 1px 0 #3e5058",
          }}
        >
          <div style={{ fontSize: "0.75rem", color: "#8da1aa", fontWeight: 700, marginBottom: "0.25rem" }}>
            ΔSignal (Contrast)
          </div>
          <div style={{ fontSize: "1.1rem", fontWeight: 900, fontFamily: "monospace", color: "#ffffff" }}>
            <span style={{ color: "var(--cyan)" }}>{protoA.contrastDiff.toFixed(3)}</span>
            <span style={{ color: "#6b828c", fontSize: "0.85rem" }}> vs </span>
            <span style={{ color: "var(--amber)" }}>{protoB.contrastDiff.toFixed(3)}</span>
          </div>
          <div
            style={{
              fontSize: "0.75rem",
              marginTop: "0.35rem",
              color: deltaContrastDiff >= 0 ? "var(--green-neon)" : "#ff7e33",
              fontWeight: "bold",
            }}
          >
            {deltaContrastDiff > 0 ? `+${deltaContrastDiff.toFixed(1)}%` : `${deltaContrastDiff.toFixed(1)}%`} in Proto B
          </div>
        </div>

        {/* Metric 2: CNR Proxy */}
        <div
          style={{
            backgroundColor: "#101618",
            border: "1px solid #2d3b40",
            borderRadius: "6px",
            padding: "0.875rem",
            boxShadow: "inset 0 1px 0 #3e5058",
          }}
        >
          <div style={{ fontSize: "0.75rem", color: "#8da1aa", fontWeight: 700, marginBottom: "0.25rem" }}>
            CNR Proxy
          </div>
          <div style={{ fontSize: "1.1rem", fontWeight: 900, fontFamily: "monospace", color: "#ffffff" }}>
            <span style={{ color: "var(--cyan)" }}>{protoA.cnrProxy.toFixed(2)}</span>
            <span style={{ color: "#6b828c", fontSize: "0.85rem" }}> vs </span>
            <span style={{ color: "var(--amber)" }}>{protoB.cnrProxy.toFixed(2)}</span>
          </div>
          <div style={{ fontSize: "0.75rem", marginTop: "0.35rem", color: "#8da1aa" }}>
            {protoB.cnrProxy >= protoA.cnrProxy ? "Higher Contrast" : "Lower Noise Margin"}
          </div>
        </div>

        {/* Metric 3: SAR Load */}
        <div
          style={{
            backgroundColor: "#101618",
            border: "1px solid #2d3b40",
            borderRadius: "6px",
            padding: "0.875rem",
            boxShadow: "inset 0 1px 0 #3e5058",
          }}
        >
          <div style={{ fontSize: "0.75rem", color: "#8da1aa", fontWeight: 700, marginBottom: "0.25rem" }}>
            Relative SAR Load
          </div>
          <div style={{ fontSize: "1.1rem", fontWeight: 900, fontFamily: "monospace", color: "#ffffff" }}>
            <span style={{ color: "var(--cyan)" }}>{protoA.relativeSar.toFixed(1)}</span>
            <span style={{ color: "#6b828c", fontSize: "0.85rem" }}> vs </span>
            <span style={{ color: "var(--amber)" }}>{protoB.relativeSar.toFixed(1)}</span>
          </div>
          <div
            style={{
              fontSize: "0.75rem",
              marginTop: "0.35rem",
              color: sarDifference <= 0 ? "var(--green-neon)" : "var(--orange-neon)",
              fontWeight: "bold",
            }}
          >
            {sarDifference <= 0
              ? `${sarDifference.toFixed(1)}x SAR Heating (Cooler)`
              : `+${sarDifference.toFixed(1)}x SAR Heating`}
          </div>
        </div>
      </div>
    </div>
  );
};
