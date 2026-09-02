"use client";

import React, { useState, useEffect, useRef } from "react";
import { useWorkspace } from "../workspace/WorkspaceProvider";
import { CLINICAL_SCENARIOS, isSpectrumScenario, ScenarioSpec } from "../../lib/scenarios";
import { isCestSpectrumRecipe, scenarioKeyForRecipe } from "../../lib/explore-catalog";
import { ResultGraph } from "../../lib/workbench-types";
import { CockpitSignalAnalysis, fetchCockpitSignals, listClinicalRecipes, runExperimentFromRecipe, saveCustomRecipe, buildSequence, patchSequence, fetchComposeSequence, SequenceBlock, SequenceBlockKind } from "../../lib/api";
import { KSpaceReconLens } from "./KSpaceReconLens";
import { OptimizeLensView } from "./OptimizeLensView";
import { CompareLensView } from "./CompareLensView";
import { PulseInspector } from "./PulseInspector";
import { SlabStackView } from "./SlabStackView";
import { SequenceIRTimeline } from "./SequenceIRTimeline";
import { SequenceIR } from "../../lib/sequence-ir";
import { GradientEventEditor } from "./GradientEventEditor";
import { SequenceLego } from "./SequenceLego";

type TimelineSelection = { channel: string; time: number; value: number; index: number };

function cestKnobsFromMetadata(cest: Record<string, unknown> | undefined) {
  if (!cest) return null;
  const power = Number(cest.saturation_power_uT);
  const span = Number(cest.offset_span_ppm);
  const duty = Number(cest.duty_cycle);
  const mode = typeof cest.mode === "string" ? cest.mode : undefined;
  return {
    power: Number.isFinite(power) ? power : undefined,
    span: Number.isFinite(span) ? span : undefined,
    duty: Number.isFinite(duty) ? duty : undefined,
    mode,
  };
}

function SpectrumPlot({ resultGraph }: { resultGraph: ResultGraph | null }) {
  const spectrum = resultGraph?.observations.find((item) => item.kind === "z_spectrum");
  const asym = resultGraph?.observations.find((item) => item.kind === "mtr_asym");
  if (!spectrum) return <div data-testid="spectrum-awaiting">awaiting z_spectrum from RUN</div>;
  const x = spectrum.data.offset_ppm as number[];
  const z = spectrum.data.Z as number[];
  const min = Math.min(...x), max = Math.max(...x), span = max - min || 1;
  const points = x.map((value, i) => `${20 + 360 * (value - min) / span},${190 - 160 * z[i]}`).join(" ");
  const ax = (asym?.data.offset_ppm || []) as number[];
  const ay = (asym?.data.MTR_asym || []) as number[];
  const mtrMax = Math.max(0.01, ...ay.map(Math.abs));
  const aMin = ax.length ? Math.min(...ax) : min;
  const aMax = ax.length ? Math.max(...ax) : max;
  const aSpan = aMax - aMin || 1;
  const asymPoints = ax.map((value, i) => `${20 + 360 * (value - aMin) / aSpan},${190 - 80 * (1 + ay[i] / mtrMax)}`).join(" ");
  const axis = (xMin: number, xMax: number, y1: number, y2: number) => xMin < 0 && xMax > 0
    ? <line x1={20 + 360 * (0 - xMin) / (xMax - xMin || 1)} x2={20 + 360 * (0 - xMin) / (xMax - xMin || 1)} y1={y1} y2={y2} stroke="#60747c" />
    : null;
  const ppmTicks = (
    <div data-testid="spectrum-z-axis" style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "#8ba0a8" }}>
      <span>{min}</span><span>0 ppm</span><span>{max}</span>
    </div>
  );
  return <figure data-testid="spectrum-plot">
    <div data-testid="spectrum-engine-boundary" style={{ fontSize: "11px", color: "#8ba0a8", marginBottom: "6px" }}>
      CEST · pool model + Bloch–McConnell + EPG-X · not MRS / COSY density-matrix
    </div>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
      <div data-testid="spectrum-z-panel">
        <div style={{ fontSize: "10px", color: "var(--cyan)", fontWeight: 800, letterSpacing: "0.08em" }}>Z(Δ)</div>
        <svg viewBox="0 0 400 220" role="img" aria-label="Backend RUN Z spectrum">
          {axis(min, max, 20, 195)}
          <polyline points={points} fill="none" stroke="var(--cyan)" strokeWidth="3" />
        </svg>
        {ppmTicks}
      </div>
      <div data-testid="spectrum-mtr-panel">
        <div style={{ fontSize: "10px", color: "var(--amber)", fontWeight: 800, letterSpacing: "0.08em" }}>MTR_asym</div>
        <svg viewBox="0 0 400 220" role="img" aria-label="Backend RUN MTR asymmetry">
          {axis(aMin, aMax, 20, 195)}
          {asymPoints && <polyline points={asymPoints} fill="none" stroke="var(--amber)" strokeWidth="2" />}
        </svg>
        <div data-testid="spectrum-mtr-scale" style={{ fontSize: "10px", color: "#8ba0a8" }}>±{mtrMax}</div>
        <div data-testid="spectrum-mtr-axis" style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "#8ba0a8" }}>
          <span>{aMin}</span><span>ppm</span><span>{aMax}</span>
        </div>
      </div>
    </div>
    <figcaption>RUN backend arrays · {spectrum.provenance?.engine} · {spectrum.provenance?.assumptions?.join(" · ")} · {spectrum.data.normalization}</figcaption>
    {spectrum.data.mode && <div data-testid="spectrum-mode">{String(spectrum.data.mode)} · duty cycle {Number(spectrum.data.duty_cycle).toFixed(3)}</div>}
  </figure>;
}

export function WorkbenchCockpit({ initialRecipeId }: { initialRecipeId?: string } = {}) {
  const { profile, activeLens, setActiveLens, cursors, setCursors, executionState, setExecutionState } = useWorkspace();
  
  const [selectedScenarioKey, setSelectedScenarioKey] = useState<string>(() => scenarioKeyForRecipe(initialRecipeId));
  const currentScenario: ScenarioSpec = CLINICAL_SCENARIOS[selectedScenarioKey] || CLINICAL_SCENARIOS.ms_brain;
  const isSpectrumExperiment = isSpectrumScenario(currentScenario);
  const activeRecipeId = isSpectrumExperiment && isCestSpectrumRecipe(initialRecipeId) ? initialRecipeId : currentScenario.recipeId;
  const clinicalScenarioEntries = Object.entries(CLINICAL_SCENARIOS).filter(([, s]) => !isSpectrumScenario(s));

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
  const imagingDefaults = currentScenario.defaultParams;
  const [fa, setFa] = useState<number>(imagingDefaults?.fa ?? 90);
  const [exciteFa, setExciteFa] = useState<number>(currentScenario.seqType === "GRE" ? (imagingDefaults?.fa ?? 90) : 90);
  const [adcBwHz, setAdcBwHz] = useState<number>(62500);
  const [te, setTe] = useState<number>(imagingDefaults?.te ?? 0);
  const [tr, setTr] = useState<number>(imagingDefaults?.tr ?? 0);
  const [compiledSequence, setCompiledSequence] = useState<SequenceIR | null>(null);
  const [timelineSelection, setTimelineSelection] = useState<TimelineSelection | null>(null);
  const [blocks, setBlocks] = useState<SequenceBlock[]>([]);
  const [selectedBlockId, setSelectedBlockId] = useState<string>();
  const composeRequestId = useRef(0);

  const compileBlocks = async (nextBlocks: SequenceBlock[]) => {
    const requestId = ++composeRequestId.current;
    try {
      const ir = await fetchComposeSequence({ name: "Lego sequence", blocks: nextBlocks });
      if (requestId !== composeRequestId.current) return;
      setBlocks(nextBlocks);
      setCompiledSequence(ir);
      setExecutionState?.("READY");
      setRunError(null);
    } catch (reason) {
      if (requestId !== composeRequestId.current) return;
      setExecutionState?.("ERROR");
      setRunError(reason instanceof Error ? reason.message : String(reason));
    }
  };

  const placeBlock = (kind: SequenceBlockKind, t0_s?: number) => {
    const id = `${kind}-${blocks.length + 1}`;
    const params: Record<string, number | string> = kind.endsWith("sinc")
      ? { duration_s: 0.001, time_bandwidth: 4, flip_angle_deg: kind === "excite_sinc" ? 90 : 180, phase_deg: 0 }
      : kind.startsWith("trap_")
        ? { amplitude_mt_m: 20, duration_s: 0.001, ramp_time_s: 0.0002, unit: "mT_m" }
        : { duration_s: 0.001 };
    const t0 = t0_s != null ? Math.round(t0_s * 10000) / 10000 : Math.round(blocks.length * 10) / 10000;
    void compileBlocks([...blocks, { id, kind, t0_s: t0, params }]);
    setSelectedBlockId(id);
  };
  const KIND_CHANNEL: Record<SequenceBlockKind, string> = {
    excite_sinc: "rf_amp", refocus_sinc: "rf_amp",
    trap_gx: "gx", trap_gy: "gy", trap_gz: "gz", adc_gate: "adc_gate",
  };
  const placeBlockAt = (kind: SequenceBlockKind, channel: string, t0_s: number) => {
    if (KIND_CHANNEL[kind] !== channel) return;
    placeBlock(kind, t0_s);
  };
  const [fov, setFov] = useState<number>(imagingDefaults?.fov ?? 0);
  const [sliceThick, setSliceThick] = useState<number>(imagingDefaults?.sliceThick ?? 0);
  const [sliceCount, setSliceCount] = useState<number>(imagingDefaults?.sliceCount ?? 0);
  const [sliceGap, setSliceGap] = useState<number>(imagingDefaults?.sliceGap ?? 0);
  const [isInterleaved, setIsInterleaved] = useState<boolean>(imagingDefaults?.isInterleaved ?? false);
  const [activeScanPlane, setActiveScanPlane] = useState<string>(currentScenario.scanPlane);
  const [mipCursorZ, setMipCursorZ] = useState<number>(Math.round((imagingDefaults?.sliceCount ?? 0) / 2));
  const [cestPowerUt, setCestPowerUt] = useState<number | null>(null);
  const [cestOffsetSpanPpm, setCestOffsetSpanPpm] = useState<number | null>(null);
  const [cestDutyCycle, setCestDutyCycle] = useState<number | null>(null);
  const [cestMode, setCestMode] = useState<string | null>(null);
  const [cestDirty, setCestDirty] = useState<{ power: boolean; span: boolean; duty: boolean }>({
    power: false, span: false, duty: false,
  });
  const cestDirtyRef = useRef(cestDirty);
  cestDirtyRef.current = cestDirty;
  
  // Custom uploaded DICOM / Phantom image
  const [customImageSrc, setCustomImageSrc] = useState<string | null>(null);

  // ResultGraph from Unified Backend / Model Seam
  const [resultGraph, setResultGraph] = useState<ResultGraph | null>(null);
  const [isComputing, setIsComputing] = useState<boolean>(false);
  const [runError, setRunError] = useState<string | null>(null);

  const applyEventPatch = async (patch: Record<string, number | string>) => {
    if (!compiledSequence || !timelineSelection || !["rf_amp", "gx", "gy", "gz"].includes(timelineSelection.channel)) return;
    try {
      const next = await patchSequence({
        ir: compiledSequence,
        event: { channel: timelineSelection.channel as "rf_amp" | "gx" | "gy" | "gz", index: timelineSelection.index },
        patch,
      });
      setCompiledSequence(next);
      setExecutionState?.("READY");
      setRunError(null);
    } catch (reason) {
      setExecutionState?.("ERROR");
      setRunError(reason instanceof Error ? reason.message : String(reason));
      throw reason;
    }
  };

  // v0.48: Backend-owned GRE Ernst / TSE intensities + SAR (no TS physics)
  const [cockpitSignals, setCockpitSignals] = useState<CockpitSignalAnalysis | null>(null);

  // Physics sub-lens selection inside Physics mode
  const [physicsTab, setPhysicsTab] = useState<"timeline" | "epg_phase" | "bloch_sphere" | "kspace" | "phantom" | "optimize" | "compare" | "spectrum">(isSpectrumExperiment ? "spectrum" : "timeline");

  // Sync params when scenario changes
  useEffect(() => {
    const s = CLINICAL_SCENARIOS[selectedScenarioKey] || CLINICAL_SCENARIOS.ms_brain;
    const imaging = s.defaultParams;
    setFa(imaging?.fa ?? 90);
    setExciteFa(s.seqType === "GRE" ? (imaging?.fa ?? 90) : 90);
    setTe(imaging?.te ?? 0);
    setTr(imaging?.tr ?? 0);
    setFov(imaging?.fov ?? 0);
    setSliceThick(imaging?.sliceThick ?? 0);
    setSliceCount(imaging?.sliceCount ?? 0);
    setSliceGap(imaging?.sliceGap ?? 0);
    setIsInterleaved(imaging?.isInterleaved ?? false);
    setActiveScanPlane(s.scanPlane);
    setMipCursorZ(Math.round((imaging?.sliceCount ?? 0) / 2));
    setPhysicsTab(isSpectrumScenario(s) ? "spectrum" : "timeline");
    setCestPowerUt(null);
    setCestOffsetSpanPpm(null);
    setCestDutyCycle(null);
    setCestMode(null);
    setCestDirty({ power: false, span: false, duty: false });
  }, [selectedScenarioKey]);

  useEffect(() => {
    if (!isSpectrumExperiment) return;
    let cancelled = false;
    void listClinicalRecipes().then((recipes) => {
      if (cancelled) return;
      const match = recipes.find((item) => item.id === activeRecipeId);
      const cest = (match?.experiment as { sequence?: { metadata?: { cest?: Record<string, unknown> } } } | undefined)
        ?.sequence?.metadata?.cest;
      const knobs = cestKnobsFromMetadata(cest);
      if (!knobs) return;
      const dirty = cestDirtyRef.current;
      if (knobs.power != null && !dirty.power) setCestPowerUt(knobs.power);
      if (knobs.span != null && !dirty.span) setCestOffsetSpanPpm(knobs.span);
      if (knobs.duty != null && !dirty.duty) setCestDutyCycle(knobs.duty);
      if (knobs.mode) setCestMode(knobs.mode);
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [isSpectrumExperiment, activeRecipeId]);

  // Trigger Execution Plan (POST /experiments/run-from-recipe). Fail closed: never mint RESULT.
  const triggerRun = async () => {
    setIsComputing(true);
    setRunError(null);
    setResultGraph(null);
    setExecutionState?.("RUNNING");

    const isCestRecipe = isSpectrumExperiment;
    const params: Record<string, number> = isCestRecipe
      ? {
          ...(cestDirty.power && cestPowerUt != null ? { saturation_power_uT: cestPowerUt } : {}),
          ...(cestDirty.span && cestOffsetSpanPpm != null ? { offset_span_ppm: cestOffsetSpanPpm } : {}),
          ...(cestDirty.duty && cestDutyCycle != null && cestMode === "pulsed" ? { duty_cycle: cestDutyCycle } : {}),
        }
      : {
          te: te / 1000.0,
          tr: tr / 1000.0,
          flip_angle: exciteFa,
          ...(currentScenario.seqType === "GRE" ? {} : { refocusing_flip_angle: fa, echo_count: 16 }),
        };

    try {
      const tseProducts = ["signal", "echo_train", "configurations"];
      const res = await runExperimentFromRecipe(activeRecipeId, params, isCestRecipe
        ? { products: ["z_spectrum", "mtr_asym"] }
        : currentScenario.seqType === "GRE"
        ? { products: ["signal", "echo_train"] }
        : { products: tseProducts, engineOptions: { return_configurations: true, epg_kmax: 8 } });
      setResultGraph(res);
      setExecutionState?.("RESULT");
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setRunError(message);
      setResultGraph(null);
      setExecutionState?.("ERROR");
    } finally {
      setIsComputing(false);
    }
  };

  useEffect(() => {
    const seqType = currentScenario.seqType;
    if (isSpectrumExperiment || seqType === "CEST") {
      setCockpitSignals(null);
      return;
    }
    let cancelled = false;
    fetchCockpitSignals({
      seq_type: seqType,
      fa_deg: fa,
      te_ms: te,
      tr_ms: tr,
      echo_train_length: seqType === "GRE" ? 1 : 16,
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

  useEffect(() => {
    const template = currentScenario.seqType;
    if (isSpectrumExperiment || template === "CEST") {
      setCompiledSequence(null);
      return;
    }
    let cancelled = false;
    const params: Record<string, number> = {
      te: te / 1000.0,
      tr: tr / 1000.0,
      flip_angle: exciteFa,
    };
    if (template !== "GRE") {
      params.refocusing_flip_angle = fa;
      params.echoes = 8;
    }
    buildSequence({ template, params })
      .then((ir) => {
        if (!cancelled) setCompiledSequence(ir);
      })
      .catch(() => {
        if (!cancelled) setCompiledSequence(null);
      });
    return () => {
      cancelled = true;
    };
  }, [currentScenario.seqType, exciteFa, fa, te, tr]);

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
  const configurations = resultGraph?.observations.find((observation) => observation.kind === "configurations");
  const magnetization = resultGraph?.observations.filter((observation) => observation.kind === "magnetization").at(-1);
  const sliceProfile = resultGraph?.observations.find((observation) => observation.kind === "slice_profile");
  const phaseDistribution = resultGraph?.observations.find((observation) => observation.kind === "phase_distribution");

  const lastVector = (value: unknown): number[] | null => {
    if (!Array.isArray(value)) return null;
    if (value.length >= 3 && value.slice(-3).every((item) => typeof item === "number")) return value.slice(-3) as number[];
    for (let index = value.length - 1; index >= 0; index -= 1) {
      const found = lastVector(value[index]);
      if (found) return found;
    }
    return null;
  };
  const runVector = lastVector(magnetization?.data);

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
          <span className="recipe-tag">{isSpectrumExperiment ? "CEST" : currentScenario.seqType}</span>
        </div>

        {isSpectrumExperiment && (
          <div data-testid="spectrum-experiment-identity" style={{ marginBottom: "10px", padding: "8px", background: "#0c1114", border: "1px solid var(--amber)", borderRadius: "4px" }}>
            <div style={{ fontSize: "10px", color: "var(--amber)", fontWeight: 800, letterSpacing: "0.08em" }}>SPECTRUM EXPERIMENT</div>
            <div style={{ fontSize: "13px", color: "#e8f4f6", fontWeight: 700, marginTop: "2px" }}>
              {`${currentScenario.id === "cest_amine" ? "Amine" : "Amide"} CEST ${cestMode === "pulsed" ? "pulsed Z-spectrum" : cestMode === "cw" ? "CW Z-spectrum" : "Z-spectrum"}`}
            </div>
            <div style={{ fontSize: "11px", color: "#8ba0a8", marginTop: "4px", lineHeight: 1.4 }}>
              {cestMode === "pulsed" ? "Two-liquid-pool pulsed train" : cestMode === "cw" ? "Two-liquid-pool CW" : "Two-liquid-pool saturation"} · frequency axis · not MS plaque imaging
            </div>
          </div>
        )}

        <div style={{ marginBottom: "14px" }}>
          <label style={{ fontSize: "11px", color: "#8ba0a8", display: "block", marginBottom: "4px" }}>
            {isSpectrumExperiment ? "Switch to clinical imaging:" : "Clinical Scenario:"}
          </label>
          <select
            value={isSpectrumExperiment ? "" : selectedScenarioKey}
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
            {isSpectrumExperiment && (
              <option value="" disabled>
                Not a clinical imaging case
              </option>
            )}
            {clinicalScenarioEntries.map(([k, s]) => (
              <option key={k} value={k}>
                [{s.category}] {s.name}
              </option>
            ))}
          </select>
        </div>

        {/* Persona-Divergent Panels */}
        {profile === "clinical" && isSpectrumExperiment ? (
          <div className="clinical-contrast-panel" data-testid="spectrum-clinical-honesty">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <h4 style={{ margin: 0 }}>SPECTRUM · SINGLE VOXEL</h4>
              <span style={{ fontSize: "10px", color: "var(--amber)", fontWeight: 700 }}>Z(Δ) · no acquisition plane</span>
            </div>
            <div style={{ background: "#0c1114", border: "1px solid #28373e", padding: "8px", borderRadius: "4px", fontSize: "11px", marginBottom: "12px", color: "#b2c5cc", lineHeight: 1.4 }}>
              Frequency-axis experiment. Axial / Coronal / Sagittal planes do not apply. Water and amide pools are chemical-shift labels, not spatial tissues.
            </div>
            <div style={{ maxHeight: "200px", overflowY: "auto" }}>
              {currentScenario.tissues.map((t) => (
                <div key={t.id} className="tissue-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px", padding: "6px" }}>
                  <div>
                    <b>{t.name}</b>
                    <small style={{ display: "block" }}>{t.desc}</small>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : profile === "clinical" ? (
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
            <div style={{ marginBottom: "12px" }} data-testid="acquisition-plane-picker">
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
                <span data-testid="physics-seam" style={{ fontSize: "10px", color: "var(--cyan)", fontWeight: 700, fontFamily: "monospace" }}>SEAM: {isSpectrumExperiment ? "CEST" : currentScenario.seqType}</span>
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
              {!isSpectrumExperiment && (
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
              )}
              {!isSpectrumExperiment && (
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
              )}
              {!isSpectrumExperiment && (
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
              )}
              {!isSpectrumExperiment && (
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
              )}
              <button onClick={() => setPhysicsTab("spectrum")} data-testid="spectrum-tab-btn"
                style={{ padding: "6px", fontSize: "10px", fontWeight: 700, fontFamily: "monospace",
                  gridColumn: "1 / span 2", backgroundColor: physicsTab === "spectrum" ? "var(--cyan)" : "#182226",
                  color: physicsTab === "spectrum" ? "#081114" : "#8ea1a8", border: "1px solid #33434a", borderRadius: "3px" }}>
                8. SPECTRUM
              </button>
            </div>

            <div className="state-metrics">
              {isSpectrumExperiment ? (
                <>
                  <div>
                    <label>Observation</label>
                    <span>Z-spectrum</span>
                  </div>
                  <div>
                    <label>Coherence Order k</label>
                    <span>k=0 water</span>
                  </div>
                  <div>
                    <label>Hamiltonian</label>
                    <span data-testid="physics-hamiltonian">{cestMode === "pulsed" ? "EPG-X CEST pulsed" : cestMode === "cw" ? "EPG-X CEST CW" : "EPG-X CEST"}</span>
                  </div>
                </>
              ) : (
                <>
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
                </>
              )}
            </div>
          </div>
        )}
      </section>

      {/* 2. Center Display: Oscilloscope or Quad MPR */}
      <section className="active-lens-display" data-testid="active-lens-display">
        <div className="display-bezel">
          <header className="display-header">
            <span data-testid="display-header-title">
              {isSpectrumExperiment
                ? "SPECTRUM VIEWPORT · SINGLE VOXEL · Z(Δ)"
                : profile === "clinical"
                ? `CLINICAL QUAD VIEWPORT · ${currentScenario.anatomy.toUpperCase()} · ${activeScanPlane}`
                : `PHYSICS INSTRUMENT · ${physicsTab.toUpperCase()}`}
            </span>
            {profile === "physics" && !isSpectrumExperiment && <div style={{ display: "flex", gap: 6 }}>
              <button data-testid="inspect-rf-btn" onClick={() => {
                const rf = compiledSequence?.channels.find((channel) => channel.name === "rf_amp")?.events[0];
                setPhysicsTab("timeline");
                setTimelineSelection(rf ? { channel: "rf_amp", time: rf.time, value: rf.value, index: 0 } : { channel: "rf_amp", time: 0, value: exciteFa, index: 0 });
              }}>Inspect RF</button>
              <button data-testid="inspect-g-btn" onClick={() => {
                const channel = compiledSequence?.channels.find((candidate) => ["gx", "gy", "gz"].includes(candidate.name) && candidate.events.length);
                const event = channel?.events[0];
                setPhysicsTab("timeline");
                if (channel && event) setTimelineSelection({ channel: channel.name, time: event.time, value: event.value, index: 0 });
              }}>Inspect G</button>
            </div>}
            <div className="cursor-readout">
              <span data-testid="time-readout">t = {cursors.cursorTime.toFixed(1)} ms</span>
              {cursors.selectedEcho != null && (
                <span data-testid="echo-readout">Echo #{cursors.selectedEcho}</span>
              )}
            </div>
          </header>

          <div className={`display-screen ${profile === "clinical" ? "clinical-screen" : ""}`} style={{ minHeight: "380px" }}>
            {profile === "clinical" ? (
              isSpectrumExperiment || (resultGraph?.observations.some((o) => o.kind === "z_spectrum") && !resultGraph.observations.some((o) => ["image", "mip", "slice_stack", "parameter_map"].includes(o.kind))) ? (
                <div data-testid="clinical-rejects-z-spectrum">Clinical spatial viewport rejects z_spectrum</div>
              ) : (
              /* CLINICAL QUAD MPR & MIP RAYCAST */
              <div data-testid="clinical-quad-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gridTemplateRows: "1fr 1fr", gap: "10px", width: "100%", height: "100%", minHeight: 0, overflow: "hidden" }}>
                {/* Quad 1: AXIAL */}
                <div style={{ backgroundColor: "#06090c", border: `1px solid ${activeScanPlane === 'AXIAL' ? 'var(--cyan)' : '#22323a'}`, borderRadius: "4px", padding: "8px", display: "flex", flexDirection: "column", minHeight: 0, overflow: "hidden" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "#8ea1a8", marginBottom: "4px" }}>
                    <b>1. AXIAL VIEW</b>
                    <span>{activeScanPlane === 'AXIAL' ? '● PRIMARY SCAN' : 'MPR DERIVED'}</span>
                  </div>
                  <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: "#030608", border: "1px dashed #1e2c33", borderRadius: "3px" }}>
                    <span style={{ fontSize: "11px", color: "#6b8089", fontFamily: "monospace" }}>[AXIAL Image Slot] · FOV:{fov}mm</span>
                  </div>
                </div>

                {/* Quad 2: SAGITTAL */}
                <div style={{ backgroundColor: "#06090c", border: `1px solid ${activeScanPlane === 'SAGITTAL' ? 'var(--cyan)' : '#22323a'}`, borderRadius: "4px", padding: "8px", display: "flex", flexDirection: "column", minHeight: 0, overflow: "hidden" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "#8ea1a8", marginBottom: "4px" }}>
                    <b>2. SAGITTAL VIEW</b>
                    <span>{activeScanPlane === 'SAGITTAL' ? '● PRIMARY SCAN' : 'MPR DERIVED'}</span>
                  </div>
                  <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: "#030608", border: "1px dashed #1e2c33", borderRadius: "3px" }}>
                    <span style={{ fontSize: "11px", color: "#6b8089", fontFamily: "monospace" }}>[SAGITTAL Image Slot] · FOV:{fov}mm</span>
                  </div>
                </div>

                {/* Quad 3: CORONAL */}
                <div style={{ backgroundColor: "#06090c", border: `1px solid ${activeScanPlane === 'CORONAL' ? 'var(--cyan)' : '#22323a'}`, borderRadius: "4px", padding: "8px", display: "flex", flexDirection: "column", minHeight: 0, overflow: "hidden" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "#8ea1a8", marginBottom: "4px" }}>
                    <b>3. CORONAL VIEW</b>
                    <span>{activeScanPlane === 'CORONAL' ? '● PRIMARY SCAN' : 'MPR DERIVED'}</span>
                  </div>
                  <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: "#030608", border: "1px dashed #1e2c33", borderRadius: "3px" }}>
                    <span style={{ fontSize: "11px", color: "#6b8089", fontFamily: "monospace" }}>[CORONAL Image Slot] · FOV:{fov}mm</span>
                  </div>
                </div>

                {/* Quad 4: 2D MIP & Multi-Slice Stack */}
                <div style={{ backgroundColor: "#06090c", border: "1px solid var(--amber)", borderRadius: "4px", padding: "8px", display: "flex", flexDirection: "column", minHeight: 0, overflow: "hidden" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "var(--amber)", marginBottom: "4px" }}>
                    <b>4. 2D MIP &amp; SLICE STACK</b>
                    <span>{isInterleaved ? 'INTERLEAVED' : 'SEQUENTIAL'}</span>
                  </div>
                  <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "#030608", padding: "6px", borderRadius: "3px", minHeight: 0, overflow: "hidden" }}>
                    <SlabStackView
                      sliceCount={sliceCount}
                      sliceThickMm={sliceThick}
                      sliceGapMm={sliceGap}
                      isInterleaved={isInterleaved}
                      cursorIndex={Math.max(0, mipCursorZ - 1)}
                      onSelect={(i) => setMipCursorZ(i + 1)}
                    />
                  </div>
                </div>
              </div>)
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
                    <SequenceLego blocks={blocks} selectedId={selectedBlockId} physicalUnits={compiledSequence?.metadata?.gradient_units === "mt_m"} onPlace={placeBlock} onSelect={setSelectedBlockId}
                      onMove={(id, t0_s) => void compileBlocks(blocks.map((block) => block.id === id ? { ...block, t0_s } : block))}
                      onDelete={(id) => { setSelectedBlockId(undefined); void compileBlocks(blocks.filter((block) => block.id !== id)); }} />
                    {runError && <div role="alert" style={{ color: "#fb7185", padding: 6 }}>STATUS ERROR · {runError}</div>}
                    {compiledSequence ? (
                      <SequenceIRTimeline
                        sequence={compiledSequence}
                        cursorTimeMs={cursors.cursorTime}
                        selectedEventKey={timelineSelection ? `${timelineSelection.channel}-${timelineSelection.index}` : undefined}
                        onDropBlock={placeBlockAt}
                        onSelectEvent={(channel, time, value, index) => {
                          setTimelineSelection({ channel, time, value, index });
                          setCursors({
                            ...cursors,
                            cursorTime: time * 1000,
                            selectedEvent: `${channel}@${(time * 1000).toFixed(1)}ms`,
                          });
                        }}
                      />
                    ) : (
                      <div data-testid="sequence-ir-waiting" style={{ fontSize: "11px", color: "#8ea1a8", fontFamily: "monospace", padding: "16px" }}>
                        awaiting SequenceIR from POST /sequences/compose
                      </div>
                    )}
                    {timelineSelection?.channel === "rf_amp" && (
                      <PulseInspector
                        key={`rf-${timelineSelection.index}`}
                        flipAngleDeg={Number((compiledSequence!.metadata?.event_overlays as Record<string, Record<string, unknown>> | undefined)?.[`${timelineSelection.channel}:${timelineSelection.index}`]?.flip_angle_deg ?? timelineSelection.value)}
                        sliceThicknessMm={sliceThick}
                        durationMs={Number((compiledSequence!.metadata?.event_overlays as Record<string, Record<string, unknown>> | undefined)?.[`${timelineSelection.channel}:${timelineSelection.index}`]?.duration_s) * 1000 || undefined}
                        timeBandwidth={Number((compiledSequence!.metadata?.event_overlays as Record<string, Record<string, unknown>> | undefined)?.[`${timelineSelection.channel}:${timelineSelection.index}`]?.time_bandwidth) || undefined}
                        phaseDeg={(compiledSequence!.metadata?.event_overlays as Record<string, Record<string, unknown>> | undefined)?.[`${timelineSelection.channel}:${timelineSelection.index}`]?.phase_deg as number | undefined}
                        eventEditor
                        onApply={applyEventPatch}
                      />
                    )}
                    {timelineSelection && ["gx", "gy", "gz"].includes(timelineSelection.channel) && (
                      <GradientEventEditor
                        key={`${timelineSelection.channel}-${timelineSelection.index}`}
                        channel={timelineSelection.channel.toUpperCase().replace("X", "x").replace("Y", "y").replace("Z", "z") as "Gx" | "Gy" | "Gz"}
                        initialAmplitude={Number((compiledSequence!.metadata?.event_overlays as Record<string, Record<string, unknown>> | undefined)?.[`${timelineSelection.channel}:${timelineSelection.index}`]?.amplitude_mt_m ?? (compiledSequence!.metadata?.gradient_units === "mt_m" ? timelineSelection.value : 20))}
                        initialDurationMs={Number((compiledSequence!.metadata?.event_overlays as Record<string, Record<string, unknown>> | undefined)?.[`${timelineSelection.channel}:${timelineSelection.index}`]?.duration_s) * 1000 || undefined}
                        initialRampMs={Number((compiledSequence!.metadata?.event_overlays as Record<string, Record<string, unknown>> | undefined)?.[`${timelineSelection.channel}:${timelineSelection.index}`]?.ramp_time_s) * 1000 || undefined}
                        physicalUnits={compiledSequence!.metadata?.gradient_units === "mt_m"}
                        onApply={applyEventPatch}
                      />
                    )}
                    {timelineSelection?.channel === "adc_gate" && (
                      <div data-testid="adc-event-chip" style={{ margin: "8px", padding: "6px 10px", border: "1px solid #fb7185", fontFamily: "monospace" }}>
                        ADC · {(timelineSelection.time * 1000).toFixed(1)} ms · value {timelineSelection.value}
                      </div>
                    )}
                  </div>
                )}
                {physicsTab === "epg_phase" && (
                  phaseDistribution && typeof phaseDistribution.data === "object" ? <div data-testid="phase-distribution-plot" style={{ width: "100%", height: "260px" }}>
                    <div style={{ font: "10px monospace", color: "#8ea1a8" }}>Backend phase_distribution · x vs off-resonance</div>
                    <svg viewBox="0 0 520 190" style={{ width: "100%", height: "100%" }} aria-label="Backend PDG spatial off-resonance grid">
                      <line x1="35" y1="95" x2="505" y2="95" stroke="#26363d" />
                      {(Array.isArray(phaseDistribution.data.off_hz) ? phaseDistribution.data.off_hz as number[] : []).map((value, index, values) => {
                        const peak = Math.max(1, ...values.map((item) => Math.abs(item)));
                        const x = 35 + index * 470 / Math.max(1, values.length - 1);
                        return <line key={index} x1={x} y1="95" x2={x} y2={95 - value * 70 / peak} stroke="var(--cyan)" strokeWidth="2" />;
                      })}
                      <text x="35" y="180" fill="#8ea1a8" fontSize="9">x (m) · off_hz from backend RUN</text>
                    </svg>
                  </div> : configurations ? <div data-testid="epg-pathways" style={{ width: "100%", height: "260px" }}>
                    <div style={{ font: "10px monospace", color: "#8ea1a8" }}>Backend configurations · rows F+ / F− / Z · columns echo snapshots</div>
                    <svg viewBox="0 0 520 190" style={{ width: "100%", height: "100%" }}>
                      {(["F+", "F−", "Z"] as const).map((label, row) => <g key={label}>
                        <text x="8" y={42 + row * 55} fill="#8ea1a8" fontSize="11">{label}</text>
                        <line x1="35" y1={38 + row * 55} x2="505" y2={38 + row * 55} stroke="#26363d" />
                        {(Array.isArray(configurations.data) ? configurations.data : []).map((snapshot: unknown, echo: number) => {
                          const states = Array.isArray(snapshot) && Array.isArray(snapshot[row]) ? snapshot[row] as number[] : [];
                          const magnitude = states.reduce((peak, value) => typeof value === "number" && value > peak ? value : peak, 0);
                          const x = 48 + echo * (440 / Math.max(1, (configurations.data as unknown[]).length - 1));
                          return <line key={echo} x1={x} y1={38 + row * 55} x2={x} y2={38 + row * 55 - Math.min(32, magnitude * 32)} stroke={row === 2 ? "var(--amber)" : "var(--cyan)"} strokeWidth="3" />;
                        })}
                      </g>)}
                    </svg>
                  </div> : <div data-testid="epg-awaiting" style={{ color: "#8ea1a8", fontFamily: "monospace" }}>awaiting phase_distribution from RUN</div>
                )}
                {physicsTab === "bloch_sphere" && (
                  <div data-testid="bloch-hud" style={{ textAlign: "center" }}>
                    {sliceProfile && typeof sliceProfile.data === "object" ? (
                      <svg data-testid="slice-profile-plot" viewBox="0 0 320 150" width="320" height="150" aria-label="Backend slice profile Mz and Mxy versus z">
                        <line x1="20" y1="130" x2="310" y2="130" stroke="#33434a" />
                        {(["mz", "mxy"] as const).map((key) => {
                          const values = Array.isArray(sliceProfile.data[key]) ? sliceProfile.data[key] as number[] : [];
                          const points = values.map((value, index) => `${20 + index * 290 / Math.max(1, values.length - 1)},${75 - value * 55}`).join(" ");
                          return <polyline key={key} points={points} fill="none" stroke={key === "mz" ? "var(--amber)" : "var(--cyan)"} strokeWidth="2" />;
                        })}
                        <text x="22" y="145" fill="#8ea1a8" fontSize="9">z (m) · backend RUN · Mz amber / Mxy cyan</text>
                      </svg>
                    ) : <div data-testid="slice-profile-awaiting" style={{ color: "#8ea1a8", fontFamily: "monospace" }}>awaiting slice_profile from RUN</div>}
                    <svg viewBox="0 0 220 220" width="220" height="220" aria-label="Mx horizontal and Mz vertical orthographic projection">
                      <circle cx="110" cy="110" r="96" fill="none" stroke="#33434a" />
                      <line x1="14" y1="110" x2="206" y2="110" stroke="#33434a" />
                      <line x1="110" y1="14" x2="110" y2="206" stroke="#33434a" />
                      <line x1="110" y1="110" x2={110 + (runVector?.[0] ?? 0) * 82} y2={110 - (runVector?.[2] ?? 1) * 82} transform={runVector ? undefined : `rotate(${faDeg} 110 110)`} stroke="var(--amber)" strokeWidth="4" />
                      <circle cx="110" cy="110" r="4" fill="var(--cyan)" />
                      <text x="172" y="104" fill="#8ea1a8" fontSize="9">Mx</text><text x="115" y="24" fill="#8ea1a8" fontSize="9">Mz</text>
                    </svg>
                    <div style={{ font: "10px monospace", color: "#8ea1a8" }}>orthographic projection: Mx → x, Mz → y</div>
                    {!runVector && <div data-testid="bloch-seed-label" style={{ color: "var(--amber)", font: "10px monospace" }}>editor seed · FA slider, not RUN magnetization</div>}
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
                {physicsTab === "spectrum" && <SpectrumPlot resultGraph={resultGraph} />}
              </div>
            )}
          </div>
        </div>

        {/* Linked Echo Train Scrubber — imaging sequences only */}
        {!isSpectrumExperiment && (
        <div className="linked-scope-rail" data-testid="echo-train-rail">
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
        )}
      </section>

      {/* 3. Control Bank: Geometric & Physical Dials */}
      <section className="control-bank" data-testid="control-bank">
        <div className="bank-header">
          <h3>CONTROL BANK</h3>
          <span className="sub-mode" data-testid="control-bank-mode">{isSpectrumExperiment ? "Saturation & Offset" : profile === "clinical" ? "Geometry & Contrast" : "Operator Dials"}</span>
        </div>

        {isSpectrumExperiment ? (
          <>
            <div className="control-group">
              <label>Saturation B1</label>
              <div className="slider-row">
                <input type="range" min="0.5" max="5" step="0.1" value={cestPowerUt == null ? "" : cestPowerUt} disabled={cestPowerUt == null} onChange={(e) => { setCestPowerUt(Number(e.target.value)); setCestDirty((d) => ({ ...d, power: true })); }} data-testid="cest-b1-slider" />
                <span className="value-badge" data-testid="cest-b1-value">{cestPowerUt == null ? "—" : `${cestPowerUt.toFixed(1)} µT`}</span>
              </div>
            </div>
            <div className="control-group">
              <label>Offset span</label>
              <div className="slider-row">
                <input type="range" min="3.5" max="10" step="0.5" value={cestOffsetSpanPpm == null ? "" : cestOffsetSpanPpm} disabled={cestOffsetSpanPpm == null} onChange={(e) => { setCestOffsetSpanPpm(Number(e.target.value)); setCestDirty((d) => ({ ...d, span: true })); }} data-testid="cest-offset-span-slider" />
                <span className="value-badge" data-testid="cest-offset-span-value">{cestOffsetSpanPpm == null ? "—" : `±${cestOffsetSpanPpm} ppm`}</span>
              </div>
            </div>
            {cestMode === "pulsed" && (
              <div className="control-group">
                <label>Duty cycle</label>
                <div className="slider-row">
                  <input type="range" min="0.2" max="1" step="0.05" value={cestDutyCycle == null ? "" : cestDutyCycle} disabled={cestDutyCycle == null} onChange={(e) => { setCestDutyCycle(Number(e.target.value)); setCestDirty((d) => ({ ...d, duty: true })); }} data-testid="cest-duty-slider" />
                  <span className="value-badge" data-testid="cest-duty-value">{cestDutyCycle == null ? "—" : cestDutyCycle.toFixed(2)}</span>
                </div>
              </div>
            )}
          </>
        ) : profile === "clinical" ? (
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

            <div className="control-group">
              <label>Repetition Time (TR)</label>
              <div className="slider-row">
                <input
                  type="range"
                  min={isGRE ? 15 : 1000}
                  max={isGRE ? 500 : 5000}
                  step={isGRE ? 5 : 500}
                  value={tr}
                  onChange={(e) => setTr(Number(e.target.value))}
                  data-testid="clinical-tr-slider"
                />
                <span className="value-badge">{tr} ms</span>
              </div>
            </div>
          </>
        ) : (
          /* Physics Controls: excitation FA, refocus FA, TE, TR, ADC BW */
          <>
            <div className="control-group">
              <label>Excitation Flip Angle</label>
              <div className="slider-row">
                <input
                  type="range"
                  min={isGRE ? 5 : 10}
                  max={isGRE ? 90 : 90}
                  step={1}
                  value={exciteFa}
                  onChange={(e) => setExciteFa(Number(e.target.value))}
                  data-testid="physics-excite-fa-slider"
                />
                <span className="value-badge">{exciteFa}°</span>
              </div>
            </div>

            <div className="control-group">
              <label>{isGRE ? "Ernst Flip Angle (α)" : "Refocusing Angle α"}</label>
              <div className="slider-row">
                <input
                  type="range"
                  min={isGRE ? 5 : 60}
                  max={isGRE ? 90 : 180}
                  step={isGRE ? 1 : 5}
                  value={faDeg}
                  onChange={(e) => setFa(Number(e.target.value))}
                  data-testid="physics-refocus-fa-slider"
                />
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

            <div className="control-group">
              <label>ADC Bandwidth</label>
              <div className="slider-row">
                <input
                  type="range"
                  min={20000}
                  max={200000}
                  step={5000}
                  value={adcBwHz}
                  onChange={(e) => setAdcBwHz(Number(e.target.value))}
                  data-testid="physics-adc-bw-slider"
                />
                <span className="value-badge">{(adcBwHz / 1000).toFixed(0)} kHz</span>
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
        <div className="cost-tier">KERNEL ENGINE: {resultGraph?.observations?.[0]?.provenance?.engine?.toUpperCase() || resultGraph?.execution_plan?.selected_engine?.toUpperCase() || (executionState === "ERROR" ? "—" : "IDLE")}</div>
        {runError ? (
          <div className="run-error" data-testid="run-error" title={runError}>
            RUN FAILED
          </div>
        ) : (
          <div className="system-info">MRQLab v0.76 · RF overlay</div>
        )}
      </section>
    </div>
  );
}
