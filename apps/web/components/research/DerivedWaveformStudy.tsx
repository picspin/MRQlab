"use client";
import React, { useEffect, useRef, useState } from "react";
import { createScientificRecord, fetchMeasuredWaveformExample } from "../../lib/api";
import type { ScientificRecord, ScientificResponse } from "../../lib/scientific-records";
import styles from "../../app/research/research.module.css";

type Binding = { tissue_id: string; value: number; standard_uncertainty_s: number; stress_interval_s: number[] };
type Outcome = { id: string; executable: boolean; eligible: boolean; reasons: string[] };
type Candidate = { index: number; scale: number; executed: boolean; eligible: boolean; reasons: string[]; stress_outcomes: Outcome[] };
type Scenario = { id: string; target_passed: boolean; refinement_passed: boolean; max_signal_difference: number; max_image_difference: number;
  refined: { validation: { image_target: { measured: number } | null } } };
type Stress = { id: string; t2_s: number[] };
type StressRun = { id: string; result: { candidates: { index: number; scenarios: Scenario[] }[] } };
export type WaveformEvidence = {
  measurement: { origin: string; source_ref: string; raw_file_sha256: string | null };
  parent_revalidation: { passed: boolean; calibration_and_holdout_passed: boolean; parent_search_complete: boolean; estimated_work: number; reserved_work: number; within_max_parent_work: boolean };
  bindings: Binding[]; stress_scenarios: Stress[]; stress_runs: StressRun[]; candidates: Candidate[]; selected_index: number | null;
  validation: { passed: boolean; calibration_and_holdout_passed: boolean; complete_grid: boolean; reasons: string[] };
  work: { total_voxel_steps: number; preflight_voxel_steps: number; max_total_voxel_steps: number };
};
const num = (n: number | null | undefined) => typeof n === "number" && Number.isFinite(n) ? n.toPrecision(5) : "未计算";
const finite = (n: unknown): n is number => typeof n === "number" && Number.isFinite(n);
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every(item => typeof item === "string");

export function parseWaveformEvidence(payload: string): WaveformEvidence | null {
  try {
    const value = JSON.parse(payload)?.derivation as WaveformEvidence | undefined;
    if (!value || !value.measurement || typeof value.measurement.origin !== "string" || typeof value.measurement.source_ref !== "string" ||
        (value.measurement.raw_file_sha256 !== null && typeof value.measurement.raw_file_sha256 !== "string") ||
        !value.parent_revalidation || typeof value.parent_revalidation.passed !== "boolean" || typeof value.parent_revalidation.parent_search_complete !== "boolean" ||
        !finite(value.parent_revalidation.estimated_work) || !finite(value.parent_revalidation.reserved_work) ||
        !value.validation || typeof value.validation.passed !== "boolean" || typeof value.validation.calibration_and_holdout_passed !== "boolean" ||
        typeof value.validation.complete_grid !== "boolean" || !strings(value.validation.reasons) ||
        !value.work || !finite(value.work.total_voxel_steps) || !finite(value.work.preflight_voxel_steps) || !finite(value.work.max_total_voxel_steps) ||
        !(value.selected_index === null || Number.isInteger(value.selected_index)) ||
        !Array.isArray(value.bindings) || value.bindings.length > 2 || !Array.isArray(value.stress_scenarios) || value.stress_scenarios.length > 5 ||
        !Array.isArray(value.stress_runs) || value.stress_runs.length > 5 || !Array.isArray(value.candidates) || value.candidates.length > 8) return null;
    if (!value.bindings.every(b => b && typeof b.tissue_id === "string" && finite(b.value) && finite(b.standard_uncertainty_s) && Array.isArray(b.stress_interval_s) && b.stress_interval_s.length === 2 && b.stress_interval_s.every(finite)) ||
        !value.stress_scenarios.every(s => s && typeof s.id === "string" && Array.isArray(s.t2_s) && s.t2_s.length === value.bindings.length && s.t2_s.every(finite)) ||
        !value.candidates.every(c => c && Number.isInteger(c.index) && finite(c.scale) && typeof c.executed === "boolean" && typeof c.eligible === "boolean" && strings(c.reasons) && Array.isArray(c.stress_outcomes) && c.stress_outcomes.length <= 5 &&
          c.stress_outcomes.every(s => s && typeof s.id === "string" && typeof s.executable === "boolean" && typeof s.eligible === "boolean" && strings(s.reasons))) ||
        !value.stress_runs.every(r => r && typeof r.id === "string" && r.result && Array.isArray(r.result.candidates) && r.result.candidates.length <= 8 && r.result.candidates.every(c => c && Number.isInteger(c.index) && Array.isArray(c.scenarios) && c.scenarios.length <= 4 &&
          c.scenarios.every(s => s && typeof s.id === "string" && typeof s.target_passed === "boolean" && typeof s.refinement_passed === "boolean" && finite(s.max_signal_difference) && finite(s.max_image_difference) &&
            s.refined && s.refined.validation && (s.refined.validation.image_target === null || (s.refined.validation.image_target && finite(s.refined.validation.image_target.measured))))))) return null;
    if ((value.selected_index !== null) !== value.validation.passed ||
        (value.selected_index !== null && !value.candidates.some(c => c.index === value.selected_index && c.eligible))) return null;
    return value;
  } catch { return null; }
}

export function DeriveWaveformStudy({ parent, onCreated }: { parent: ScientificRecord; onCreated: (response: ScientificResponse) => void | Promise<void> }) {
  const [question, setQuestion] = useState("T2 不确定性下，哪些有限 RF 波形满足重建图像对比度目标？");
  const [rationale, setRationale] = useState("");
  const [draft, setDraft] = useState("");
  const [template, setTemplate] = useState<{ tissue_ids: string[]; origin: string; source_ref: string } | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);
  async function load() {
    const controller = new AbortController(); active.current?.abort(); active.current = controller; setBusy(true); setError("");
    try {
      const result = await fetchMeasuredWaveformExample(parent.record_sha256, controller.signal);
      if (!result || !result.study || typeof result.study !== "object" || Array.isArray(result.study) || !result.parent || !strings(result.parent.tissue_ids) || result.parent.tissue_ids.length !== 2 || new Set(result.parent.tissue_ids).size !== 2 ||
          !["synthetic", "measured"].includes(result.parent.origin) || typeof result.parent.source_ref !== "string") throw new Error("模板来源或组织绑定不完整。");
      if (!controller.signal.aborted) { setDraft(JSON.stringify(result.study, null, 2)); setTemplate(result.parent); }
    } catch (caught) { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "模板载入失败。"); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  async function derive() {
    const controller = new AbortController(); active.current?.abort(); active.current = controller; setBusy(true); setError("");
    try {
      const study: unknown = JSON.parse(draft);
      if (!study || typeof study !== "object" || Array.isArray(study)) throw new Error("研究输入必须是 JSON 对象。");
      const result = await createScientificRecord({ context: { study_id: parent.summary.study_id, research_question: question.trim(), target_rationale: rationale.trim(), intended_use: "research",
        assumptions: "几何、波形、T1/PD 和目标由用户提供或采用合成模板；仅 T2 来自父记录拟合及不确定性角点；不把接收增益用于图像。" },
        execution: { type: "measured_waveform_image", parent_record_sha256: parent.record_sha256, study: study as Record<string, unknown> } }, controller.signal);
      if (!controller.signal.aborted) await onCreated(result);
    } catch (caught) { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "派生波形研究失败。"); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  return <section className={styles.provenance} aria-label="从 T2 实验派生波形图像研究">
    <h3>从 T2 实验派生波形图像研究</h3>
    <p>先重算父实验和独立留出，再将 T2 名义值与四个不确定性角点用于有限 RF 网格。全部场景通过才选择设计；没有合格候选时不显示替代图像。</p>
    <p>模板的 2×2 几何、T1/PD、波形和阈值均为合成或人工设定；T2 仅在父实验验证通过后绑定。点 ADC 与 RF 能量代理不是扫描仪采集或 SAR。</p>
    <button disabled={busy} onClick={() => void load()}>载入合成波形模板</button>
    {template && <p>父数据：{template.origin === "synthetic" ? "合成" : "实测（用户声明）"}；{template.source_ref}；组织：{template.tissue_ids.join("、")}。</p>}
    <div className={styles.recordFields}>
      <label>波形研究问题<textarea rows={2} disabled={busy} value={question} onChange={e => setQuestion(e.target.value)} /></label>
      <label>波形目标依据<textarea rows={2} disabled={busy} value={rationale} onChange={e => setRationale(e.target.value)} placeholder="说明选择图像目标和压力场景的原因" /></label>
      {draft && <details><summary>波形、目标与预算 JSON</summary><textarea aria-label="波形研究 JSON" rows={12} disabled={busy} value={draft} onChange={e => setDraft(e.target.value)} /></details>}
    </div>
    <button disabled={busy || !draft || !question.trim() || !rationale.trim()} onClick={() => void derive()}>{busy ? "正在重算父实验与全部场景…" : "计算并保存波形研究"}</button>
    {error && <p role="alert" className={styles.error}>{error}</p>}
  </section>;
}

export function DerivedWaveformEvidence({ evidence }: { evidence: WaveformEvidence }) {
  return <section className={styles.provenance} aria-label="T2 校准与波形搜索证据">
    <h3>T2 校准与波形搜索证据</h3>
    <p>来源：{evidence.measurement.origin === "synthetic" ? "合成数据" : evidence.measurement.origin === "measured" ? "实测（用户声明，未认证）" : "未识别"}；{evidence.measurement.source_ref}。原文件 SHA256：{evidence.measurement.raw_file_sha256 ?? "未提供"}。</p>
    <p>父实验重算：{evidence.parent_revalidation.passed ? "一致" : "未通过"}；校准及独立留出：{evidence.validation.calibration_and_holdout_passed ? "通过" : "未通过"}；完整压力网格：{evidence.validation.complete_grid ? "已计算" : "未计算"}。</p>
    <p>父 TSE 搜索：{evidence.parent_revalidation.parent_search_complete ? "完整" : "不完整"}；父工作量 {evidence.parent_revalidation.estimated_work}，声明预算 {evidence.parent_revalidation.reserved_work}。波形 voxel-step {evidence.work.total_voxel_steps} / 预检 {evidence.work.preflight_voxel_steps} / 上限 {evidence.work.max_total_voxel_steps}；两种工作单位不相加。</p>
    {evidence.validation.reasons.map((reason, i) => <p className={styles.failed} key={i}>{reason}</p>)}
    <div className={styles.scroll}><table><caption>T2 绑定与局部压力区间（ms）</caption><thead><tr><th>组织</th><th>拟合值</th><th>标准不确定度</th><th>区间</th></tr></thead><tbody>{evidence.bindings.map(b => <tr key={b.tissue_id}><th scope="row">{b.tissue_id}</th><td>{num(b.value * 1000)}</td><td>{num(b.standard_uncertainty_s * 1000)}</td><td>{b.stress_interval_s.map(v => num(v * 1000)).join(" / ")}</td></tr>)}</tbody></table></div>
    {!evidence.bindings.length && <p>未应用实验 T2。</p>}
    {evidence.stress_scenarios.length > 0 && <div className={styles.scroll}><table><caption>各 T2 压力场景（ms）</caption><thead><tr><th>场景</th>{evidence.bindings.map(b => <th key={b.tissue_id}>{b.tissue_id}</th>)}</tr></thead><tbody>{evidence.stress_scenarios.map(s => <tr key={s.id}><th scope="row">{s.id}</th>{s.t2_s.map((v, i) => <td key={i}>{num(v * 1000)}</td>)}</tr>)}</tbody></table></div>}
    <div className={styles.scroll}><table><caption>RF 候选及全部 T2 场景</caption><thead><tr><th>RF 比例</th><th>完整执行</th><th>全部目标</th><th>场景结果与原因</th></tr></thead><tbody>{evidence.candidates.map(c => <tr key={c.index}><th scope="row">{num(c.scale)}{c.index === evidence.selected_index ? "（已选）" : ""}</th><td>{c.executed ? "是" : "否"}</td><td>{c.eligible ? "通过" : "未通过"}</td><td>{c.reasons.join("；")}{c.stress_outcomes.map(s => <div key={s.id}>{s.id}：{s.executable ? s.eligible ? "通过" : "未通过" : "未执行"}{s.reasons.length ? `（${s.reasons.join("；")}）` : ""}</div>)}</td></tr>)}</tbody></table></div>
    {evidence.stress_runs.length > 0 && <details><summary>查看每个 T2 与 B0/B1 场景的数值</summary><div className={styles.scroll}><table><caption>细化后的图像目标与数值差异</caption><thead><tr><th>候选 / T2 / 场景</th><th>图像差值 (a.u.)</th><th>信号 / 图像细化差 (a.u.)</th><th>目标 / 细化</th></tr></thead><tbody>{evidence.stress_runs.flatMap(run => run.result.candidates.flatMap(c => c.scenarios.map(s => <tr key={`${run.id}-${c.index}-${s.id}`}><th scope="row">{c.index + 1} / {run.id} / {s.id}</th><td>{num(s.refined.validation.image_target?.measured)}</td><td>{num(s.max_signal_difference)} / {num(s.max_image_difference)}</td><td>{s.target_passed ? "通过" : "未通过"} / {s.refinement_passed ? "通过" : "未通过"}</td></tr>)))}</tbody></table></div></details>}
    <p>局部 T2 矩形角点与有限 B0/B1 情景是压力测试，不是联合置信区间或临床质量认证。</p>
  </section>;
}
