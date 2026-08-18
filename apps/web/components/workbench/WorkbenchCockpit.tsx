"use client";
import { useState } from "react";
import { useWorkspace } from "../workspace/WorkspaceProvider";
import { WorkbenchLens } from "../../lib/workbench-types";

export function WorkbenchCockpit() {
  const { profile, activeLens, setActiveLens, cursors, setCursors, executionState } =
    useWorkspace();
  const [fa, setFa] = useState(150);
  const [te, setTe] = useState(100);

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
                  <span>Hard/Sinc matrix</span>
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
              <span>t = {cursors.cursorTime.toFixed(1)} ms</span>
              {cursors.selectedEcho && <span>Echo #{cursors.selectedEcho}</span>}
            </div>
          </header>
          <div className="display-screen">
            {activeLens === "sequence" && (
              <div className="canvas-view sequence-view">
                <svg viewBox="0 0 600 200" className="waveform-svg">
                  <path d="M 0 100 L 40 100 L 45 20 L 50 100 L 150 100 L 155 40 L 160 100 L 600 100" stroke="#59e0e6" fill="none" strokeWidth="2" />
                  <line x1="155" y1="0" x2="155" y2="200" stroke="#ffc45b" strokeDasharray="4" />
                </svg>
                <div className="screen-caption">Multi-echo refocusing chain (TSE ETL=16)</div>
              </div>
            )}
            {activeLens === "state" && (
              <div className="canvas-view epg-view">
                <div className="epg-chart-mock">EPG Coherence Transition Grid (F+/F-/Z)</div>
              </div>
            )}
            {activeLens === "acquisition" && (
              <div className="canvas-view acq-view">
                <div className="kspace-mock">k-space Trajectory (Cartesian Spin Warp)</div>
              </div>
            )}
            {activeLens === "image" && (
              <div className="canvas-view image-view">
                <div className="reconstruction-mock">Reconstructed T2 Magnitude Map</div>
              </div>
            )}
            {activeLens === "compare" && (
              <div className="canvas-view compare-view">
                <div className="compare-mock">A/B Dual Parameter Trace (FA 120° vs 160°)</div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 3. Control Bank */}
      <section className="control-bank" data-testid="control-bank">
        <h4>CONTROL BANK</h4>
        <div className="control-dial">
          <label>Refocusing FA: {fa}°</label>
          <input
            type="range"
            min="60"
            max="180"
            value={fa}
            onChange={(e) => setFa(+e.target.value)}
          />
        </div>
        <div className="control-dial">
          <label>Effective TE: {te} ms</label>
          <input
            type="range"
            min="20"
            max="200"
            value={te}
            onChange={(e) => setTe(+e.target.value)}
          />
        </div>
        <div className="interactive-trigger">
          <button className="run-button">EXECUTE (0-Token)</button>
        </div>
      </section>

      {/* 4. Status Rail */}
      <section className="status-rail" data-testid="status-rail">
        <span>STATUS: {executionState}</span>
        <span className="cost-tag">Cost: &lt;50ms (Realtime)</span>
      </section>
    </div>
  );
}
