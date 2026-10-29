import React from "react";
import type { ResearchRun } from "../../lib/research";
import styles from "../../app/research/research.module.css";

const COLORS = ["#4fe3eb", "#ffb834", "#c7a9ef", "#f08e9a"];
const TARGET_LABELS: Record<string, string> = {
  target_image_error: "Image NRMSE target", target_coefficient_error: "Component NRMSE target", target_data_residual: "Data residual target", target_min_contrast: "ROI magnitude contrast minimum", target_max_rf_energy: "RF energy proxy limit",
  threshold: "Image NRMSE target", target_rf_error: "RF refinement target", target_fit_residual: "Fit residual target", target_refinement_error: "Grid refinement target", target_fov_error: "Expanded FOV target", target_leakage_fraction: "Outside-voxel power limit", max_interrupted_fraction: "Maximum interrupted fraction", blood_target_max: "Blood |Mz| limit", wall_target_min: "Wall |Mz| minimum",
  target_min_amide_contrast: "Amide contrast target", target_min_relay_contrast: "Relay contrast target", target: "Maximum relative amount error target",
};
const format = (value: number) => Number.isInteger(value) ? String(value) : value.toPrecision(5);

export default function Measurements({ view, validationLabel = "目标验证" }: { view: ResearchRun["view"]; validationLabel?: string }) {
  const { images, curves, x_label, y_label } = view;
  const scaleGroups = new Map<string, number[]>();
  for (const image of images) {
    const key = image.scale_group ?? "shared";
    const values = scaleGroups.get(key) ?? [];
    values.push(...image.values); scaleGroups.set(key, values);
  }
  const scales = new Map(Array.from(scaleGroups, ([key, values]) => [key, {
    low: values.length ? Math.min(...values) : 0, high: values.length ? Math.max(...values) : 1,
  }]));
  const xs = curves.flatMap(curve => curve.x), ys = curves.flatMap(curve => curve.y);
  const xmin = Math.min(...xs), xmax = Math.max(...xs), ymin = Math.min(0, ...ys), ymax = Math.max(...ys);
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
      <p>{scales.size > 1 ? "参考与重建共享绝对值色标；失配对照使用单独色标，数值范围见各图。" : "图像共享绝对值色标。"}3D 显示中心层；完整体数据保留在导出记录。</p>
    </div>}
    {curves.length > 0 && <figure className={styles.trace}>
      <svg viewBox="0 0 680 265" role="img" aria-label={`${y_label} versus ${x_label}`}>
        <title>{y_label}</title>
        {[0, .25, .5, .75, 1].map(t => <g key={t}>
          <line x1={52} x2={642} y1={216 - 190*t} y2={216 - 190*t} stroke="#334b55" />
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
      {Object.entries(view.validation).filter(([key, value]) => key in TARGET_LABELS && typeof value === "number").map(([key, value]) => <tr key={key}><th scope="row">{TARGET_LABELS[key]}</th><td>{format(value as number)}</td></tr>)}
    </tbody></table>
    <details><summary>曲线数值表</summary><div className={styles.scroll}>
      <table><thead><tr><th>序列</th><th>{x_label}</th><th>{y_label}</th></tr></thead><tbody>
        {curves.flatMap(curve => curve.x.map((x, i) => <tr key={`${curve.label}-${i}`}><td>{curve.label}</td><td>{format(x)}</td><td>{format(curve.y[i])}</td></tr>))}
      </tbody></table>
    </div></details>
  </div>;
}
