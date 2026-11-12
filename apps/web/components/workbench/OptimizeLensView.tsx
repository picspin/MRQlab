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
        color: "var(--text)",
        fontSize: "12px",
        width: "100%",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          backgroundColor: "var(--surface)",
          padding: "0.875rem 1.25rem",
          borderRadius: "4px",
          border: ".5px solid var(--border)",
          flexWrap: "wrap",
          gap: "0.75rem",
          boxShadow: "none",
        }}
      >
        <div>
          <div
            style={{
              fontSize: "12px",
              textTransform: "uppercase",
              color: "var(--cyan)",
              letterSpacing: "0.08em",
              fontWeight: 800,
            }}
          >
            Optimization Goal & Policy
          </div>
          <div style={{ color: "var(--text)", fontSize: "14px", fontWeight: 700, marginTop: "2px" }}>
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
              fontSize: "12px",
              fontWeight: 700,
              backgroundColor: goalMode === "max_contrast" ? "var(--cyan)" : "var(--surface)",
              color: goalMode === "max_contrast" ? "var(--surface-sunken)" : "var(--text-muted)",
              border: ".5px solid var(--border)",
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
              fontSize: "12px",
              fontWeight: 700,
              backgroundColor: goalMode === "balanced_sar" ? "var(--cyan)" : "var(--surface)",
              color: goalMode === "balanced_sar" ? "var(--surface-sunken)" : "var(--text-muted)",
              border: ".5px solid var(--border)",
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
              fontSize: "12px",
              fontWeight: 700,
              backgroundColor: goalMode === "min_sar" ? "var(--cyan)" : "var(--surface)",
              color: goalMode === "min_sar" ? "var(--surface-sunken)" : "var(--text-muted)",
              border: ".5px solid var(--border)",
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
          backgroundColor: "var(--surface)",
          padding: "0.875rem 1.25rem",
          borderRadius: "4px",
          border: ".5px solid var(--border)",
        }}
      >
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
            <span style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 700 }}>Max SAR Budget:</span>
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
            <span style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 700 }}>Min CNR Proxy:</span>
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
        <div data-testid="optimize-backend-wait" style={{ fontSize: "12px", color: "var(--amber-11)", fontFamily: "monospace" }}>
          awaiting backend pareto payload  --  {error}
        </div>
      )}
      {loading && (
        <div data-testid="optimize-loading" style={{ fontSize: "12px", color: "var(--cyan)", fontFamily: "monospace" }}>
          solving Pareto grid…
        </div>
      )}

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "0.5rem",
          backgroundColor: "var(--bg-crt)",
          border: ".5px solid var(--border)",
          borderRadius: "4px",
          padding: "1rem",
          boxShadow: "none",
          backgroundImage:
            "linear-gradient(var(--graticule) 1px, transparent 1px), linear-gradient(90deg, var(--graticule) 1px, transparent 1px)",
          backgroundSize: "20px 20px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span
            style={{
              fontSize: "12px",
              fontWeight: 800,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--text-muted)",
            }}
          >
            PARETO FRONTIER (CONTRAST VS SAR TRADE-OFF)
          </span>
          <span style={{ fontSize: "12px", color: "var(--cyan)", fontFamily: "monospace" }}>
            ● Recommended Optimum &nbsp; ○ Feasible Frontier
          </span>
        </div>

        <div style={{ height: "180px", width: "100%", position: "relative" }}>
          <svg width="100%" height="100%" viewBox="0 0 500 180" preserveAspectRatio="none" data-testid="pareto-svg">
            <line x1="40" y1="20" x2="480" y2="20" stroke="var(--surface)" strokeDasharray="3 3" />
            <line x1="40" y1="90" x2="480" y2="90" stroke="var(--surface)" strokeDasharray="3 3" />
            <line x1="40" y1="150" x2="480" y2="150" stroke="var(--border)" strokeWidth="2" />
            <line x1="40" y1="10" x2="40" y2="150" stroke="var(--border)" strokeWidth="2" />

            {(() => {
              const sarX = 40 + ((maxSar - 15) / 35) * 440;
              return (
                <g>
                  <line x1={sarX} y1="10" x2={sarX} y2="150" stroke="var(--red-11)" strokeDasharray="4 2" strokeWidth="2" />
                  <text x={sarX + 6} y="28" fill="var(--red-11)" fontSize="10" fontWeight="bold">
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
                    fill={isOpt ? "var(--cyan)" : p.is_feasible ? "var(--green-neon)" : "var(--border)"}
                    stroke={isOpt ? "var(--text)" : "none"}
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
            fontSize: "12px",
            color: "var(--text-muted)",
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
            backgroundColor: "var(--surface)",
            padding: "1rem 1.25rem",
            borderRadius: "4px",
            border: ".5px solid var(--border)",
            alignItems: "center",
            boxShadow: "none",
          }}
        >
          <div>
            <div
              style={{
                fontSize: "12px",
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
                fontSize: "16px",
                fontWeight: 900,
                color: "var(--text)",
                marginTop: "0.25rem",
                fontFamily: "monospace",
              }}
              data-testid="optimal-params"
            >
              Flip Angle: {optimalCandidate.flip_angle}° &nbsp; -- &nbsp; Effective TE: {optimalCandidate.te_eff} ms
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "0.35rem", fontFamily: "monospace" }}>
              Predicted ΔSignal: <b style={{ color: "var(--text)" }}>{optimalCandidate.contrast}</b>  --  CNR Proxy:{" "}
              <b style={{ color: "var(--green-neon)" }}>{optimalCandidate.cnr_proxy}</b>  --  Relative SAR:{" "}
              <b style={{ color: "var(--amber)" }}>{optimalCandidate.relative_sar}x</b>
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button
              data-testid="apply-optimal-button"
              onClick={() => onApplyOptimal(optimalCandidate.flip_angle, optimalCandidate.te_eff)}
              style={{
                backgroundColor: "var(--cyan)",
                color: "var(--surface-sunken)",
                border: "none",
                borderRadius: "6px",
                padding: "0.75rem 1.25rem",
                fontWeight: 900,
                fontSize: "12px",
                cursor: "pointer",
                boxShadow: "none",
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
            fontSize: "12px",
            fontWeight: 800,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--text-muted)",
          }}
        >
          SENSITIVITY GRADIENTS (LOCAL DERIVATIVES ∂/∂θ)
        </span>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.875rem" }}>
          {sensitivities.map((s, idx) => (
            <div
              key={idx}
              style={{
                backgroundColor: "var(--surface)",
                padding: "0.75rem 1rem",
                borderRadius: "6px",
                border: ".5px solid var(--border)",
              }}
            >
              <div style={{ fontWeight: 800, color: "var(--text)", fontSize: "12px" }}>{s.parameter}</div>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "0.35rem", fontFamily: "monospace" }}>
                ∂CNR / ∂θ:{" "}
                <span style={{ color: s.d_cnr >= 0 ? "var(--green-neon)" : "var(--red-11)", fontWeight: "bold" }}>
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
