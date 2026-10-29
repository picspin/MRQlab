"use client";
import React, { useEffect, useRef, useState } from "react";
import { createScientificRecord } from "../../lib/api";
import type { ScientificRecord, ScientificResponse } from "../../lib/scientific-records";
import styles from "../../app/research/research.module.css";

export function DeriveRadialStudy({ parent, onCreated }: { parent: ScientificRecord; onCreated: (response: ScientificResponse) => void | Promise<void> }) {
  const [question, setQuestion] = useState("校准 T2 不确定性下，哪些径向 TSE 设计能通过固定重建先验的全部目标？");
  const [rationale, setRationale] = useState("");
  const [draft, setDraft] = useState(JSON.stringify({ candidates: [{}, { refocusing_angle: 140, refocusing_end_angle: 110 }] }, null, 2));
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);
  async function derive() {
    const controller = new AbortController(); active.current?.abort(); active.current = controller;
    setBusy(true); setError("");
    try {
      const study: unknown = JSON.parse(draft);
      if (!study || typeof study !== "object" || Array.isArray(study)) throw new Error("候选与预算必须是 JSON 对象。");
      const response = await createScientificRecord({ context: { study_id: parent.summary.study_id, research_question: question.trim(), target_rationale: rationale.trim(), intended_use: "research",
        assumptions: "采用父实验的 T2 秒单位校准与局部矩形角点；T1/PD 为作者先验；重建基组在名义 T2 固定。" },
        execution: { type: "calibrated_radial_tse", parent_record_sha256: parent.record_sha256, study: study as Record<string, unknown> } }, controller.signal);
      if (!controller.signal.aborted) await onCreated(response);
    } catch (caught) { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "派生实验失败。"); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  return <section className={styles.provenance} aria-label="从测量派生径向 TSE">
    <h3>从测量派生径向 TSE</h3><p>重新核对父实验数值结果，按组织编号绑定 T2 与不确定性；每个角点只改变样本 T2，重建基组固定在名义值。默认保留 1e-6 图像与组分目标。</p>
    <p>包含父实验重新计算和全部候选的五个情景，计算可能比单次运行更久。RF 代理计入准备与采集，仍不是 SAR。</p>
    <div className={styles.recordFields}>
      <label>派生研究问题<textarea rows={2} disabled={busy} value={question} onChange={e => setQuestion(e.target.value)} /></label>
      <label>派生目标依据<textarea rows={2} disabled={busy} value={rationale} onChange={e => setRationale(e.target.value)} placeholder="说明为何使用这些目标和不确定性压力情景" /></label>
      <details><summary>径向候选与数值预算</summary><textarea aria-label="派生候选 JSON" rows={10} disabled={busy} value={draft} onChange={e => setDraft(e.target.value)} /></details>
    </div>
    <button disabled={busy || !question.trim() || !rationale.trim()} onClick={() => void derive()}>{busy ? "正在计算固定先验情景…" : "计算并保存派生实验"}</button>
    {error && <p role="alert" className={styles.error}>{error}</p>}
  </section>;
}

interface Derivation {
  parameter_bindings: { tissue_id: string; value: number; unit: string; standard_uncertainty_s: number; stress_interval_s: number[] }[];
  validation: { calibration_and_holdout_passed: boolean; parent_result_revalidated: boolean; calibrated_parameters_applied: boolean; complete_budgeted_search: boolean; selected_design_passed: boolean };
  provenance: { estimated_work: number; reserved_work: number; planned_work: number };
  candidates: { index: number; scenarios: { name: string; sample_t2_s: number[]; basis_t2_s: number[]; executable: boolean; passed: boolean; reason?: string;
    run?: { quality: { nrmse: number }; validation: { coefficient_error: number } } }[] }[];
}
const number = (value: number | undefined) => typeof value === "number" && Number.isFinite(value) ? value.toPrecision(5) : "未计算";
const milliseconds = (values: number[]) => values.map(v => number(v * 1000)).join(" / ");
export function DerivedRadialEvidence({ evidence }: { evidence: Derivation }) {
  return <section className={styles.provenance} aria-label="校准参数与固定先验证据">
    <h3>校准参数与固定先验证据</h3>
    <p>父实验数值重核：{evidence.validation.parent_result_revalidated ? "一致" : "不一致"}；校准与留出：{evidence.validation.calibration_and_holdout_passed ? "通过" : "未通过"}；参数采用：{evidence.validation.calibrated_parameters_applied ? "已绑定" : "未采用"}。</p>
    <p>原父记录保留自己的源码和环境。这里核对原测量产生的数值结果；没有把父记录改标为当前源码。</p>
    <div className={styles.scroll}><table><caption>T2 参数绑定（记录单位为秒）</caption><thead><tr><th>组织</th><th>名义 T2 (ms)</th><th>标准不确定度 (ms)</th><th>压力区间 (ms)</th></tr></thead><tbody>{evidence.parameter_bindings.map(binding => <tr key={binding.tissue_id}><td>{binding.tissue_id}</td><td>{number(binding.value * 1000)}</td><td>{number(binding.standard_uncertainty_s * 1000)}</td><td>{milliseconds(binding.stress_interval_s)}</td></tr>)}</tbody></table></div>
    {!evidence.parameter_bindings.length && <p>没有校准参数被采用。</p>}
    <p>局部矩形角点用于压力测试，不是联合置信区间或临床界限。T1/PD 仍为父实验作者先验。</p>
    <div className={styles.scroll}><table><caption>全部固定基组情景</caption><thead><tr><th>候选 / 情景</th><th>样本 T2 (ms)</th><th>固定基组 T2 (ms)</th><th>图像 NRMSE</th><th>组分 NRMSE</th><th>全部目标</th></tr></thead><tbody>{evidence.candidates.flatMap(candidate => candidate.scenarios.map(row => <tr key={`${candidate.index}-${row.name}`}><td>{candidate.index + 1} / {row.name}</td><td>{milliseconds(row.sample_t2_s)}</td><td>{milliseconds(row.basis_t2_s)}</td><td>{number(row.run?.quality.nrmse)}</td><td>{number(row.run?.validation.coefficient_error)}</td><td>{row.executable ? row.passed ? "通过" : "未通过" : row.reason ?? "不可执行"}</td></tr>))}</tbody></table></div>
    <p>工作量 {evidence.provenance.estimated_work}；已预留 {evidence.provenance.reserved_work}；完整计划需 {evidence.provenance.planned_work}。完整情景预算：{evidence.validation.complete_budgeted_search ? "已覆盖" : "未覆盖"}。</p>
  </section>;
}
