"use client";

import React, { useEffect, useState } from "react";
import { GradientValidationResult, validateGradient } from "../../lib/api";

export function GradientEventEditor({ channel, initialAmplitude, onApply }: { channel: "Gx" | "Gy" | "Gz"; initialAmplitude: number; onApply?: (patch: { amplitude_mt_m: number; duration_s: number; ramp_time_s: number; unit: "mT_m" }) => Promise<void> }) {
  const [amplitude, setAmplitude] = useState(initialAmplitude);
  const [duration, setDuration] = useState(1);
  const [ramp, setRamp] = useState(0.1);
  const [result, setResult] = useState<GradientValidationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setResult(null);
    setPending(true);
    validateGradient({ amplitude_mt_m: amplitude, duration_ms: duration, ramp_time_ms: ramp, channel })
      .then((payload) => {
        if (!cancelled) {
          setResult(payload);
          setPending(false);
        }
      })
      .catch((reason) => {
        if (!cancelled) {
          setResult(null);
          setPending(false);
          setError(reason instanceof Error ? reason.message : String(reason));
        }
      });
    return () => { cancelled = true; };
  }, [amplitude, channel, duration, ramp]);

  return (
    <section data-testid="gradient-event-editor" style={{ border: "1px solid #33434a", padding: "10px", marginTop: "8px" }}>
      <strong>{channel} GRADIENT VALIDATION</strong>
      <div style={{ display: "flex", gap: "10px", marginTop: "8px", fontSize: "11px", flexWrap: "wrap" }}>
        <label>Amplitude (mT/m) <input data-testid="grad-amp" type="number" step="0.1" value={amplitude} onChange={(e) => setAmplitude(Number(e.target.value))} /></label>
        <label>Duration (ms) <input data-testid="grad-duration" type="number" step="0.1" value={duration} onChange={(e) => setDuration(Number(e.target.value))} /></label>
        <label>Ramp (ms) <input data-testid="grad-ramp" type="number" step="0.1" value={ramp} onChange={(e) => setRamp(Number(e.target.value))} /></label>
      </div>
      <div data-testid="editor-seed-note" style={{ color: "#8ea1a8", fontSize: "10px", marginTop: "6px" }}>
        editor seed · not SequenceIR unless loaded from overlay · timeline normalized value is not mT/m
      </div>
      {pending && <div data-testid="gradient-validate-pending" style={{ color: "#8ea1a8", fontSize: "10px", marginTop: "4px" }}>validating…</div>}
      {error && <div role="alert" data-testid="gradient-validate-error" style={{ color: "#fb7185" }}>{error}</div>}
      {result && <div data-testid="gradient-validation-result">
        <b>{result.is_valid ? "VALID" : "INVALID"}</b> · actual slew: {result.actual_slew_rate}
        <ul>{result.violations.map((violation) => <li key={violation}>{violation}</li>)}</ul>
      </div>}
      <button
        data-testid="event-apply"
        disabled={!result?.is_valid || pending || applying || !onApply}
        onClick={async () => {
          if (!onApply) return;
          setApplying(true);
          setError(null);
          try {
            await onApply({ amplitude_mt_m: amplitude, duration_s: duration / 1000, ramp_time_s: ramp / 1000, unit: "mT_m" });
          } catch (reason) {
            setError(reason instanceof Error ? reason.message : String(reason));
          } finally {
            setApplying(false);
          }
        }}
      >{applying ? "APPLYING…" : "APPLY"}</button>
    </section>
  );
}
