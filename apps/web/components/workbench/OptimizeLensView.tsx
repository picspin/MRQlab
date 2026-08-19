"use client";

import React, { useState } from "react";
import {
  OptimizationGoal,
  computeOptimization,
  ParetoPoint,
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
        color: "var(--color-fg-subtle, #94a3b8)",
        fontSize: "0.875rem",
      }}
    >
      {/* Objective Control Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          backgroundColor: "#0d131f",
          padding: "0.875rem 1rem",
          borderRadius: "6px",
          border: "1px solid #1e293b",
          flexWrap: "wrap",
          gap: "0.75rem",
        }}
      >
        <div>
          <div
            style={{
              fontSize: "0.75rem",
              textTransform: "uppercase",
              color: "#38bdf8",
              letterSpacing: "0.05em",
              fontWeight: 600,
            }}
          >
            Optimization Goal & Policy
          </div>
          <div style={{ color: "#f8fafc", fontSize: "0.95rem", fontWeight: 500 }}>
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
              padding: "0.375rem 0.75rem",
              borderRadius: "4px",
              fontSize: "0.75rem",
              fontWeight: 600,
              backgroundColor: goalMode === "max_contrast" ? "#38bdf8" : "#1e293b",
              color: goalMode === "max_contrast" ? "#0f172a" : "#94a3b8",
              border: "none",
              cursor: "pointer",
            }}
          >
            Max Contrast
          </button>
          <button
            data-testid="goal-balanced-sar"
            onClick={() => setGoalMode("balanced_sar")}
            style={{
              padding: "0.375rem 0.75rem",
              borderRadius: "4px",
              fontSize: "0.75rem",
              fontWeight: 600,
              backgroundColor: goalMode === "balanced_sar" ? "#38bdf8" : "#1e293b",
              color: goalMode === "balanced_sar" ? "#0f172a" : "#94a3b8",
              border: "none",
              cursor: "pointer",
            }}
          >
            Balanced SAR
          </button>
          <button
            data-testid="goal-min-sar"
            onClick={() => setGoalMode("min_sar")}
            style={{
              padding: "0.375rem 0.75rem",
              borderRadius: "4px",
              fontSize: "0.75rem",
              fontWeight: 600,
              backgroundColor: goalMode === "min_sar" ? "#38bdf8" : "#1e293b",
              color: goalMode === "min_sar" ? "#0f172a" : "#94a3b8",
              border: "none",
              cursor: "pointer",
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
          backgroundColor: "#0b0f17",
          padding: "0.75rem 1rem",
          borderRadius: "6px",
          border: "1px solid #1a2234",
        }}
      >
        <div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.75rem" }}>Max SAR Budget:</span>
            <span style={{ color: "#f8fafc", fontWeight: 600 }}>{maxSar.toFixed(1)}x</span>
          </div>
          <input
            type="range"
            min="15"
            max="50"
            step="1"
            value={maxSar}
            onChange={(e) => setMaxSar(parseFloat(e.target.value))}
            style={{ width: "100%", accentColor: "#ef4444" }}
          />
        </div>
        <div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.75rem" }}>Min CNR Proxy:</span>
            <span style={{ color: "#f8fafc", fontWeight: 600 }}>{minCnr.toFixed(1)}</span>
          </div>
          <input
            type="range"
            min="1.0"
            max="4.0"
            step="0.1"
            value={minCnr}
            onChange={(e) => setMinCnr(parseFloat(e.target.value))}
            style={{ width: "100%", accentColor: "#10b981" }}
          />
        </div>
      </div>

      {/* Pareto Frontier Canvas / Visual Map */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "0.5rem",
          backgroundColor: "#070a0f",
          border: "1px solid #1e293b",
          borderRadius: "6px",
          padding: "1rem",
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
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "#64748b",
            }}
          >
            Pareto Frontier (Contrast vs SAR Trade-off)
          </span>
          <span style={{ fontSize: "0.7rem", color: "#38bdf8" }}>
            ● Recommended Optimum &nbsp; ○ Feasible Candidates
          </span>
        </div>

        {/* SVG Scatter & Curve */}
        <div
          style={{
            height: "180px",
            width: "100%",
            backgroundColor: "#04070c",
            borderRadius: "4px",
            position: "relative",
            border: "1px solid #151e2e",
          }}
        >
          <svg width="100%" height="100%" viewBox="0 0 500 180" preserveAspectRatio="none">
            {/* Grid Lines */}
            <line x1="40" y1="20" x2="480" y2="20" stroke="#1e293b" strokeDasharray="3 3" />
            <line x1="40" y1="90" x2="480" y2="90" stroke="#1e293b" strokeDasharray="3 3" />
            <line x1="40" y1="150" x2="480" y2="150" stroke="#334155" />
            <line x1="40" y1="10" x2="40" y2="150" stroke="#334155" />

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
                    strokeWidth="1.5"
                  />
                  <text x={sarX + 4} y="30" fill="#ef4444" fontSize="9">
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
                    r={isOpt ? 6 : 3.5}
                    fill={isOpt ? "#38bdf8" : p.isFeasible ? "#10b981" : "#64748b"}
                    stroke={isOpt ? "#ffffff" : "none"}
                    strokeWidth={isOpt ? 2 : 0}
                  />
                  {isOpt && (
                    <text
                      x={Math.min(430, x + 8)}
                      y={y - 6}
                      fill="#38bdf8"
                      fontSize="10"
                      fontWeight="bold"
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
            fontSize: "0.7rem",
            color: "#64748b",
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
          backgroundColor: "#0d131f",
          padding: "1rem",
          borderRadius: "6px",
          border: "1px solid #1e293b",
          alignItems: "center",
        }}
      >
        <div>
          <div
            style={{
              fontSize: "0.75rem",
              color: "#38bdf8",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              fontWeight: 600,
            }}
          >
            Recommended Protocol Parameters
          </div>
          <div
            style={{
              fontSize: "1.1rem",
              fontWeight: 700,
              color: "#f8fafc",
              marginTop: "0.25rem",
            }}
          >
            Flip Angle: {optimalCandidate.flipAngle}° &nbsp;·&nbsp; Effective TE:{" "}
            {optimalCandidate.teEff} ms
          </div>
          <div
            style={{
              fontSize: "0.8rem",
              color: "#94a3b8",
              marginTop: "0.25rem",
            }}
          >
            Predicted Contrast ΔSignal: <b>{optimalCandidate.contrast}</b> · CNR
            Proxy: <b>{optimalCandidate.cnrProxy}</b> · Relative SAR:{" "}
            <b>{optimalCandidate.relativeSar}x</b>
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button
            data-testid="apply-optimal-button"
            onClick={() =>
              onApplyOptimal(optimalCandidate.flipAngle, optimalCandidate.teEff)
            }
            style={{
              backgroundColor: "#0284c7",
              color: "#ffffff",
              border: "none",
              borderRadius: "4px",
              padding: "0.625rem 1rem",
              fontWeight: 600,
              fontSize: "0.8rem",
              cursor: "pointer",
              boxShadow: "0 2px 4px rgba(0,0,0,0.3)",
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
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            color: "#64748b",
          }}
        >
          Sensitivity Gradients (Local Derivatives ∂/∂θ)
        </span>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "0.75rem",
          }}
        >
          {sensitivities.map((s, idx) => (
            <div
              key={idx}
              style={{
                backgroundColor: "#0b0f17",
                padding: "0.625rem 0.875rem",
                borderRadius: "4px",
                border: "1px solid #1a2234",
              }}
            >
              <div style={{ fontWeight: 600, color: "#f8fafc" }}>
                {s.parameter}
              </div>
              <div
                style={{
                  fontSize: "0.75rem",
                  color: "#94a3b8",
                  marginTop: "0.25rem",
                }}
              >
                ∂CNR / ∂θ:{" "}
                <span
                  style={{
                    color: s.dCnr >= 0 ? "#10b981" : "#ef4444",
                    fontWeight: 600,
                  }}
                >
                  {s.dCnr > 0 ? `+${s.dCnr}` : s.dCnr} / unit
                </span>
                &nbsp;|&nbsp; ∂SAR / ∂θ:{" "}
                <span style={{ color: "#fbbf24", fontWeight: 600 }}>
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
