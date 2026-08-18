"use client";
import React from "react";
import { PulseInspectorData } from "../../lib/pulse-inspector-data";

interface PulseInspectorProps {
  pulse: PulseInspectorData;
  onClose?: () => void;
}

export function PulseInspector({ pulse, onClose }: PulseInspectorProps) {
  // SVG helpers
  const w = 240;
  const h = 100;

  // Waveform polyline points
  const wavePoints = pulse.waveformTime
    .map((t, idx) => {
      const x = ((t - pulse.waveformTime[0]) / (pulse.waveformTime[pulse.waveformTime.length - 1] - pulse.waveformTime[0])) * w;
      const b1 = pulse.waveformB1[idx];
      const y = h / 2 - (b1 / Math.max(...pulse.waveformB1, 1e-3)) * (h * 0.4);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  // Slice profile points (Mxy)
  const slicePoints = pulse.spatialAxisMm
    .map((z, idx) => {
      const x = ((z - pulse.spatialAxisMm[0]) / (pulse.spatialAxisMm[pulse.spatialAxisMm.length - 1] - pulse.spatialAxisMm[0])) * w;
      const mxy = pulse.sliceProfileMxy[idx];
      const y = h - mxy * (h * 0.8) - 10;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  // Frequency response points
  const freqPoints = pulse.freqAxisKhz
    .map((f, idx) => {
      const x = ((f - pulse.freqAxisKhz[0]) / (pulse.freqAxisKhz[pulse.freqAxisKhz.length - 1] - pulse.freqAxisKhz[0])) * w;
      const mag = pulse.freqResponseMag[idx];
      const y = h - mag * (h * 0.8) - 10;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <div className="pulse-inspector" data-testid="pulse-inspector">
      <header className="inspector-header">
        <div className="title-group">
          <span className="pulse-tag">PULSE INSPECTOR</span>
          <h3>{pulse.name}</h3>
        </div>
        <div className="pulse-params-badge">
          <span>FA: {pulse.flipAngleDeg}°</span>
          <span>Phase: {pulse.phaseDeg}°</span>
          <span>T_dur: {pulse.durationMs} ms</span>
          <span>TBW: {pulse.timeBandwidth}</span>
          <span>Δz: {pulse.sliceThicknessMm} mm</span>
        </div>
        {onClose && (
          <button className="close-btn" onClick={onClose} aria-label="Close Inspector">
            ×
          </button>
        )}
      </header>

      <div className="inspector-grid">
        {/* Panel 1: Time Waveform B1(t) */}
        <div className="chart-panel waveform-panel">
          <label>B1(t) Envelope (RF Waveform)</label>
          <svg viewBox={`0 0 ${w} ${h}`} className="inspector-svg">
            <line x1="0" y1={h / 2} x2={w} y2={h / 2} stroke="#3b4f68" strokeDasharray="2" />
            <polyline points={wavePoints} fill="none" stroke="#59e0e6" strokeWidth="2" />
          </svg>
          <div className="axis-legend">
            <span>-{(pulse.durationMs / 2).toFixed(1)} ms</span>
            <span>0</span>
            <span>+{(pulse.durationMs / 2).toFixed(1)} ms</span>
          </div>
        </div>

        {/* Panel 2: Frequency Response |Mxy(f)| */}
        <div className="chart-panel freq-panel">
          <label>Frequency Response |Mxy(f)|</label>
          <svg viewBox={`0 0 ${w} ${h}`} className="inspector-svg">
            <line x1="0" y1={h - 10} x2={w} y2={h - 10} stroke="#3b4f68" strokeDasharray="2" />
            <polyline points={freqPoints} fill="none" stroke="#ffc45b" strokeWidth="2" />
          </svg>
          <div className="axis-legend">
            <span>{pulse.freqAxisKhz[0].toFixed(1)} kHz</span>
            <span>0</span>
            <span>{pulse.freqAxisKhz[pulse.freqAxisKhz.length - 1].toFixed(1)} kHz</span>
          </div>
        </div>

        {/* Panel 3: Slice Profile Mxy(z) */}
        <div className="chart-panel slice-panel">
          <label>Slice Profile Mxy(z) &amp; Thickness</label>
          <svg viewBox={`0 0 ${w} ${h}`} className="inspector-svg">
            <line x1="0" y1={h - 10} x2={w} y2={h - 10} stroke="#3b4f68" strokeDasharray="2" />
            {/* Slice boundary markers */}
            <line
              x1={w / 2 - (w / 6)}
              y1="0"
              x2={w / 2 - (w / 6)}
              y2={h}
              stroke="#e65a5a"
              strokeDasharray="3"
            />
            <line
              x1={w / 2 + (w / 6)}
              y1="0"
              x2={w / 2 + (w / 6)}
              y2={h}
              stroke="#e65a5a"
              strokeDasharray="3"
            />
            <polyline points={slicePoints} fill="none" stroke="#8ae65a" strokeWidth="2" />
          </svg>
          <div className="axis-legend">
            <span>{pulse.spatialAxisMm[0].toFixed(1)} mm</span>
            <span>z=0</span>
            <span>{pulse.spatialAxisMm[pulse.spatialAxisMm.length - 1].toFixed(1)} mm</span>
          </div>
        </div>

        {/* Panel 4: EPG Coherence Transfer Matrix */}
        <div className="chart-panel epg-matrix-panel">
          <label>EPG Coherence Transfer (|T_epg|)</label>
          <div className="matrix-table">
            <div className="matrix-row header">
              <span></span>
              <span>F+</span>
              <span>F-</span>
              <span>Z</span>
            </div>
            {pulse.epgTransitionMatrix.map((row, rIdx) => (
              <div className="matrix-row" key={rIdx}>
                <span className="row-label">{rIdx === 0 ? "F+" : rIdx === 1 ? "F-" : "Z"}</span>
                {row.map((val, cIdx) => (
                  <span
                    key={cIdx}
                    className="matrix-cell"
                    style={{
                      backgroundColor: `rgba(89, 224, 230, ${Math.min(1, Math.abs(val)).toFixed(2)})`,
                    }}
                  >
                    {val.toFixed(2)}
                  </span>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
