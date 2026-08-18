"use client";
import React, { useMemo, useState } from "react";
import { useWorkspace } from "../workspace/WorkspaceProvider";
import { WorkbenchLens } from "../../lib/workbench-types";
import { PulseInspector } from "./PulseInspector";
import { generateSincPulseResponse } from "../../lib/pulse-inspector-data";
import { CompareLensView } from "./CompareLensView";
import { computeCompareProtocol } from "../../lib/compare-engine";

export function WorkbenchCockpit() {
  const { profile, activeLens, setActiveLens, cursors, setCursors, executionState } =
    useWorkspace();
  const [fa, setFa] = useState(150);
  const [te, setTe] = useState(100);
  const [showPulseInspector, setShowPulseInspector] = useState(false);

  // Compare Protocol B parameters
  const [faB, setFaB] = useState(120);
  const [teB, setTeB] = useState(80);

  // Generate real pulse response data linked to FA
  const pulseData = useMemo(() => {
    return generateSincPulseResponse(fa, 90, 2.5, 5.0, 4.0);
  }, [fa]);

  // Generate Compare Protocols A & B
  const protoA = useMemo(() => {
    return computeCompareProtocol("proto_a", "Standard TSE", fa, te, 3.0);
  }, [fa, te]);

  const protoB = useMemo(() => {
    return computeCompareProtocol("proto_b", "Low SAR Candidate", faB, teB, 3.0);
  }, [faB, teB]);

  // Handle echo selection for cross-lens cursor
  const handleSelectEcho = (echoNum: number, timeMs: number) => {
    setCursors({
      selectedEcho: echoNum,
      cursorTime: timeMs,
      selectedEvent: `Echo #${echoNum}`,
    });
  };

  return (
    <div className="retromorphic-cockpit">
      {/* 1. Instrument Bay: Recipe & Lens Navigation */}
      <section className="instrument-bay" data-testid="instrument-bay">
        <div className="bay-header">
          <h3>EXPERIMENT</h3>
          <span className="recipe-tag">Brain T2 TSE</span>
        </div>
        <div className="lens-selector">
          {(["sequence", "state", "acquisition", "image", "compare"] as WorkbenchLens[]).map(
            (lens) => (
              <button
                key={lens}
                className={activeLens === lens ? "lens-btn active" : "lens-btn"}
                onClick={() => setActiveLens(lens)}
                data-testid={`lens-tab-${lens}`}
              >
                {lens.toUpperCase()}
              </button>
            )
          )}
        </div>

        {/* Clinical vs Physics Side Panels */}
        <div className="bay-details">
          {profile === "clinical" ? (
            <div className="clinical-contrast-panel">
              <h4>CLINICAL CONTRAST</h4>
              <div className="tissue-row target">
                <b>Target</b>
                <span>MS Lesion</span>
                <small>T1 1400ms · T2 120ms</small>
              </div>
              <div className="tissue-row reference">
                <b>Reference</b>
                <span>White Matter</span>
                <small>T1 900ms · T2 80ms</small>
              </div>
              <div className="metrics-box">
                <div className="metric">
                  <label>ΔSignal (Contrast)</label>
                  <span>0.38 a.u.</span>
                </div>
                <div className="metric">
                  <label>CNR Proxy</label>
                  <span>7.6</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="physics-details-panel">
              <h4>PHYSICS ENGINE</h4>
              <div className="engine-badge">EPG (Configuration State)</div>
              <div className="state-metrics">
                <div>
                  <label>Max Coherence k</label>
                  <span>16</span>
                </div>
                <div>
                  <label>Refocusing Propagator</label>
                  <button
                    className="drilldown-btn"
                    data-testid="open-pulse-inspector-btn"
                    onClick={() => setShowPulseInspector(true)}
                  >
                    🔍 Inspect Sinc Pulse
                  </button>
                </div>
                <div>
                  <label>SAR Relative</label>
                  <span>{(16 * (fa / 180) ** 2).toFixed(1)}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* 2. Single Large Active Display */}
      <section className="active-lens-display" data-testid="active-lens-display">
        <div className="display-bezel">
          <header className="display-header">
            <span>ACTIVE LENS: {activeLens.toUpperCase()}</span>
            <div className="cursor-readout">
              <span data-testid="time-readout">t = {cursors.cursorTime.toFixed(1)} ms</span>
              {cursors.selectedEcho != null && (
                <span data-testid="echo-readout">Echo #{cursors.selectedEcho}</span>
              )}
            </div>
          </header>
          <div className="display-screen">
            {showPulseInspector ? (
              <PulseInspector
                pulse={pulseData}
                onClose={() => setShowPulseInspector(false)}
              />
            ) : (
              <>
                {activeLens === "sequence" && (
                  <div className="canvas-view sequence-view">
                    <svg viewBox="0 0 600 200" className="waveform-svg">
                      <path
                        d="M 0 100 L 40 100 L 45 20 L 50 100 L 150 100 L 155 40 L 160 100 L 250 100 L 255 40 L 260 100 L 600 100"
                        stroke="#59e0e6"
                        fill="none"
                        strokeWidth="2"
                      />
                      {/* Dynamic cursor line based on cursorTime */}
                      <line
                        x1={Math.min(590, Math.max(10, cursors.cursorTime * 2))}
                        y1="0"
                        x2={Math.min(590, Math.max(10, cursors.cursorTime * 2))}
                        y2="200"
                        stroke="#ffc45b"
                        strokeDasharray="4"
                      />
                    </svg>
                    <div className="screen-caption">
                      Multi-echo refocusing chain (TSE ETL=16) · Cross-Lens cursor active
                    </div>
                  </div>
                )}
                {activeLens === "state" && (
                  <div className="canvas-view epg-view">
                    <div className="epg-chart-mock">
                      EPG Coherence Transition Grid (F+/F-/Z) · Selected: Echo #{cursors.selectedEcho ?? 1}
                    </div>
                  </div>
                )}
                {activeLens === "acquisition" && (
                  <div className="canvas-view acq-view">
                    <div className="kspace-mock">
                      k-space Trajectory (Cartesian Spin Warp · ky line #{cursors.selectedEcho ?? 1})
                    </div>
                  </div>
                )}
                {activeLens === "image" && (
                  <div className="canvas-view image-view">
                    <div className="reconstruction-mock">Reconstructed T2 Magnitude Map</div>
                  </div>
                )}
                {activeLens === "compare" && (
                  <CompareLensView protoA={protoA} protoB={protoB} />
                )}
              </>
            )}
          </div>
        </div>

        {/* Linked Scope / Echo Train with Cross-Lens Selection */}
        <div className="linked-scope-rail">
          <label>INTERACTIVE ECHO TRAIN (CROSS-LENS LINKED)</label>
          <div className="echo-chips-row">
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16].map((echo) => {
              const echoTime = echo * 12.5;
              const isSelected = cursors.selectedEcho === echo;
              return (
                <button
                  key={echo}
                  className={isSelected ? "echo-chip active" : "echo-chip"}
                  onClick={() => handleSelectEcho(echo, echoTime)}
                  data-testid={`echo-chip-${echo}`}
                >
                  e{echo}
                  <small>{echoTime.toFixed(0)}ms</small>
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {/* 3. Control Bank: Physical Dial Sliders */}
      <section className="control-bank" data-testid="control-bank">
        <div className="bank-header">
          <h3>CONTROL BANK</h3>
          <span className="sub-mode">Interactive T2 Engine</span>
        </div>
        <div className="control-group">
          <label>Refocusing Flip Angle (FA) - Protocol A</label>
          <div className="slider-row">
            <input
              type="range"
              min="60"
              max="180"
              step="5"
              value={fa}
              onChange={(e) => setFa(Number(e.target.value))}
              aria-label="Refocusing Flip Angle"
            />
            <span className="value-badge">{fa}°</span>
          </div>
          <small className="bound-warn">Hardware Limit: 180° (SAR Critical above 160°)</small>
        </div>

        <div className="control-group">
          <label>Effective TE (TE_eff) - Protocol A</label>
          <div className="slider-row">
            <input
              type="range"
              min="30"
              max="200"
              step="10"
              value={te}
              onChange={(e) => setTe(Number(e.target.value))}
              aria-label="Effective TE"
            />
            <span className="value-badge">{te} ms</span>
          </div>
        </div>

        {activeLens === "compare" && (
          <>
            <div className="control-group compare-branch">
              <label>Protocol B Refocusing FA</label>
              <div className="slider-row">
                <input
                  type="range"
                  min="60"
                  max="180"
                  step="5"
                  value={faB}
                  onChange={(e) => setFaB(Number(e.target.value))}
                  aria-label="Protocol B FA"
                />
                <span className="value-badge" style={{ color: "#ffc45b" }}>{faB}°</span>
              </div>
            </div>
            <div className="control-group compare-branch">
              <label>Protocol B Effective TE</label>
              <div className="slider-row">
                <input
                  type="range"
                  min="30"
                  max="200"
                  step="10"
                  value={teB}
                  onChange={(e) => setTeB(Number(e.target.value))}
                  aria-label="Protocol B TE"
                />
                <span className="value-badge" style={{ color: "#ffc45b" }}>{teB} ms</span>
              </div>
            </div>
          </>
        )}

        <div className="action-row">
          <button className="execute-btn" data-cost="realtime">
            RUN RECONSTRUCTION
          </button>
        </div>
      </section>

      {/* 4. Status Rail: Execution State & Compute Cost */}
      <section className="status-rail" data-testid="status-rail">
        <div className="state-badge" data-state={executionState}>
          STATUS: {executionState}
        </div>
        <div className="cost-tier">COMPUTE: &lt;50ms (REALTIME INTERACTION)</div>
        <div className="system-info">MRQLab v0.3 · Physics &amp; Compare Engine Ready</div>
      </section>
    </div>
  );
}
