"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { fetchReconDemo, ReconDemoPayload, TrajectoryType } from "../../lib/api";

function paintHeatmap(canvas: HTMLCanvasElement | null, grid: number[][] | undefined) {
  if (!canvas || !grid?.length) return;
  const n = grid.length;
  canvas.width = n;
  canvas.height = n;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const img = ctx.createImageData(n, n);
  let max = 1e-12;
  for (const row of grid) for (const v of row) max = Math.max(max, v);
  for (let y = 0; y < n; y++) {
    for (let x = 0; x < n; x++) {
      const t = Math.max(0, Math.min(1, grid[y][x] / max));
      const i = (y * n + x) * 4;
      img.data[i] = Math.round(20 + t * 56);
      img.data[i + 1] = Math.round(40 + t * 200);
      img.data[i + 2] = Math.round(48 + t * 180);
      img.data[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
}

export function KSpaceReconLens() {
  const [trajectoryType, setTrajectoryType] = useState<TrajectoryType>("cartesian");
  const [acceleration, setAcceleration] = useState(2);
  const [spokes, setSpokes] = useState(24);
  const [demo, setDemo] = useState<ReconDemoPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const phantomRef = useRef<HTMLCanvasElement>(null);
  const reconRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchReconDemo({
      trajectory_type: trajectoryType,
      matrix_size: 32,
      acceleration_factor: acceleration,
      num_spokes_or_interleaves: spokes,
      points_per_arm: 32,
      num_slices: trajectoryType === "stack_of_stars" ? 4 : 1,
    })
      .then((payload) => {
        if (!cancelled) setDemo(payload);
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setDemo(null);
          setError(err.message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [trajectoryType, acceleration, spokes]);

  useEffect(() => {
    paintHeatmap(phantomRef.current, demo?.phantom);
    paintHeatmap(reconRef.current, demo?.recon);
  }, [demo]);

  const trajPath = useMemo(() => {
    if (!demo?.preview) return "";
    return demo.preview.kx
      .map((kx, i) => {
        const x = 100 + kx * 90;
        const y = 100 - (demo.preview.ky[i] ?? 0) * 90;
        return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(" ");
  }, [demo]);

  return (
    <div data-testid="kspace-recon-lens" style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", gap: "8px" }}>
      <div style={{ display: "flex", gap: "10px", alignItems: "center", fontSize: "11px", color: "var(--cyan)", fontFamily: "monospace", flexWrap: "wrap" }}>
        <b>K-SPACE / RECON</b>
        <select
          data-testid="trajectory-type-select"
          value={trajectoryType}
          onChange={(e) => setTrajectoryType(e.target.value as TrajectoryType)}
          style={{ background: "#111", color: "var(--cyan)", border: "1px solid #33434a", fontSize: "11px" }}
        >
          <option value="cartesian">Cartesian</option>
          <option value="radial">Radial</option>
          <option value="spiral">Spiral</option>
          <option value="stack_of_stars">Stack-of-Stars</option>
        </select>
        {trajectoryType === "cartesian" ? (
          <>
            <span>R</span>
            <input
              data-testid="kspace-accel-slider"
              type="range"
              min={1}
              max={4}
              step={1}
              value={acceleration}
              onChange={(e) => setAcceleration(Number(e.target.value))}
              style={{ width: "80px" }}
            />
            <span>{acceleration}×</span>
          </>
        ) : (
          <>
            <span>spokes</span>
            <input
              data-testid="kspace-spokes-slider"
              type="range"
              min={8}
              max={64}
              step={4}
              value={spokes}
              onChange={(e) => setSpokes(Number(e.target.value))}
              style={{ width: "80px" }}
            />
            <span>{spokes}</span>
          </>
        )}
        {demo && <span data-testid="kspace-nrmse">NRMSE {demo.nrmse.toFixed(3)}</span>}
        {loading && <span>loading…</span>}
      </div>

      {error && (
        <div data-testid="kspace-backend-wait" style={{ fontSize: "11px", color: "#f59e0b", fontFamily: "monospace" }}>
          awaiting backend recon payload · {error}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px", minHeight: "200px" }}>
        <div style={{ background: "#030608", border: "1px solid #22323a", borderRadius: "4px", padding: "6px" }}>
          <div style={{ fontSize: "10px", color: "#8ea1a8", marginBottom: "4px" }}>TRAJECTORY (kx, ky)</div>
          <svg viewBox="0 0 200 200" style={{ width: "100%", height: "180px" }} data-testid="kspace-trajectory-svg">
            <rect x="5" y="5" width="190" height="190" fill="none" stroke="#1f2d33" />
            <circle cx="100" cy="100" r="90" fill="none" stroke="#1f2d33" />
            {trajPath && <path d={trajPath} fill="none" stroke="var(--cyan)" strokeWidth="0.8" opacity="0.85" />}
          </svg>
        </div>
        <div style={{ background: "#030608", border: "1px solid #22323a", borderRadius: "4px", padding: "6px" }}>
          <div style={{ fontSize: "10px", color: "#8ea1a8", marginBottom: "4px" }}>PHANTOM (backend)</div>
          <canvas ref={phantomRef} data-testid="kspace-phantom-canvas" style={{ width: "100%", height: "180px", imageRendering: "pixelated" }} />
        </div>
        <div style={{ background: "#030608", border: "1px solid #22323a", borderRadius: "4px", padding: "6px" }}>
          <div style={{ fontSize: "10px", color: "#8ea1a8", marginBottom: "4px" }}>RECON (backend)</div>
          <canvas ref={reconRef} data-testid="kspace-recon-canvas" style={{ width: "100%", height: "180px", imageRendering: "pixelated" }} />
        </div>
      </div>
    </div>
  );
}
