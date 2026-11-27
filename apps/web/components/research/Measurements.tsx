import React from "react";
import type { ResearchRun } from "../../lib/research";
import styles from "../../app/research/research.module.css";

export const COLORS = ["var(--blue-11)", "var(--amber-9)", "var(--violet-11)", "var(--red-11)"];
const TARGET_LABELS: Record<string, string> = {
  target_state_error: "Density / periodic-state target", target_min_signal_fraction: "Retained signal fraction minimum",
  target_memory_refinement_error: "Memory trace refinement target", target_kernel_error: "Integrated memory-kernel target",
  target_velocity_rmse_m_s: "Velocity RMSE target (m/s)", target_frozen_image_error: "Complex frozen-reference NRMSE target",
  target_image_error: "Image NRMSE target", target_coefficient_error: "Component NRMSE target", target_data_residual: "Data residual target", target_min_contrast: "ROI magnitude contrast minimum", target_max_rf_energy: "RF energy proxy limit",
  threshold: "Image NRMSE target", target_rf_error: "RF refinement target", target_fit_residual: "Fit residual target", target_refinement_error: "Grid refinement target", target_fov_error: "Expanded FOV target", target_leakage_fraction: "Outside-voxel power limit", max_interrupted_fraction: "Maximum interrupted fraction", blood_target_max: "Blood |Mz| limit", wall_target_min: "Wall |Mz| minimum",
  target_min_amide_contrast: "Amide contrast target", target_min_relay_contrast: "Relay contrast target", target: "Maximum relative amount error target",
};
const format = (value: number) => Number.isInteger(value) ? String(value) : value.toPrecision(5);
// Axis extents are computed by iteration: spreading an untrusted preview array into Math.min/Math.max
// can exceed the engine's argument limit. Empty ranges keep each caller's documented fallback.
function extent(values: number[], emptyLow: number, emptyHigh: number): [number, number] {
  if (!values.length) return [emptyLow, emptyHigh];
  let low = values[0], high = values[0];
  for (let index = 1; index < values.length; index++) {
    const value = values[index];
    if (value < low) low = value;
    if (value > high) high = value;
  }
  return [low, high];
}
// Labels come from untyped JSON keys, so only own entries may resolve; "__proto__" / "constructor"
// must never read Object.prototype and be rendered as a React child.
function ownLabel(map: Record<string, string>, key: string): string | undefined {
  return Object.prototype.hasOwnProperty.call(map, key) ? map[key] : undefined;
}
const hasOwn = (value: object, key: PropertyKey) => Object.prototype.hasOwnProperty.call(value, key);
const numberArray = (value: unknown): value is number[] => Array.isArray(value) && value.every(item => typeof item === "number" && Number.isFinite(item));
const MAX_IMAGES = 8, MAX_CURVES = 32, MAX_SIDE = 128, MAX_POINTS = 10000;

function renderable(view: unknown): view is ResearchRun["view"] {
  if (!view || typeof view !== "object") return false;
  const candidate = view as ResearchRun["view"];
  if (!Array.isArray(candidate.images) || candidate.images.length > MAX_IMAGES || !Array.isArray(candidate.curves) || candidate.curves.length > MAX_CURVES ||
      typeof candidate.x_label !== "string" || typeof candidate.y_label !== "string" || !candidate.validation || typeof candidate.validation !== "object" ||
      typeof candidate.validation.passed !== "boolean" || !candidate.metrics || typeof candidate.metrics !== "object" || Array.isArray(candidate.metrics)) return false;
  if (!Object.values(candidate.metrics).every(value => typeof value === "number" && Number.isFinite(value))) return false;
  if (!Object.entries(candidate.validation).every(([key, value]) => typeof value === "boolean" ||
      (typeof value === "number" && Number.isFinite(value) && hasOwn(TARGET_LABELS, key)))) return false;
  if (!candidate.images.every(image => image && typeof image.label === "string" && Number.isInteger(image.width) && image.width > 0 && image.width <= MAX_SIDE &&
      Number.isInteger(image.height) && image.height > 0 && image.height <= MAX_SIDE && numberArray(image.values) && image.values.length === image.width * image.height &&
      (image.scale_group === undefined || typeof image.scale_group === "string"))) return false;
  let totalPoints = 0;
  return candidate.curves.every(curve => {
    if (!curve || typeof curve.label !== "string" || !numberArray(curve.x) || !numberArray(curve.y) || curve.x.length !== curve.y.length || curve.x.length > MAX_POINTS) return false;
    totalPoints += curve.x.length;
    return totalPoints <= MAX_POINTS;
  });
}

export default function Measurements({ view, validationLabel = "目标验证" }: { view: ResearchRun["view"]; validationLabel?: string }) {
  if (!renderable(view)) return <p role="alert">记录载荷缺少可安全显示的测量结构。</p>;
  const { images, curves, x_label, y_label } = view;
  const scaleGroups = new Map<string, number[]>();
  for (const image of images) {
    const key = image.scale_group ?? "shared";
    const values = scaleGroups.get(key) ?? [];
    for (const value of image.values) values.push(value);
    scaleGroups.set(key, values);
  }
  const scales = new Map(Array.from(scaleGroups, ([key, values]): [string, { low: number; high: number }] => {
    const [low, high] = values.length ? extent(values, 0, 1) : [0, 1];
    return [key, { low, high }];
  }));
  const xs = curves.flatMap(curve => curve.x), ys = curves.flatMap(curve => curve.y);
  const [xmin, xmax] = extent(xs, Infinity, -Infinity);
  const [yLow, yHigh] = extent(ys, Infinity, -Infinity);
  const ymin = Math.min(0, yLow), ymax = yHigh;
  const sx = (x: number) => 52 + 590 * (x - xmin) / (xmax - xmin || 1);
  const sy = (y: number) => 216 - 190 * (y - ymin) / (ymax - ymin || 1);
  return <div className={styles.measurements}>
    {images.length > 0 && <div className={styles.images}>
      {images.map(image => {
        const { low, high } = scales.get(image.scale_group ?? "shared")!;
        return <figure key={image.label}>
        <svg viewBox={`0 0 ${image.width} ${image.height}`} role="img" aria-label={image.label}>
          {image.values.map((value, i) => {
            const intensity = (value - low) / (high - low || 1);
            return <rect key={i} x={i % image.width} y={Math.floor(i / image.width)} width={1} height={1}
              fill={`rgb(${Math.round(16 + 225 * intensity)},${Math.round(45 + 161 * intensity)},${Math.round(61 + 70 * intensity)})`} />;
          })}
        </svg><figcaption>{image.label} <span>色标 {format(low)} — {format(high)}</span></figcaption>
      </figure>; })}
      <p>{scales.size > 1 ? "按标注的物理量分组显示，同组共享色标；数值范围和单位见各图。" : "图像共享绝对值色标。"}3D 显示中心层；完整体数据保留在导出记录。</p>
    </div>}
    {curves.length > 0 && <figure className={styles.trace}>
      <svg viewBox="0 0 680 265" role="img" aria-label={`${y_label} versus ${x_label}`}>
        <title>{y_label}</title>
        {[0, .25, .5, .75, 1].map(t => <g key={t}>
          <line x1={52} x2={642} y1={216 - 190*t} y2={216 - 190*t} stroke="var(--border)" />
          <text x={44} y={220 - 190*t} textAnchor="end">{format(ymin+(ymax-ymin)*t)}</text>
        </g>)}
        {curves.map((curve, index) => <g key={curve.label}>
          <polyline fill="none" stroke={COLORS[index % COLORS.length]} strokeWidth={2}
            points={curve.x.map((x, i) => `${sx(x)},${sy(curve.y[i])}`).join(" ")} />
          {curve.x.length <= 16 && curve.x.map((x, i) => <circle key={i} cx={sx(x)} cy={sy(curve.y[i])} r={3} fill={COLORS[index % COLORS.length]} />)}
        </g>)}
        <text x={52} y={238}>{format(xmin)}</text><text x={642} y={238} textAnchor="end">{format(xmax)}</text>
        <text x={347} y={260} textAnchor="middle">{x_label}</text>
      </svg>
      <figcaption>{y_label} <span>{curves.map((curve, i) => <b key={curve.label} style={{ color: COLORS[i % COLORS.length] }}>{curve.label}</b>)}</span></figcaption>
    </figure>}
    <table><caption>目标与测量</caption><tbody>
      <tr><th scope="row">{validationLabel}</th><td>{view.validation.passed ? "通过" : "未通过"}</td></tr>
      {Object.entries(view.metrics).map(([key, value]) => <tr key={key}><th scope="row">{key}</th><td>{format(value)}</td></tr>)}
      {Object.entries(view.validation).flatMap(([key, value]) => {
        const label = ownLabel(TARGET_LABELS, key);
        return typeof value === "number" && label ? [<tr key={key}><th scope="row">{label}</th><td>{format(value)}</td></tr>] : [];
      })}
    </tbody></table>
    <details><summary>曲线数值表</summary><div className={styles.scroll}>
      <table><thead><tr><th>序列</th><th>{x_label}</th><th>{y_label}</th></tr></thead><tbody>
        {curves.flatMap(curve => curve.x.map((x, i) => <tr key={`${curve.label}-${i}`}><td>{curve.label}</td><td>{format(x)}</td><td>{format(curve.y[i])}</td></tr>))}
      </tbody></table>
    </div></details>
  </div>;
}
