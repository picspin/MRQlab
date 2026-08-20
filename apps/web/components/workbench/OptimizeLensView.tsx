"use client";

import React, { useEffect, useState } from "react";
import { fetchPareto, OptimizeAnalysis, OptimizeMode, ParetoPoint } from "../../lib/api";

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
  const [goalMode, setGoalMode] = useState<OptimizeMode>("balanced_sar");
  const [maxSar, setMaxSar] = useState<number>(35.0);
  const [minCnr, setMinCnr] = useState<number>(2.5);
  const [analysis, setAnalysis] = useState<OptimizeAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchPareto({
      mode: goalMode,
      max_sar_budget: maxSar,
      min_cnr_proxy: minCnr,
      current_fa_deg: currentFa,
      current_te_ms: currentTe,
    })
      .then((payload) => {
        if (!cancelled) setAnalysis(payload);
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setAnalysis(null);
          setError(err.message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [goalMode, maxSar, minCnr, currentFa, currentTe]);

  const optimalCandidate: ParetoPoint | undefined = analysis?.optimal_candidate;
  const paretoFrontier: ParetoPoint[] = analysis?.pareto_frontier ?? [];
  const sensitivities = analysis?.sensitivities ?? [];

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
            }}
          >
            Min SAR (Cool)
          </button>
        </div>
      </div>

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
            data-testid="max-sar-slider"
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
            data-testid="min-cnr-slider"
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

      {error && (
        <div data-testid="optimize-backend-wait" style={{ fontSize: "11px", color: "#f59e0b", fontFamily: "monospace" }}>
          awaiting backend pareto payload · {error}
        </div>
      )}
      {loading && (
        <div data-testid="optimize-loading" style={{ fontSize: "11px", color: "var(--cyan)", fontFamily: "monospace" }}>
          solving Pareto grid…
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
            PARETO FRONTIER (CONTRAST VS SAR TRADE-OFF)
          </span>
          <span style={{ fontSize: "0.75rem", color: "var(--cyan)", fontFamily: "monospace" }}>
            ● Recommended Optimum &nbsp; ○ Feasible Frontier
          </span>
        </div>

        <div style={{ height: "180px", width: "100%", position: "relative" }}>
          <svg width="100%" height="100%" viewBox="0 0 500 180" preserveAspectRatio="none" data-testid="pareto-svg">
            <line x1="40" y1="20" x2="480" y2="20" stroke="#253238" strokeDasharray="3 3" />
            <line x1="40" y1="90" x2="480" y2="90" stroke="#253238" strokeDasharray="3 3" />
            <line x1="40" y1="150" x2="480" y2="150" stroke="#3b4d55" strokeWidth="2" />
            <line x1="40" y1="10" x2="40" y2="150" stroke="#3b4d55" strokeWidth="2" />

            {(() => {
              const sarX = 40 + ((maxSar - 15) / 35) * 440;
              return (
                <g>
                  <line x1={sarX} y1="10" x2={sarX} y2="150" stroke="#ef4444" strokeDasharray="4 2" strokeWidth="2" />
                  <text x={sarX + 6} y="28" fill="#ef4444" fontSize="10" fontWeight="bold">
                    SAR Limit
                  </text>
                </g>
              );
            })()}

            {paretoFrontier.map((p, idx) => {
              const x = 40 + ((p.relative_sar - 15) / 35) * 440;
              const y = 150 - (p.cnr_proxy / 5.0) * 130;
              const isOpt =
                !!optimalCandidate &&
                p.flip_angle === optimalCandidate.flip_angle &&
                p.te_eff === optimalCandidate.te_eff;

              return (
                <g key={idx}>
                  <circle
                    cx={x}
                    cy={y}
                    r={isOpt ? 7 : 4}
                    fill={isOpt ? "var(--cyan)" : p.is_feasible ? "var(--green-neon)" : "#4a5960"}
                    stroke={isOpt ? "#ffffff" : "none"}
                    strokeWidth={isOpt ? 2 : 0}
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
                      Optimal (FA {p.flip_angle}°, TE {p.te_eff}ms)
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

      {optimalCandidate && (
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
              data-testid="optimal-params"
            >
              Flip Angle: {optimalCandidate.flip_angle}° &nbsp;·&nbsp; Effective TE: {optimalCandidate.te_eff} ms
            </div>
            <div style={{ fontSize: "0.8rem", color: "#8da1aa", marginTop: "0.35rem", fontFamily: "monospace" }}>
              Predicted ΔSignal: <b style={{ color: "#fff" }}>{optimalCandidate.contrast}</b> · CNR Proxy:{" "}
              <b style={{ color: "var(--green-neon)" }}>{optimalCandidate.cnr_proxy}</b> · Relative SAR:{" "}
              <b style={{ color: "var(--amber)" }}>{optimalCandidate.relative_sar}x</b>
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button
              data-testid="apply-optimal-button"
              onClick={() => onApplyOptimal(optimalCandidate.flip_angle, optimalCandidate.te_eff)}
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
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
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
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.875rem" }}>
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
              <div style={{ fontWeight: 800, color: "#ffffff", fontSize: "0.85rem" }}>{s.parameter}</div>
              <div style={{ fontSize: "0.75rem", color: "#8da1aa", marginTop: "0.35rem", fontFamily: "monospace" }}>
                ∂CNR / ∂θ:{" "}
                <span style={{ color: s.d_cnr >= 0 ? "var(--green-neon)" : "#ef4444", fontWeight: "bold" }}>
                  {s.d_cnr > 0 ? `+${s.d_cnr}` : s.d_cnr} / unit
                </span>
                &nbsp;|&nbsp; ∂SAR / ∂θ:{" "}
                <span style={{ color: "var(--amber)", fontWeight: "bold" }}>+{s.d_sar} / unit</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
