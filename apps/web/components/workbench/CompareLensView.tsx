"use client";
import React from "react";
import { CompareProtocol } from "../../lib/compare-engine";

interface CompareLensProps {
  protoA: CompareProtocol;
  protoB: CompareProtocol;
  onUpdateProtoA?: (updates: Partial<CompareProtocol>) => void;
  onUpdateProtoB?: (updates: Partial<CompareProtocol>) => void;
}

export function CompareLensView({ protoA, protoB }: CompareLensProps) {
  const w = 560;
  const h = 180;
  const maxEcho = 16;

  // Polyline for Proto A
  const pointsA = protoA.echoTrain
    .map((sig, idx) => {
      const x = (idx / (maxEcho - 1)) * (w - 60) + 40;
      const y = h - sig * (h - 40) - 20;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  // Polyline for Proto B
  const pointsB = protoB.echoTrain
    .map((sig, idx) => {
      const x = (idx / (maxEcho - 1)) * (w - 60) + 40;
      const y = h - sig * (h - 40) - 20;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <div className="compare-lens-container" data-testid="compare-lens">
      <header className="compare-header">
        <div className="protocol-badge proto-a">
          <span className="dot" style={{ backgroundColor: "#59e0e6" }} />
          <b>PROTOCOL A: {protoA.name}</b>
          <small>FA {protoA.flipAngleDeg}° · TE {protoA.teEffMs}ms · {protoA.b0T}T</small>
        </div>
        <div className="vs-badge">VS</div>
        <div className="protocol-badge proto-b">
          <span className="dot" style={{ backgroundColor: "#ffc45b" }} />
          <b>PROTOCOL B: {protoB.name}</b>
          <small>FA {protoB.flipAngleDeg}° · TE {protoB.teEffMs}ms · {protoB.b0T}T</small>
        </div>
      </header>

      {/* Comparison Chart: Echo Train Overlay */}
      <div className="compare-chart-panel">
        <label>ECHO TRAIN DECAY DYNAMICS (ETL=16)</label>
        <svg viewBox={`0 0 ${w} ${h}`} className="compare-svg">
          {/* Grid lines */}
          <line x1="40" y1="20" x2={w - 20} y2="20" stroke="#253347" strokeDasharray="2" />
          <line x1="40" y1={h / 2} x2={w - 20} y2={h / 2} stroke="#253347" strokeDasharray="2" />
          <line x1="40" y1={h - 20} x2={w - 20} y2={h - 20} stroke="#486581" />

          {/* Trace A */}
          <polyline points={pointsA} fill="none" stroke="#59e0e6" strokeWidth="2.5" />
          {/* Trace B */}
          <polyline points={pointsB} fill="none" stroke="#ffc45b" strokeWidth="2.5" />

          {/* Echo dots */}
          {protoA.echoTrain.map((sig, idx) => {
            const x = (idx / (maxEcho - 1)) * (w - 60) + 40;
            const y = h - sig * (h - 40) - 20;
            return <circle key={`a-${idx}`} cx={x} cy={y} r="3" fill="#59e0e6" />;
          })}
          {protoB.echoTrain.map((sig, idx) => {
            const x = (idx / (maxEcho - 1)) * (w - 60) + 40;
            const y = h - sig * (h - 40) - 20;
            return <circle key={`b-${idx}`} cx={x} cy={y} r="3" fill="#ffc45b" />;
          })}
        </svg>
        <div className="chart-legend">
          <span>Echo 1 (12.5ms)</span>
          <span>Echo 8 (100ms)</span>
          <span>Echo 16 (200ms)</span>
        </div>
      </div>

      {/* Metric Collision Matrix */}
      <div className="metric-collision-grid">
        <div className="collision-card">
          <label>ΔSignal (Contrast)</label>
          <div className="val-comparison">
            <span style={{ color: "#59e0e6" }}>{protoA.contrastDiff.toFixed(3)}</span>
            <small>vs</small>
            <span style={{ color: "#ffc45b" }}>{protoB.contrastDiff.toFixed(3)}</span>
          </div>
          <div className="diff-indicator">
            {protoB.contrastDiff >= protoA.contrastDiff
              ? `+${(((protoB.contrastDiff - protoA.contrastDiff) / protoA.contrastDiff) * 100).toFixed(1)}% in Proto B`
              : `${(((protoB.contrastDiff - protoA.contrastDiff) / protoA.contrastDiff) * 100).toFixed(1)}% in Proto B`}
          </div>
        </div>

        <div className="collision-card">
          <label>CNR Proxy</label>
          <div className="val-comparison">
            <span style={{ color: "#59e0e6" }}>{protoA.cnrProxy}</span>
            <small>vs</small>
            <span style={{ color: "#ffc45b" }}>{protoB.cnrProxy}</span>
          </div>
          <div className="diff-indicator">
            {protoB.cnrProxy >= protoA.cnrProxy ? "Higher Contrast Fidelity" : "Lower Noise Margin"}
          </div>
        </div>

        <div className="collision-card">
          <label>Relative SAR Load</label>
          <div className="val-comparison">
            <span style={{ color: "#59e0e6" }}>{protoA.relativeSar}</span>
            <small>vs</small>
            <span style={{ color: "#ffc45b" }}>{protoB.relativeSar}</span>
          </div>
          <div className="diff-indicator warn">
            {protoB.relativeSar > protoA.relativeSar
              ? `+${(protoB.relativeSar - protoA.relativeSar).toFixed(1)}x SAR Heating`
              : `${(protoB.relativeSar - protoA.relativeSar).toFixed(1)}x SAR Heating (Cooler)`}
          </div>
        </div>
      </div>
    </div>
  );
}
