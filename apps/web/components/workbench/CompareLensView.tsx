"use client";

import React, { useEffect, useId, useState } from "react";
import { CompareAnalysis, fetchCompare } from "../../lib/api";

interface CompareLensViewProps {
  currentFa: number;
  currentTe: number;
}

export const CompareLensView: React.FC<CompareLensViewProps> = ({ currentFa, currentTe }) => {
  const maskId = useId();
  const [faB, setFaB] = useState(120);
  const [teB, setTeB] = useState(80);
  const [analysis, setAnalysis] = useState<CompareAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    fetchCompare({
      protocol_a: { id: "A", name: "Protocol A", flip_angle_deg: currentFa, te_eff_ms: currentTe, b0_t: 3.0 },
      protocol_b: { id: "B", name: "Protocol B", flip_angle_deg: faB, te_eff_ms: teB, b0_t: 3.0 },
    })
      .then((payload) => {
        if (!cancelled) setAnalysis(payload);
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setAnalysis(null);
          setError(err.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [currentFa, currentTe, faB, teB]);

  const protoA = analysis?.protocol_a;
  const protoB = analysis?.protocol_b;
  const deltaContrastDiff = analysis?.delta.contrast_pct ?? 0;
  const sarDifference = analysis?.delta.sar_delta ?? 0;

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
            PROTOCOL A: LIVE
          </span>
          <span style={{ color: "#ffffff", fontSize: "0.95rem", fontWeight: 700 }} data-testid="compare-proto-a">
            FA {currentFa}° · TE {currentTe}ms · 3T
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

        <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem", textAlign: "right" }}>
          <span
            style={{
              fontSize: "0.75rem",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--amber)",
              fontWeight: 800,
            }}
          >
            PROTOCOL B: CHALLENGER
          </span>
          <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end", alignItems: "center" }}>
            <label style={{ fontSize: "11px", color: "#8da1aa", fontFamily: "monospace" }}>
              FA
              <input
                data-testid="compare-fa-b"
                type="number"
                min={90}
                max={180}
                step={5}
                value={faB}
                onChange={(e) => setFaB(Number(e.target.value))}
                style={{
                  width: "64px",
                  marginLeft: "4px",
                  background: "#0c1114",
                  color: "var(--amber)",
                  border: "1px solid #3d4c53",
                  borderRadius: "3px",
                  padding: "2px 4px",
                }}
              />
            </label>
            <label style={{ fontSize: "11px", color: "#8da1aa", fontFamily: "monospace" }}>
              TE
              <input
                data-testid="compare-te-b"
                type="number"
                min={40}
                max={160}
                step={5}
                value={teB}
                onChange={(e) => setTeB(Number(e.target.value))}
                style={{
                  width: "64px",
                  marginLeft: "4px",
                  background: "#0c1114",
                  color: "var(--amber)",
                  border: "1px solid #3d4c53",
                  borderRadius: "3px",
                  padding: "2px 4px",
                }}
              />
            </label>
          </div>
        </div>
      </div>

      {error && (
        <div data-testid="compare-backend-wait" style={{ fontSize: "11px", color: "#f59e0b", fontFamily: "monospace" }}>
          awaiting backend compare payload · {error}
        </div>
      )}

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
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
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

        <div style={{ height: "180px", width: "100%", position: "relative" }}>
          <svg width="100%" height="100%" viewBox="0 0 500 180" preserveAspectRatio="none" data-testid="compare-svg">
            <defs>
              <clipPath id={maskId}>
                <rect x="0" y="0" width="500" height="180" />
              </clipPath>
            </defs>
            {protoA && (
              <path
                d={protoA.echo_train.map((sig, i) => `${i === 0 ? "M" : "L"} ${30 + i * 28} ${160 - sig * 140}`).join(" ")}
                fill="none"
                stroke="var(--cyan)"
                strokeWidth="2.5"
              />
            )}
            {protoB && (
              <path
                d={protoB.echo_train.map((sig, i) => `${i === 0 ? "M" : "L"} ${30 + i * 28} ${160 - sig * 140}`).join(" ")}
                fill="none"
                stroke="var(--amber)"
                strokeWidth="2.5"
                strokeDasharray="4 2"
              />
            )}
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

      {protoA && protoB && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.875rem" }} data-testid="compare-metrics">
          <div
            style={{
              backgroundColor: "#101618",
              border: "1px solid #2d3b40",
              borderRadius: "6px",
              padding: "0.875rem",
            }}
          >
            <div style={{ fontSize: "0.75rem", color: "#8da1aa", fontWeight: 700, marginBottom: "0.25rem" }}>
              ΔSignal (Contrast)
            </div>
            <div style={{ fontSize: "1.1rem", fontWeight: 900, fontFamily: "monospace", color: "#ffffff" }}>
              <span style={{ color: "var(--cyan)" }}>{protoA.contrast_diff.toFixed(3)}</span>
              <span style={{ color: "#6b828c", fontSize: "0.85rem" }}> vs </span>
              <span style={{ color: "var(--amber)" }}>{protoB.contrast_diff.toFixed(3)}</span>
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

          <div
            style={{
              backgroundColor: "#101618",
              border: "1px solid #2d3b40",
              borderRadius: "6px",
              padding: "0.875rem",
            }}
          >
            <div style={{ fontSize: "0.75rem", color: "#8da1aa", fontWeight: 700, marginBottom: "0.25rem" }}>CNR Proxy</div>
            <div style={{ fontSize: "1.1rem", fontWeight: 900, fontFamily: "monospace", color: "#ffffff" }}>
              <span style={{ color: "var(--cyan)" }}>{protoA.cnr_proxy.toFixed(2)}</span>
              <span style={{ color: "#6b828c", fontSize: "0.85rem" }}> vs </span>
              <span style={{ color: "var(--amber)" }}>{protoB.cnr_proxy.toFixed(2)}</span>
            </div>
          </div>

          <div
            style={{
              backgroundColor: "#101618",
              border: "1px solid #2d3b40",
              borderRadius: "6px",
              padding: "0.875rem",
            }}
          >
            <div style={{ fontSize: "0.75rem", color: "#8da1aa", fontWeight: 700, marginBottom: "0.25rem" }}>
              Relative SAR Load
            </div>
            <div style={{ fontSize: "1.1rem", fontWeight: 900, fontFamily: "monospace", color: "#ffffff" }}>
              <span style={{ color: "var(--cyan)" }}>{protoA.relative_sar.toFixed(1)}</span>
              <span style={{ color: "#6b828c", fontSize: "0.85rem" }}> vs </span>
              <span style={{ color: "var(--amber)" }}>{protoB.relative_sar.toFixed(1)}</span>
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
      )}
    </div>
  );
};
