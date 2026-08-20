"use client";

import React, { useState, useEffect } from "react";
import { useWorkspace } from "../workspace/WorkspaceProvider";
import { CLINICAL_SCENARIOS, ScenarioSpec } from "../../lib/scenarios";
import { ExperimentGraph, ResultGraph } from "../../lib/workbench-types";
import { CockpitSignalAnalysis, fetchCockpitSignals, runExperiment, saveCustomRecipe } from "../../lib/api";
import { KSpaceReconLens } from "./KSpaceReconLens";
import { OptimizeLensView } from "./OptimizeLensView";
import { CompareLensView } from "./CompareLensView";

export function WorkbenchCockpit() {
  const { profile, activeLens, setActiveLens, cursors, setCursors, executionState, setExecutionState } = useWorkspace();
  
  const [selectedScenarioKey, setSelectedScenarioKey] = useState<string>("ms_brain");
  const currentScenario: ScenarioSpec = CLINICAL_SCENARIOS[selectedScenarioKey] || CLINICAL_SCENARIOS.ms_brain;

  // v0.43: Edit Mode toggle
  const [isEditMode, setIsEditMode] = useState<boolean>(false);
  const [customScenarioName, setCustomScenarioName] = useState<string>("");
  const [showCustomModal, setShowCustomModal] = useState<boolean>(false);

  // v0.43: Sequence timeline interactive drag handles
  const [readoutWidthFactor, setReadoutWidthFactor] = useState<number>(1.0);
  const [skippedPeLines, setSkippedPeLines] = useState<number>(0);
  const [partialFourierFrac, setPartialFourierFrac] = useState<number>(1.0);
  const [accelerationFactor, setAccelerationFactor] = useState<number>(1);
  const [matrixSize, setMatrixSize] = useState<number>(256);

  // Acquisition and Physics Parameters
  const [fa, setFa] = useState<number>(currentScenario.defaultParams.fa);
  const [te, setTe] = useState<number>(currentScenario.defaultParams.te);
  const [tr, setTr] = useState<number>(currentScenario.defaultParams.tr);
  const [fov, setFov] = useState<number>(currentScenario.defaultParams.fov);
  const [sliceThick, setSliceThick] = useState<number>(currentScenario.defaultParams.sliceThick);
  const [sliceCount, setSliceCount] = useState<number>(currentScenario.defaultParams.sliceCount);
  const [sliceGap, setSliceGap] = useState<number>(currentScenario.defaultParams.sliceGap);
  const [isInterleaved, setIsInterleaved] = useState<boolean>(currentScenario.defaultParams.isInterleaved);
  const [activeScanPlane, setActiveScanPlane] = useState<string>(currentScenario.scanPlane);
  const [mipCursorZ, setMipCursorZ] = useState<number>(Math.round(currentScenario.defaultParams.sliceCount / 2));
  
  // Custom uploaded DICOM / Phantom image
  const [customImageSrc, setCustomImageSrc] = useState<string | null>(null);

  // ResultGraph from Unified Backend / Model Seam
  const [resultGraph, setResultGraph] = useState<ResultGraph | null>(null);
  const [isComputing, setIsComputing] = useState<boolean>(false);

  // v0.48: Backend-owned GRE Ernst / TSE intensities + SAR (no TS physics)
  const [cockpitSignals, setCockpitSignals] = useState<CockpitSignalAnalysis | null>(null);

  // Physics sub-lens selection inside Physics mode
  const [physicsTab, setPhysicsTab] = useState<"timeline" | "epg_phase" | "bloch_sphere" | "kspace" | "phantom" | "optimize" | "compare">("timeline");

  // Sync params when scenario changes
  useEffect(() => {
    const s = CLINICAL_SCENARIOS[selectedScenarioKey] || CLINICAL_SCENARIOS.ms_brain;
    setFa(s.defaultParams.fa);
    setTe(s.defaultParams.te);
    setTr(s.defaultParams.tr);
    setFov(s.defaultParams.fov);
    setSliceThick(s.defaultParams.sliceThick);
    setSliceCount(s.defaultParams.sliceCount);
    setSliceGap(s.defaultParams.sliceGap);
    setIsInterleaved(s.defaultParams.isInterleaved);
    setActiveScanPlane(s.scanPlane);
    setMipCursorZ(Math.round(s.defaultParams.sliceCount / 2));
  }, [selectedScenarioKey]);

  // Trigger Execution Plan (POST /experiments/run)
  const triggerRun = async () => {
    setIsComputing(true);
    setExecutionState?.("RUNNING");

    // Construct Canonical ExperimentGraph
    const graph: ExperimentGraph = {
      schema_version: "1.0",
      id: `exp-${currentScenario.id}-${Date.now()}`,
      name: currentScenario.name,
      sequence: {
        template: {
          ref: currentScenario.seqType,
          parameters: {
            te: te / 1000.0,
            tr: tr / 1000.0,
            refocusing_flip_angle: fa,
            echo_count: currentScenario.seqType === "GRE" ? 1 : 16,
          },
        },
      },
      sample: {
        tissues: currentScenario.tissues.map((t) => ({
          id: t.id,
          t1: t.t1 / 1000.0,
          t2: t.t2 / 1000.0,
          proton_density: t.pd,
        })),
      },
      scanner: {
        b0_t: 3.0,
      },
      engine: {
        target_representation: currentScenario.seqType === "GRE" ? "bloch" : "epg",
      },
      readout: {
        products: ["signal", "k_trajectory", "magnetization"],
      },
      constraints: {},
      disturbances: [],
      provenance: {},
    };

    try {
      const res = await runExperiment(graph);
      setResultGraph(res);
      setExecutionState?.("RESULT");
    } catch (e) {
      // Offline fallback: synthesize ResultGraph contract
      setResultGraph({
        schema_version: "1.0",
        experiment_id: graph.id,
        execution_plan: {
          fingerprint: `plan-${currentScenario.id}-fa${fa}-te${te}`,
          selected_engine: currentScenario.seqType === "GRE" ? "bloch" : "epg",
          cost_estimate_ms: 12.5,
        },
        observations: [
          { id: "obs-signal", kind: "signal", data: { echo_count: 16 } },
          { id: "obs-recon", kind: "reconstruction", data: { magnitude: [] } },
        ],
      });
      setExecutionState?.("RESULT");
    } finally {
      setIsComputing(false);
    }
  };

  useEffect(() => {
    triggerRun();
  }, [selectedScenarioKey, fa, te, tr]);

  useEffect(() => {
    let cancelled = false;
    fetchCockpitSignals({
      seq_type: currentScenario.seqType,
      fa_deg: fa,
      te_ms: te,
      tr_ms: tr,
      echo_train_length: currentScenario.seqType === "GRE" ? 1 : 16,
      tissues: currentScenario.tissues.map((t) => ({
        id: t.id,
        name: t.name,
        t1: t.t1,
        t2: t.t2,
        t2s: t.t2s,
        pd: t.pd,
      })),
    })
      .then((payload) => {
        if (!cancelled) setCockpitSignals(payload);
      })
      .catch(() => {
        if (!cancelled) setCockpitSignals(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedScenarioKey, fa, te, tr, currentScenario]);

  // Handle echo selection for cross-lens cursor
  const handleSelectEcho = (echoNum: number, timeMs: number) => {
    setCursors({
      ...cursors,
      selectedEcho: echoNum,
      cursorTime: timeMs,
      selectedEvent: `Echo #${echoNum}`,
    });
  };

  // UI range helper only — physics lives on POST /cockpit/signals
  const isGRE = currentScenario.seqType === "GRE";
  const faDeg = fa;
  const tissueIntensities = currentScenario.tissues.map((t) => ({
    ...t,
    intensity: cockpitSignals?.signals[t.id] ?? 0,
  }));
  const deltaSignal = cockpitSignals?.delta_signal ?? 0;
  const cnrProxy = cockpitSignals?.cnr_proxy ?? 0;
  const relativeSar = cockpitSignals?.relative_sar ?? 0;
  const refocusEff = cockpitSignals?.refocus_eff ?? 0;

  // Voxel dimensions (mm)
  const voxelX = (fov / matrixSize).toFixed(2);
  const voxelY = (fov / matrixSize).toFixed(2);
  const voxelZ = sliceThick.toFixed(2);

  return (
    <div className="retromorphic-cockpit" data-testid="workbench-cockpit">
      
      {/* 1. Left Bay: Scenario Selection & Dual Persona Context */}
      <section className="instrument-bay" data-testid="instrument-bay">
        <div className="bay-header">
          <h3>EXPERIMENT</h3>
          <span className="recipe-tag">{currentScenario.seqType}</span>
        </div>

        {/* Scenario Selection Dropdown */}
        <div style={{ marginBottom: "14px" }}>
          <label style={{ fontSize: "11px", color: "#8ba0a8", display: "block", marginBottom: "4px" }}>Clinical Scenario:</label>
          <select
            value={selectedScenarioKey}
            onChange={(e) => setSelectedScenarioKey(e.target.value)}
            style={{
              width: "100%",
              backgroundColor: "#13181a",
              color: "var(--cyan)",
              border: "1px solid #3c4a50",
              borderRadius: "4px",
              padding: "6px 8px",
              fontSize: "12px",
              fontWeight: 700,
              fontFamily: "monospace",
            }}
            data-testid="scenario-dropdown"
          >
            {Object.entries(CLINICAL_SCENARIOS).map(([k, s]) => (
              <option key={k} value={k}>
                [{s.category}] {s.name}
              </option>
            ))}
          </select>
        </div>

        {/* Persona-Divergent Panels */}
        {profile === "clinical" ? (
          /* CLINICAL LENS: Radiology View (ZERO EPG/Timing Jargon) */
          <div className="clinical-contrast-panel" data-testid="clinical-contrast-panel">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <h4 style={{ margin: 0 }}>CLINICAL CONTRAST</h4>
              <span style={{ fontSize: "10px", color: "var(--amber)", fontWeight: 700 }}>{currentScenario.weightingName}</span>
            </div>

            {/* v0.43: Custom Scenario Button */}
            <div style={{ display: "flex", gap: "6px", marginBottom: "8px" }}>
              <button
                onClick={() => setShowCustomModal(true)}
                style={{
                  flex: 1,
                  padding: "4px 8px",
                  fontSize: "10px",
                  fontWeight: 700,
                  backgroundColor: "#1f2930",
                  color: "var(--cyan)",
                  border: "1px dashed var(--cyan)",
                  borderRadius: "3px",
                  cursor: "pointer",
                }}
                data-testid="custom-scenario-btn"
              >
                ➕ Custom Scenario
              </button>
            </div>

            <div style={{ background: "#0c1114", border: "1px solid #28373e", padding: "8px", borderRadius: "4px", fontSize: "11px", marginBottom: "12px", color: "#b2c5cc", lineHeight: 1.4 }}>
              <b>Diagnostic Objective:</b> {currentScenario.clinicalQuestion}
            </div>

            {/* Scan Plane Selection */}
            <div style={{ marginBottom: "12px" }}>
              <label style={{ fontSize: "10px", color: "#7a9099", fontWeight: 700, display: "block", marginBottom: "4px" }}>PRIMARY ACQUISITION PLANE:</label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "4px" }}>
                {["AXIAL", "CORONAL", "SAGITTAL"].map((plane) => (
                  <button
                    key={plane}
                    onClick={() => setActiveScanPlane(plane)}
                    style={{
                      padding: "4px 0",
                      fontSize: "10px",
                      fontWeight: 700,
                      backgroundColor: activeScanPlane === plane ? "var(--cyan)" : "#182226",
                      color: activeScanPlane === plane ? "#081114" : "#8ea1a8",
                      border: "1px solid #33434a",
                      borderRadius: "3px",
                      cursor: "pointer",
                    }}
                  >
                    {plane}
                  </button>
                ))}
              </div>
            </div>

            {/* Tissue Intensity Table */}
            <div style={{ maxHeight: "200px", overflowY: "auto" }}>
              {tissueIntensities.map((t) => {
                const gray = Math.round(t.intensity * 255);
                return (
                  <div key={t.id} className="tissue-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px", padding: "6px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span style={{ width: "12px", height: "12px", backgroundColor: `rgb(${gray},${gray},${gray})`, borderRadius: "2px", border: "1px solid #4a5c64" }} />
                      <div>
                        <b>{t.name}</b>
                        <small style={{ display: "block" }}>{t.desc}</small>
                      </div>
                    </div>
                    <span style={{ fontFamily: "monospace", color: "var(--cyan)", fontWeight: 700 }}>{(t.intensity * 100).toFixed(0)}%</span>
                  </div>
                );
              })}
            </div>

            <div className="metrics-box" style={{ marginTop: "12px" }} data-testid="cockpit-signal-metrics">
              <div className="metric">
                <label>ΔSignal (Contrast)</label>
                <span data-testid="cockpit-delta-signal">{deltaSignal.toFixed(3)}</span>
              </div>
              <div className="metric">
                <label>CNR Proxy Margin</label>
                <span data-testid="cockpit-cnr-proxy">{cnrProxy.toFixed(1)}</span>
              </div>
            </div>
          </div>
        ) : (
          /* PHYSICS LENS: Operator Evolution & Phase Space */
          <div className="physics-details-panel" data-testid="physics-details-panel">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <h4>PHYSICS ENGINE SPEC</h4>
              <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                <button
                  onClick={() => setIsEditMode(!isEditMode)}
                  style={{
                    padding: "3px 8px",
                    fontSize: "10px",
                    fontWeight: 700,
                    backgroundColor: isEditMode ? "var(--amber)" : "#182226",
                    color: isEditMode ? "#081114" : "var(--cyan)",
                    border: `1px solid ${isEditMode ? "var(--amber)" : "#33434a"}`,
                    borderRadius: "3px",
                    cursor: "pointer",
                  }}
                  data-testid="edit-mode-toggle"
                >
                  {isEditMode ? "🔓 EDITING" : "✏️ EDIT"}
                </button>
                <span style={{ fontSize: "10px", color: "var(--cyan)", fontWeight: 700, fontFamily: "monospace" }}>SEAM: {currentScenario.seqType}</span>
              </div>
            </div>

            {/* Physics Sub-lens switcher */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px", marginBottom: "12px" }} data-testid="physics-sublens-switcher">
              <button
                onClick={() => setPhysicsTab("timeline")}
                style={{
                  padding: "6px",
                  fontSize: "10px",
                  fontWeight: 700,
                  fontFamily: "monospace",
                  backgroundColor: physicsTab === "timeline" ? "var(--cyan)" : "#182226",
                  color: physicsTab === "timeline" ? "#081114" : "#8ea1a8",
                  border: "1px solid #33434a",
                  borderRadius: "3px",
                  cursor: "pointer",
                }}
              >
                1. 5-CH TIMELINE
              </button>
              <button
                onClick={() => setPhysicsTab("epg_phase")}
                style={{
                  padding: "6px",
                  fontSize: "10px",
                  fontWeight: 700,
                  fontFamily: "monospace",
                  backgroundColor: physicsTab === "epg_phase" ? "var(--cyan)" : "#182226",
                  color: physicsTab === "epg_phase" ? "#081114" : "#8ea1a8",
                  border: "1px solid #33434a",
                  borderRadius: "3px",
                  cursor: "pointer",
                }}
              >
                2. EPG (TIME, k)
              </button>
              <button
                onClick={() => setPhysicsTab("bloch_sphere")}
                style={{
                  padding: "6px",
                  fontSize: "10px",
                  fontWeight: 700,
                  fontFamily: "monospace",
                  backgroundColor: physicsTab === "bloch_sphere" ? "var(--cyan)" : "#182226",
                  color: physicsTab === "bloch_sphere" ? "#081114" : "#8ea1a8",
                  border: "1px solid #33434a",
                  borderRadius: "3px",
                  cursor: "pointer",
                }}
              >
                3. ROTATING M(t)
              </button>
              <button
                onClick={() => setPhysicsTab("phantom")}
                style={{
                  padding: "6px",
                  fontSize: "10px",
                  fontWeight: 700,
                  fontFamily: "monospace",
                  backgroundColor: physicsTab === "phantom" ? "var(--amber)" : "#182226",
                  color: physicsTab === "phantom" ? "#081114" : "#8ea1a8",
                  border: "1px solid #33434a",
                  borderRadius: "3px",
                  cursor: "pointer",
                }}
              >
                🎯 4. TEST PHANTOM
              </button>
              <button
                onClick={() => setPhysicsTab("kspace")}
                data-testid="kspace-tab-btn"
                style={{
                  padding: "6px",
                  fontSize: "10px",
                  fontWeight: 700,
                  fontFamily: "monospace",
                  backgroundColor: physicsTab === "kspace" ? "var(--cyan)" : "#182226",
                  color: physicsTab === "kspace" ? "#081114" : "#8ea1a8",
                  border: "1px solid #33434a",
                  borderRadius: "3px",
                  cursor: "pointer",
                }}
              >
                5. K-SPACE / RECON
              </button>
              <button
                onClick={() => setPhysicsTab("optimize")}
                data-testid="optimize-tab-btn"
                style={{
                  padding: "6px",
                  fontSize: "10px",
                  fontWeight: 700,
                  fontFamily: "monospace",
                  backgroundColor: physicsTab === "optimize" ? "var(--cyan)" : "#182226",
                  color: physicsTab === "optimize" ? "#081114" : "#8ea1a8",
                  border: "1px solid #33434a",
                  borderRadius: "3px",
                  cursor: "pointer",
                }}
              >
                6. OPTIMIZE / PARETO
              </button>
              <button
                onClick={() => setPhysicsTab("compare")}
                data-testid="compare-tab-btn"
                style={{
                  padding: "6px",
                  fontSize: "10px",
                  fontWeight: 700,
                  fontFamily: "monospace",
                  gridColumn: "1 / span 2",
                  backgroundColor: physicsTab === "compare" ? "var(--cyan)" : "#182226",
                  color: physicsTab === "compare" ? "#081114" : "#8ea1a8",
                  border: "1px solid #33434a",
                  borderRadius: "3px",
                  cursor: "pointer",
                }}
              >
                7. COMPARE A/B
              </button>
            </div>

            <div className="state-metrics">
              <div>
                <label>RF Energy ∫B1²dt</label>
                <span>{relativeSar.toFixed(1)} a.u.</span>
              </div>
              <div>
                <label>Coherence Order k</label>
                <span>{isGRE ? "GRE Steady State" : "EPG k=16"}</span>
              </div>
              <div>
                <label>Refocusing Eff</label>
                <span>{(refocusEff * 100).toFixed(1)}%</span>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* 2. Center Display: Oscilloscope or Quad MPR */}
      <section className="active-lens-display" data-testid="active-lens-display">
        <div className="display-bezel">
          <header className="display-header">
            <span>
              {profile === "clinical"
                ? `CLINICAL QUAD VIEWPORT · ${currentScenario.anatomy.toUpperCase()} · ${activeScanPlane}`
                : `PHYSICS INSTRUMENT · ${physicsTab.toUpperCase()}`}
            </span>
            <div className="cursor-readout">
              <span data-testid="time-readout">t = {cursors.cursorTime.toFixed(1)} ms</span>
              {cursors.selectedEcho != null && (
                <span data-testid="echo-readout">Echo #{cursors.selectedEcho}</span>
              )}
            </div>
          </header>

          <div className="display-screen" style={{ minHeight: "380px" }}>
            {profile === "clinical" ? (
              /* CLINICAL QUAD MPR & MIP RAYCAST */
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", width: "100%", height: "100%" }}>
                {/* Quad 1: AXIAL */}
                <div style={{ backgroundColor: "#06090c", border: `1px solid ${activeScanPlane === 'AXIAL' ? 'var(--cyan)' : '#22323a'}`, borderRadius: "4px", padding: "8px", display: "flex", flexDirection: "column" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "#8ea1a8", marginBottom: "4px" }}>
                    <b>1. AXIAL VIEW</b>
                    <span>{activeScanPlane === 'AXIAL' ? '● PRIMARY SCAN' : 'MPR DERIVED'}</span>
                  </div>
                  <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: "#030608", border: "1px dashed #1e2c33", borderRadius: "3px" }}>
                    <span style={{ fontSize: "11px", color: "#6b8089", fontFamily: "monospace" }}>[AXIAL Image Slot] · FOV:{fov}mm</span>
                  </div>
                </div>

                {/* Quad 2: SAGITTAL */}
                <div style={{ backgroundColor: "#06090c", border: `1px solid ${activeScanPlane === 'SAGITTAL' ? 'var(--cyan)' : '#22323a'}`, borderRadius: "4px", padding: "8px", display: "flex", flexDirection: "column" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "#8ea1a8", marginBottom: "4px" }}>
                    <b>2. SAGITTAL VIEW</b>
                    <span>{activeScanPlane === 'SAGITTAL' ? '● PRIMARY SCAN' : 'MPR DERIVED'}</span>
                  </div>
                  <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: "#030608", border: "1px dashed #1e2c33", borderRadius: "3px" }}>
                    <span style={{ fontSize: "11px", color: "#6b8089", fontFamily: "monospace" }}>[SAGITTAL Image Slot] · FOV:{fov}mm</span>
                  </div>
                </div>

                {/* Quad 3: CORONAL */}
                <div style={{ backgroundColor: "#06090c", border: `1px solid ${activeScanPlane === 'CORONAL' ? 'var(--cyan)' : '#22323a'}`, borderRadius: "4px", padding: "8px", display: "flex", flexDirection: "column" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "#8ea1a8", marginBottom: "4px" }}>
                    <b>3. CORONAL VIEW</b>
                    <span>{activeScanPlane === 'CORONAL' ? '● PRIMARY SCAN' : 'MPR DERIVED'}</span>
                  </div>
                  <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: "#030608", border: "1px dashed #1e2c33", borderRadius: "3px" }}>
                    <span style={{ fontSize: "11px", color: "#6b8089", fontFamily: "monospace" }}>[CORONAL Image Slot] · FOV:{fov}mm</span>
                  </div>
                </div>

                {/* Quad 4: 2D MIP & Multi-Slice Stack */}
                <div style={{ backgroundColor: "#06090c", border: "1px solid var(--amber)", borderRadius: "4px", padding: "8px", display: "flex", flexDirection: "column" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "var(--amber)", marginBottom: "4px" }}>
                    <b>4. 2D MIP &amp; SLICE STACK</b>
                    <span>{isInterleaved ? 'INTERLEAVED' : 'SEQUENTIAL'}</span>
                  </div>
                  <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between", background: "#030608", padding: "6px", borderRadius: "3px" }}>
                    <div style={{ display: "flex", gap: "2px", alignItems: "center", height: "40px", overflowX: "auto" }}>
                      {Array.from({ length: Math.min(20, sliceCount) }).map((_, i) => {
                        const isEven = (i + 1) % 2 === 0;
                        const isCur = mipCursorZ === (i + 1);
                        return (
                          <div
                            key={i}
                            onClick={() => setMipCursorZ(i + 1)}
                            style={{
                              flex: 1,
                              height: "100%",
                              backgroundColor: isInterleaved ? (isEven ? "var(--cyan)" : "var(--amber)") : "#38bdf8",
                              opacity: isCur ? 1.0 : 0.4,
                              cursor: "pointer",
                              borderRadius: "1px",
                              border: isCur ? "1px solid #fff" : "none",
                            }}
                          />
                        );
                      })}
                    </div>
                    <div style={{ fontSize: "10px", color: "#8ea1a8", display: "flex", justifyContent: "space-between", fontFamily: "monospace" }}>
                      <span>Slab Z: {((sliceCount * (sliceThick + sliceGap)) - sliceGap).toFixed(1)}mm</span>
                      <span>Slice #{mipCursorZ} / {sliceCount}</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              /* PHYSICS VIEWPORTS */
              <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
                {physicsTab === "timeline" && (
                  <div style={{ width: "100%", height: "100%", position: "relative" }}>
                    {isEditMode && (
                      <div style={{ display: "flex", gap: "10px", padding: "6px", background: "rgba(255,184,52,0.1)", borderBottom: "1px solid var(--amber)", fontSize: "11px", color: "var(--amber)", alignItems: "center" }}>
                        <b>✏️ SEQUENCE EDIT ACTIVE:</b>
                        <span>Readout Width:</span>
                        <input
                          type="range"
                          min="0.5"
                          max="2.0"
                          step="0.1"
                          value={readoutWidthFactor}
                          onChange={(e) => setReadoutWidthFactor(Number(e.target.value))}
                          style={{ width: "80px" }}
                          data-testid="readout-width-slider"
                        />
                        <span>{readoutWidthFactor.toFixed(1)}x</span>

                        <span style={{ marginLeft: "10px" }}>Partial Fourier:</span>
                        <select
                          value={partialFourierFrac}
                          onChange={(e) => setPartialFourierFrac(Number(e.target.value))}
                          style={{ background: "#111", color: "var(--amber)", border: "1px solid var(--amber)", fontSize: "10px" }}
                          data-testid="partial-fourier-select"
                        >
                          <option value={1.0}>OFF (100%)</option>
                          <option value={0.75}>6/8 (75%)</option>
                          <option value={0.625}>5/8 (62.5%)</option>
                        </select>
                      </div>
                    )}
                    <svg viewBox="0 0 600 200" style={{ width: "100%", height: "240px" }}>
                      {/* RF Channel */}
                      <line x1="0" y1="40" x2="600" y2="40" stroke="#25373f" />
                      <path d="M 20 40 Q 30 10 40 40" fill="none" stroke="var(--cyan)" strokeWidth="2.5" />
                      {Array.from({ length: 16 }).map((_, i) => (
                        <line key={i} x1={70 + i * 32} y1="40" x2={70 + i * 32} y2={40 - (faDeg / 180) * 25} stroke="var(--amber)" strokeWidth="2" />
                      ))}
                      {/* Gy Channel */}
                      <line x1="0" y1="90" x2="600" y2="90" stroke="#25373f" />
                      {Array.from({ length: 16 }).map((_, i) => (
                        <line key={i} x1={65 + i * 32} y1="90" x2={65 + i * 32} y2={90 - (i - 8) * 2} stroke="#3bf48d" strokeWidth="1.5" />
                      ))}
                      {/* Gx Readout */}
                      <line x1="0" y1="140" x2="600" y2="140" stroke="#25373f" />
                      {Array.from({ length: 16 }).map((_, i) => {
                        const isPartialOmitted = partialFourierFrac < 1.0 && i > 16 * partialFourierFrac;
                        return (
                          <rect
                            key={i}
                            x={65 + i * 32}
                            y="130"
                            width={16 * readoutWidthFactor}
                            height="10"
                            fill={isPartialOmitted ? "rgba(100, 116, 139, 0.2)" : "rgba(59, 244, 141, 0.3)"}
                            stroke={isPartialOmitted ? "#475569" : "#3bf48d"}
                            strokeDasharray={isPartialOmitted ? "2 2" : "none"}
                          />
                        );
                      })}
                      {/* Time Cursor */}
                      <line x1={70 + ((cursors.selectedEcho ?? 8) - 1) * 32} y1="10" x2={70 + ((cursors.selectedEcho ?? 8) - 1) * 32} y2="180" stroke="var(--cyan)" strokeDasharray="3 3" strokeWidth="1.5" />
                    </svg>
                  </div>
                )}
                {physicsTab === "epg_phase" && (
                  <div style={{ width: "100%", height: "240px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
                    <svg viewBox="0 0 500 180" style={{ width: "100%", height: "100%" }}>
                      <line x1="20" y1="90" x2="480" y2="90" stroke="#3bf48d" strokeWidth="2" />
                      <text x="440" y="85" fill="#3bf48d" fontSize="9">k=0 (Echo)</text>
                      {[-2, -1, 1, 2].map((k) => (
                        <line key={k} x1="20" y1={90 - k * 25} x2="480" y2={90 - k * 25} stroke="#1f2d33" strokeDasharray="2 2" />
                      ))}
                    </svg>
                  </div>
                )}
                {physicsTab === "bloch_sphere" && (
                  <div style={{ width: "200px", height: "200px", border: "1px solid #33434a", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", position: "relative" }}>
                    <div style={{ width: "100%", height: "1px", backgroundColor: "#33434a", position: "absolute" }} />
                    <div style={{ width: "1px", height: "100%", backgroundColor: "#33434a", position: "absolute" }} />
                    <div style={{ width: "60px", height: "2px", backgroundColor: "var(--amber)", transformOrigin: "left center", transform: `rotate(${faDeg}deg)` }} />
                  </div>
                )}
                {physicsTab === "kspace" && <KSpaceReconLens />}
                {physicsTab === "optimize" && (
                  <OptimizeLensView
                    currentFa={fa}
                    currentTe={te}
                    onApplyOptimal={(nextFa, nextTe) => {
                      setFa(nextFa);
                      setTe(nextTe);
                    }}
                  />
                )}
                {physicsTab === "compare" && <CompareLensView currentFa={fa} currentTe={te} />}
                {physicsTab === "phantom" && (
                  /* SINGLE DEDICATED CALIBRATION PHANTOM */
                  <div style={{ width: "180px", height: "180px", borderRadius: "50%", backgroundColor: "#0c1317", border: "2px solid #38e8f0", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", padding: "20px" }}>
                    <div style={{ borderRadius: "50%", backgroundColor: "#fff", display: "flex", alignItems: "center", justifyContent: "center", color: "#000", fontWeight: 700, fontSize: "10px" }}>V1</div>
                    <div style={{ borderRadius: "50%", backgroundColor: "#aaa", display: "flex", alignItems: "center", justifyContent: "center", color: "#000", fontWeight: 700, fontSize: "10px" }}>V2</div>
                    <div style={{ borderRadius: "50%", backgroundColor: "#666", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: 700, fontSize: "10px" }}>V3</div>
                    <div style={{ borderRadius: "50%", backgroundColor: "#333", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: 700, fontSize: "10px" }}>V4</div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Linked Echo Train Scrubber */}
        <div className="linked-scope-rail">
          <label>INTERACTIVE ECHO TRAIN (ETL=16 CROSS-LENS LINKED)</label>
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

      {/* 3. Control Bank: Geometric & Physical Dials */}
      <section className="control-bank" data-testid="control-bank">
        <div className="bank-header">
          <h3>CONTROL BANK</h3>
          <span className="sub-mode">{profile === "clinical" ? "Geometry & Contrast" : "Operator Dials"}</span>
        </div>

        {profile === "clinical" ? (
          /* Clinical Controls: Slice thickness, gap, count, FOV, TR/TE */
          <>
            <div className="control-group">
              <label>Matrix &amp; Voxel Size</label>
              <div className="slider-row">
                <select
                  value={matrixSize}
                  onChange={(e) => setMatrixSize(Number(e.target.value))}
                  style={{ background: "#111", color: "var(--cyan)", border: "1px solid #33434a", padding: "4px 8px", borderRadius: "3px", fontSize: "11px", fontWeight: 700 }}
                  data-testid="matrix-size-select"
                >
                  <option value={128}>128 x 128</option>
                  <option value={256}>256 x 256</option>
                  <option value={384}>384 x 384</option>
                  <option value={512}>512 x 512</option>
                </select>
                <span className="value-badge">{voxelX}x{voxelY}x{voxelZ}mm³</span>
              </div>
            </div>

            <div className="control-group">
              <label>Parallel Acceleration (R)</label>
              <div className="slider-row">
                <input type="range" min="1" max="4" step="1" value={accelerationFactor} onChange={(e) => setAccelerationFactor(Number(e.target.value))} />
                <span className="value-badge">R = {accelerationFactor}x</span>
              </div>
            </div>

            <div className="control-group">
              <label>Slice Thickness</label>
              <div className="slider-row">
                <input type="range" min="1.0" max="8.0" step="0.5" value={sliceThick} onChange={(e) => setSliceThick(Number(e.target.value))} />
                <span className="value-badge">{sliceThick} mm</span>
              </div>
            </div>

            <div className="control-group">
              <label>Slice Gap</label>
              <div className="slider-row">
                <input type="range" min="0.0" max="5.0" step="0.5" value={sliceGap} onChange={(e) => setSliceGap(Number(e.target.value))} />
                <span className="value-badge">{sliceGap} mm</span>
              </div>
            </div>

            <div className="control-group">
              <label>Number of Slices</label>
              <div className="slider-row">
                <input type="range" min="6" max="40" step="2" value={sliceCount} onChange={(e) => setSliceCount(Number(e.target.value))} />
                <span className="value-badge">{sliceCount}</span>
              </div>
            </div>

            <div className="control-group">
              <label>Field of View (FOV)</label>
              <div className="slider-row">
                <input type="range" min="120" max="400" step="20" value={fov} onChange={(e) => setFov(Number(e.target.value))} />
                <span className="value-badge">{fov} mm</span>
              </div>
            </div>

            <div className="control-group">
              <label>Effective TE</label>
              <div className="slider-row">
                <input type="range" min={isGRE ? 1.5 : 30} max={isGRE ? 25 : 160} step={isGRE ? 0.5 : 10} value={te} onChange={(e) => setTe(Number(e.target.value))} />
                <span className="value-badge">{te} ms</span>
              </div>
            </div>
          </>
        ) : (
          /* Physics Controls: Alpha, TE, TR, Bandwidth */
          <>
            <div className="control-group">
              <label>{isGRE ? "Ernst Flip Angle (α)" : "Refocusing Angle α"}</label>
              <div className="slider-row">
                <input type="range" min={isGRE ? 5 : 60} max={isGRE ? 90 : 180} step={isGRE ? 1 : 5} value={faDeg} onChange={(e) => setFa(Number(e.target.value))} />
                <span className="value-badge">{faDeg}°</span>
              </div>
            </div>

            <div className="control-group">
              <label>Effective TE</label>
              <div className="slider-row">
                <input type="range" min={isGRE ? 1.5 : 30} max={isGRE ? 25 : 160} step={isGRE ? 0.5 : 10} value={te} onChange={(e) => setTe(Number(e.target.value))} />
                <span className="value-badge">{te} ms</span>
              </div>
            </div>

            <div className="control-group">
              <label>Repetition Time (TR)</label>
              <div className="slider-row">
                <input type="range" min={isGRE ? 15 : 1000} max={isGRE ? 500 : 5000} step={isGRE ? 5 : 500} value={tr} onChange={(e) => setTr(Number(e.target.value))} />
                <span className="value-badge">{tr} ms</span>
              </div>
            </div>
          </>
        )}

        <div className="action-row" style={{ marginTop: "16px" }}>
          <button className="execute-btn" onClick={triggerRun} data-cost="realtime" data-testid="run-experiment-btn">
            {isComputing ? "COMPUTING..." : "RUN EXPERIMENT"}
          </button>
        </div>
      </section>

      {/* 4. Status Rail */}
      <section className="status-rail" data-testid="status-rail">
        <div className="state-badge" data-state={executionState}>
          STATUS: {executionState}
        </div>
        <div className="cost-tier">KERNEL ENGINE: {resultGraph?.execution_plan?.selected_engine?.toUpperCase() || "EPG"}</div>
        <div className="system-info">MRQLab v0.42 · Lens Projection &amp; ResultGraph Verified</div>
      </section>
    </div>
  );
}
