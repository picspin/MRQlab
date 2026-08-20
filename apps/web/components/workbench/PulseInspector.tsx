"use client";

import React, { useEffect, useState } from "react";
import { fetchPulseInspect, PulseInspectAnalysis } from "../../lib/api";

interface PulseInspectorProps {
  flipAngleDeg: number;
  sliceThicknessMm?: number;
  onClose?: () => void;
}

export function PulseInspector({ flipAngleDeg, sliceThicknessMm = 5.0, onClose }: PulseInspectorProps) {
  const [pulse, setPulse] = useState<PulseInspectAnalysis | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchPulseInspect({
      flip_angle_deg: flipAngleDeg,
      slice_thickness_mm: sliceThicknessMm,
    })
      .then((payload) => {
        if (!cancelled) setPulse(payload);
      })
      .catch(() => {
        if (!cancelled) setPulse(null);
      });
    return () => {
      cancelled = true;
    };
  }, [flipAngleDeg, sliceThicknessMm]);

  const w = 240;
  const h = 100;

  const wavePoints = pulse
    ? pulse.waveform_time
        .map((t, idx) => {
          const span = pulse.waveform_time[pulse.waveform_time.length - 1] - pulse.waveform_time[0];
          const x = ((t - pulse.waveform_time[0]) / span) * w;
          const b1 = pulse.waveform_b1[idx];
          const y = h / 2 - (b1 / Math.max(...pulse.waveform_b1, 1e-3)) * (h * 0.4);
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(" ")
    : "";

  const slicePoints = pulse
    ? pulse.spatial_axis_mm
        .map((z, idx) => {
          const span = pulse.spatial_axis_mm[pulse.spatial_axis_mm.length - 1] - pulse.spatial_axis_mm[0];
          const x = ((z - pulse.spatial_axis_mm[0]) / span) * w;
          const mxy = pulse.slice_profile_mxy[idx];
          const y = h - mxy * (h * 0.8) - 10;
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(" ")
    : "";

  const freqPoints = pulse
    ? pulse.freq_axis_khz
        .map((f, idx) => {
          const span = pulse.freq_axis_khz[pulse.freq_axis_khz.length - 1] - pulse.freq_axis_khz[0];
          const x = ((f - pulse.freq_axis_khz[0]) / span) * w;
          const mag = pulse.freq_response_mag[idx];
          const y = h - mag * (h * 0.8) - 10;
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(" ")
    : "";

  return (
    <div className="pulse-inspector" data-testid="pulse-inspector">
      <header className="inspector-header">
        <div className="title-group">
          <span className="pulse-tag">PULSE INSPECTOR</span>
          <h3>{pulse?.name ?? "Awaiting backend pulse payload"}</h3>
        </div>
        <div className="pulse-params-badge">
          <span>FA: {pulse?.flip_angle_deg ?? flipAngleDeg}°</span>
          <span>Phase: {pulse?.phase_deg ?? 90}°</span>
          <span>T_dur: {pulse?.duration_ms ?? 2.5} ms</span>
          <span>TBW: {pulse?.time_bandwidth ?? 4}</span>
          <span>Δz: {pulse?.slice_thickness_mm ?? sliceThicknessMm} mm</span>
        </div>
        {onClose && (
          <button className="close-btn" onClick={onClose} aria-label="Close Inspector">
            ×
          </button>
        )}
      </header>

      <div className="inspector-grid">
        <div className="chart-panel waveform-panel">
          <label>B1(t) Envelope (RF Waveform)</label>
          <svg viewBox={`0 0 ${w} ${h}`} className="inspector-svg" data-testid="pulse-b1-svg">
            <line x1="0" y1={h / 2} x2={w} y2={h / 2} stroke="#3b4f68" strokeDasharray="2" />
            {wavePoints && <polyline points={wavePoints} fill="none" stroke="#59e0e6" strokeWidth="2" />}
          </svg>
          <div className="axis-legend">
            <span>-{((pulse?.duration_ms ?? 2.5) / 2).toFixed(1)} ms</span>
            <span>0</span>
            <span>+{((pulse?.duration_ms ?? 2.5) / 2).toFixed(1)} ms</span>
          </div>
        </div>

        <div className="chart-panel freq-panel">
          <label>Frequency Response |Mxy(f)|</label>
          <svg viewBox={`0 0 ${w} ${h}`} className="inspector-svg">
            <line x1="0" y1={h - 10} x2={w} y2={h - 10} stroke="#3b4f68" strokeDasharray="2" />
            {freqPoints && <polyline points={freqPoints} fill="none" stroke="#ffc45b" strokeWidth="2" />}
          </svg>
          <div className="axis-legend">
            <span>{pulse ? pulse.freq_axis_khz[0].toFixed(1) : "—"} kHz</span>
            <span>0</span>
            <span>{pulse ? pulse.freq_axis_khz[pulse.freq_axis_khz.length - 1].toFixed(1) : "—"} kHz</span>
          </div>
        </div>

        <div className="chart-panel slice-panel">
          <label>Slice Profile Mxy(z) &amp; Thickness</label>
          <svg viewBox={`0 0 ${w} ${h}`} className="inspector-svg">
            <line x1="0" y1={h - 10} x2={w} y2={h - 10} stroke="#3b4f68" strokeDasharray="2" />
            <line x1={w / 2 - w / 6} y1="0" x2={w / 2 - w / 6} y2={h} stroke="#e65a5a" strokeDasharray="3" />
            <line x1={w / 2 + w / 6} y1="0" x2={w / 2 + w / 6} y2={h} stroke="#e65a5a" strokeDasharray="3" />
            {slicePoints && <polyline points={slicePoints} fill="none" stroke="#8ae65a" strokeWidth="2" />}
          </svg>
          <div className="axis-legend">
            <span>{pulse ? pulse.spatial_axis_mm[0].toFixed(1) : "—"} mm</span>
            <span>z=0</span>
            <span>{pulse ? pulse.spatial_axis_mm[pulse.spatial_axis_mm.length - 1].toFixed(1) : "—"} mm</span>
          </div>
        </div>

        <div className="chart-panel epg-matrix-panel">
          <label>EPG Coherence Transfer (|T_epg|)</label>
          <div className="matrix-table" data-testid="pulse-epg-matrix">
            <div className="matrix-row header">
              <span></span>
              <span>F+</span>
              <span>F-</span>
              <span>Z</span>
            </div>
            {(pulse?.epg_transition_matrix ?? []).map((row, rIdx) => (
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
