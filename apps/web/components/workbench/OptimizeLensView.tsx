"use client";

import React, { useState } from "react";
import {
  computeOptimization,
} from "../../lib/optimize-engine";

interface OptimizeLensViewProps {
  currentFa: number;
  currentTe: number;
  onApplyOptimal: (fa: number, te: number) => void;
}

export const OptimizeLensView: React.FC<OptimizeLensViewProps> = ({
  currentFa,
  currentTe,
  onApplyOptimal,
}) => {
  const [goalMode, setGoalMode] = useState<
    "max_contrast" | "balanced_sar" | "min_sar"
  >("balanced_sar");
  const [maxSar, setMaxSar] = useState<number>(35.0);
  const [minCnr, setMinCnr] = useState<number>(2.5);

  const analysis = computeOptimization({
    mode: goalMode,
    maxSarBudget: maxSar,
    minCnrProxy: minCnr,
  });

  const { optimalCandidate, paretoFrontier, sensitivities } = analysis;

  return (
    <div
      data-testid="optimize-lens-view"
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
      {/* Objective Control Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          backgroundColor: "#101618",
          padding: "0.875rem 1.25rem",
          borderRadius: "8px",
          border: "2px solid #2e3b40",
          flexWrap: "wrap",
          gap: "0.75rem",
          boxShadow: "inset 0 2px 6px rgba(0,0,0,0.6)",
        }}
      >
        <div>
          <div
            style={{
              fontSize: "0.75rem",
              textTransform: "uppercase",
              color: "var(--cyan)",
              letterSpacing: "0.08em",
              fontWeight: 800,
            }}
          >
            Optimization Goal & Policy
          </div>
          <div style={{ color: "#ffffff", fontSize: "0.95rem", fontWeight: 700, marginTop: "2px" }}>
            {goalMode === "max_contrast" && "Maximum Contrast-to-Noise"}
            {goalMode === "balanced_sar" && "Balanced SAR & Diagnostic Contrast"}
            {goalMode === "min_sar" && "Minimum SAR / Thermal Safety First"}
          </div>
        </div>

        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            data-testid="goal-max-contrast"
            onClick={() => setGoalMode("max_contrast")}
            style={{
              padding: "0.45rem 0.85rem",
              borderRadius: "4px",
              fontSize: "0.75rem",
              fontWeight: 700,
              backgroundColor: goalMode === "max_contrast" ? "var(--cyan)" : "#1e262a",
              color: goalMode === "max_contrast" ? "#061012" : "#92a6af",
              border: "1px solid #3d4c53",
              cursor: "pointer",
              boxShadow: goalMode === "max_contrast" ? "0 0 10px var(--cyan-glow)" : "none",
            }}
          >
            Max Contrast
          </button>
          <button
            data-testid="goal-balanced-sar"
            onClick={() => setGoalMode("balanced_sar")}
            style={{
              padding: "0.45rem 0.85rem",
              borderRadius: "4px",
              fontSize: "0.75rem",
              fontWeight: 700,
              backgroundColor: goalMode === "balanced_sar" ? "var(--cyan)" : "#1e262a",
              color: goalMode === "balanced_sar" ? "#061012" : "#92a6af",
              border: "1px solid #3d4c53",
              cursor: "pointer",
              boxShadow: goalMode === "balanced_sar" ? "0 0 10px var(--cyan-glow)" : "none",
            }}
          >
            Balanced SAR
          </button>
          <button
            data-testid="goal-min-sar"
            onClick={() => setGoalMode("min_sar")}
            style={{
              padding: "0.45rem 0.85rem",
              borderRadius: "4px",
              fontSize: "0.75rem",
              fontWeight: 700,
              backgroundColor: goalMode === "min_sar" ? "var(--cyan)" : "#1e262a",
              color: goalMode === "min_sar" ? "#061012" : "#92a6af",
              border: "1px solid #3d4c53",
              cursor: "pointer",
              boxShadow: goalMode === "min_sar" ? "0 0 10px var(--cyan-glow)" : "none",
            }}
          >
            Min SAR (Cool)
          </button>
        </div>
      </div>

      {/* Constraints Bar */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "1rem",
          backgroundColor: "#101618",
          padding: "0.875rem 1.25rem",
          borderRadius: "8px",
          border: "1px solid #283439",
        }}
      >
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
            <span style={{ fontSize: "0.75rem", color: "#8da1aa", fontWeight: 700 }}>Max SAR Budget:</span>
            <span style={{ color: "var(--orange-neon)", fontWeight: 800, fontFamily: "monospace" }}>{maxSar.toFixed(1)}x</span>
          </div>
          <input
            type="range"
            min="15"
            max="50"
            step="1"
            value={maxSar}
            onChange={(e) => setMaxSar(parseFloat(e.target.value))}
            style={{ width: "100%", accentColor: "var(--orange-neon)" }}
          />
        </div>
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
            <span style={{ fontSize: "0.75rem", color: "#8da1aa", fontWeight: 700 }}>Min CNR Proxy:</span>
            <span style={{ color: "var(--green-neon)", fontWeight: 800, fontFamily: "monospace" }}>{minCnr.toFixed(1)}</span>
          </div>
          <input
            type="range"
            min="1.0"
            max="4.0"
            step="0.1"
            value={minCnr}
            onChange={(e) => setMinCnr(parseFloat(e.target.value))}
            style={{ width: "100%", accentColor: "var(--green-neon)" }}
          />
        </div>
      </div>

      {/* Pareto Frontier Canvas / Visual Map */}
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
          backgroundImage:
            "linear-gradient(var(--graticule) 1px, transparent 1px), linear-gradient(90deg, var(--graticule) 1px, transparent 1px)",
          backgroundSize: "20px 20px",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span
            style={{
              fontSize: "0.75rem",
              fontWeight: 800,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "#8da1aa",
            }}
          >
            PARETO FRONTIER (CONTRAST VS SAR TRADE-OFF)
          </span>
          <span style={{ fontSize: "0.75rem", color: "var(--cyan)", fontFamily: "monospace" }}>
            ● Recommended Optimum &nbsp; ○ Feasible Candidates
          </span>
        </div>

        {/* SVG Scatter & Curve */}
        <div style={{ height: "180px", width: "100%", position: "relative" }}>
          <svg width="100%" height="100%" viewBox="0 0 500 180" preserveAspectRatio="none">
            {/* Grid Axes */}
            <line x1="40" y1="20" x2="480" y2="20" stroke="#253238" strokeDasharray="3 3" />
            <line x1="40" y1="90" x2="480" y2="90" stroke="#253238" strokeDasharray="3 3" />
            <line x1="40" y1="150" x2="480" y2="150" stroke="#3b4d55" strokeWidth="2" />
            <line x1="40" y1="10" x2="40" y2="150" stroke="#3b4d55" strokeWidth="2" />

            {/* SAR Budget Limit Line */}
            {(() => {
              const sarX = 40 + ((maxSar - 15) / 35) * 440;
              return (
                <g>
                  <line
                    x1={sarX}
                    y1="10"
                    x2={sarX}
                    y2="150"
                    stroke="#ef4444"
                    strokeDasharray="4 2"
                    strokeWidth="2"
                  />
                  <text x={sarX + 6} y="28" fill="#ef4444" fontSize="10" fontWeight="bold">
                    SAR Limit
                  </text>
                </g>
              );
            })()}

            {/* Pareto Points */}
            {paretoFrontier.map((p, idx) => {
              const x = 40 + ((p.relativeSar - 15) / 35) * 440;
              const y = 150 - (p.cnrProxy / 5.0) * 130;
              const isOpt =
                p.flipAngle === optimalCandidate.flipAngle &&
                p.teEff === optimalCandidate.teEff;

              return (
                <g key={idx}>
                  <circle
                    cx={x}
                    cy={y}
                    r={isOpt ? 7 : 4}
                    fill={isOpt ? "var(--cyan)" : p.isFeasible ? "var(--green-neon)" : "#4a5960"}
                    stroke={isOpt ? "#ffffff" : "none"}
                    strokeWidth={isOpt ? 2 : 0}
                    style={{
                      filter: isOpt
                        ? "drop-shadow(0 0 8px var(--cyan-glow))"
                        : p.isFeasible
                        ? "drop-shadow(0 0 4px var(--green-glow))"
                        : "none",
                    }}
                  />
                  {isOpt && (
                    <text
                      x={Math.min(410, x + 10)}
                      y={y - 8}
                      fill="var(--cyan)"
                      fontSize="11"
                      fontWeight="bold"
                      fontFamily="monospace"
                    >
                      Optimal (FA {p.flipAngle}°, TE {p.teEff}ms)
                    </text>
                  )}
                </g>
              );
            })}
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
          <span>Low SAR (15x)</span>
          <span>Relative SAR Heat Load →</span>
          <span>High SAR (50x)</span>
        </div>
      </div>

      {/* Optimal Candidate Card & Apply Action */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "2fr 1fr",
          gap: "1rem",
          backgroundColor: "#101618",
          padding: "1rem 1.25rem",
          borderRadius: "8px",
          border: "2px solid #2e3b40",
          alignItems: "center",
          boxShadow: "inset 0 1px 0 #46575f",
        }}
      >
        <div>
          <div
            style={{
              fontSize: "0.75rem",
              color: "var(--amber)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              fontWeight: 800,
            }}
          >
            RECOMMENDED PROTOCOL PARAMETERS
          </div>
          <div
            style={{
              fontSize: "1.2rem",
              fontWeight: 900,
              color: "#ffffff",
              marginTop: "0.25rem",
              fontFamily: "monospace",
            }}
          >
            Flip Angle: {optimalCandidate.flipAngle}° &nbsp;·&nbsp; Effective TE:{" "}
            {optimalCandidate.teEff} ms
          </div>
          <div
            style={{
              fontSize: "0.8rem",
              color: "#8da1aa",
              marginTop: "0.35rem",
              fontFamily: "monospace",
            }}
          >
            Predicted ΔSignal: <b style={{ color: "#fff" }}>{optimalCandidate.contrast}</b> · CNR
            Proxy: <b style={{ color: "var(--green-neon)" }}>{optimalCandidate.cnrProxy}</b> · Relative SAR:{" "}
            <b style={{ color: "var(--amber)" }}>{optimalCandidate.relativeSar}x</b>
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button
            data-testid="apply-optimal-button"
            onClick={() =>
              onApplyOptimal(optimalCandidate.flipAngle, optimalCandidate.teEff)
            }
            style={{
              backgroundColor: "var(--cyan)",
              color: "#061012",
              border: "none",
              borderRadius: "6px",
              padding: "0.75rem 1.25rem",
              fontWeight: 900,
              fontSize: "0.85rem",
              cursor: "pointer",
              boxShadow: "0 0 12px var(--cyan-glow)",
              letterSpacing: "0.5px",
            }}
          >
            Apply to Protocol
          </button>
        </div>
      </div>

      {/* Parameter Sensitivity Gradients */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "0.5rem",
        }}
      >
        <span
          style={{
            fontSize: "0.75rem",
            fontWeight: 800,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "#8da1aa",
          }}
        >
          SENSITIVITY GRADIENTS (LOCAL DERIVATIVES ∂/∂θ)
        </span>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "0.875rem",
          }}
        >
          {sensitivities.map((s, idx) => (
            <div
              key={idx}
              style={{
                backgroundColor: "#101618",
                padding: "0.75rem 1rem",
                borderRadius: "6px",
                border: "1px solid #283439",
              }}
            >
              <div style={{ fontWeight: 800, color: "#ffffff", fontSize: "0.85rem" }}>
                {s.parameter}
              </div>
              <div
                style={{
                  fontSize: "0.75rem",
                  color: "#8da1aa",
                  marginTop: "0.35rem",
                  fontFamily: "monospace",
                }}
              >
                ∂CNR / ∂θ:{" "}
                <span
                  style={{
                    color: s.dCnr >= 0 ? "var(--green-neon)" : "#ef4444",
                    fontWeight: "bold",
                  }}
                >
                  {s.dCnr > 0 ? `+${s.dCnr}` : s.dCnr} / unit
                </span>
                &nbsp;|&nbsp; ∂SAR / ∂θ:{" "}
                <span style={{ color: "var(--amber)", fontWeight: "bold" }}>
                  +{s.dSar} / unit
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
