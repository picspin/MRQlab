"use client";
import React, { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { createScientificRecord, fetchFlowStudyExample, importFlowVelocity, replayScientificRecord } from "../../../lib/api";
import type { FlowStudyInput, FlowStudyResult } from "../../../lib/flow-study";
import type { ScientificResponse } from "../../../lib/scientific-records";
import Measurements from "../../../components/research/Measurements";
import styles from "../research.module.css";

const format = (n: number | null | undefined) => n == null ? "未计算" : n.toPrecision(5);
function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob), link = document.createElement("a");
  link.href = url; link.download = name; document.body.appendChild(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function FlowStudyPage() {
  const [draft, setDraft] = useState(""), [studyId, setStudyId] = useState("velocity-dir-pilot");
  const [origin, setOrigin] = useState<"measured" | "synthetic" | "">(""), [source, setSource] = useState("");
  const [response, setResponse] = useState<ScientificResponse | null>(null);
  const [busy, setBusy] = useState(false), [message, setMessage] = useState(""), [error, setError] = useState("");
  const generation = useRef(0), controller = useRef<AbortController | null>(null);
  useEffect(() => () => { generation.current++; controller.current?.abort(); }, []);
  function reset() { generation.current++; controller.current?.abort(); setBusy(false); setResponse(null); setError(""); setMessage(""); }
  function parse(): FlowStudyInput {
    const value: unknown = JSON.parse(draft);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("研究输入必须是 JSON 对象。");
    return value as FlowStudyInput;
  }
  async function perform(action: (signal: AbortSignal) => Promise<void>) {
    controller.current?.abort(); const active = new AbortController(); controller.current = active;
    const id = ++generation.current; setBusy(true); setError(""); setMessage(""); setResponse(null);
    try { await action(active.signal); }
    catch (caught) { if (generation.current === id && !active.signal.aborted) setError(caught instanceof Error ? caught.message : "流动研究操作失败。"); }
    finally { if (generation.current === id) setBusy(false); }
  }
  async function loadExample(signal: AbortSignal) {
    const input = await fetchFlowStudyExample(signal); if (signal.aborted) return;
    setDraft(JSON.stringify(input, null, 2)); setOrigin("synthetic"); setSource(input.dataset.source_ref);
    setMessage("已载入合成速度 CSV 示例；没有导入患者或扫描仪数据。");
  }
  async function loadCSV(file?: File) {
    if (!file) return;
    await perform(async signal => {
      if (!origin || !source.trim()) throw new Error("先声明速度测量来源及实测/合成类型。");
      if (file.size > 1000000) throw new Error("速度 CSV 不能超过 1 MB。");
      const input = parse(), bytes = new Uint8Array(await file.arrayBuffer()); if (signal.aborted) return;
      const chunks: string[] = [];
      for (let start = 0; start < bytes.length; start += 8192) chunks.push(String.fromCharCode(...Array.from(bytes.subarray(start, start + 8192))));
      const dataset = await importFlowVelocity({ csv_base64: btoa(chunks.join("")), source_ref: source, origin }, signal);
      if (signal.aborted) return;
      setDraft(JSON.stringify({ ...input, dataset }, null, 2)); setMessage("已保留 CSV 原始字节与哈希；来源为用户声明，尚未校准或验证。");
    });
  }
  async function execute(signal: AbortSignal) {
    const study = parse();
    const result = await createScientificRecord({ context: { study_id: studyId, research_question: study.research_question, target_rationale: study.target_rationale }, execution: { type: "measured_flow", study } }, signal);
    if (signal.aborted) return;
    setResponse(result); setMessage("计算及本地保存完成；校准通过与设计目标通过分别报告。尚未执行独立计算回放。");
  }
  async function replay(signal: AbortSignal, saved: ScientificResponse) {
    const result = await replayScientificRecord(saved.record.record_sha256, signal); if (signal.aborted) return;
    if (!result.computational_replay_performed) throw new Error("后端没有完成计算回放。");
    setResponse(saved); setMessage("完整计算回放一致：原始测量、压力校准、全部场景和目标结果匹配。");
  }
  function downloadCSV() {
    try {
      const d = parse().dataset; if (!d.raw_csv_base64) throw new Error("当前输入没有归档的原始 CSV。");
      download(new Blob([Uint8Array.from(atob(d.raw_csv_base64), c => c.charCodeAt(0))], { type: "text/csv" }), "mrqlab-velocity.csv");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "无法导出 CSV。"); }
  }
  const result = useMemo(() => response ? (JSON.parse(response.record.payload_json) as { flow_study: FlowStudyResult }).flow_study : null, [response]);
  const fit = result?.calibration;
  return <div className={styles.workbench}>
    <header className={styles.heading}><div><h1>速度测量到 DIR 设计验证</h1><p>速度 CSV  --  条件压力校准  --  有限选层 RF  --  因果门控  --  完整回放</p></div><Link href="/research" className={styles.scope}>脉冲设计研究台</Link></header>
    <p className={styles.boundary}>教学 / 研究仿真；不作为扫描仪验证或临床质量认证。B/C 保持 parked。</p>
    <div className={styles.instrument}>
      <section className={styles.design} aria-label="速度测量与设计输入">
        <h2>测量与先验</h2><p>刚性圆管、牛顿流体、已知频率的一阶谐波 Womersley 模型。半径、密度、黏度、时钟及组织 T1/T2 为显式先验。</p>
        <button disabled={busy} onClick={() => void perform(loadExample)}>载入合成速度示例</button>
        <label>研究编号<input value={studyId} onChange={event => { reset(); setStudyId(event.target.value); }} /></label>
        <label>完整流动研究 JSON<textarea aria-label="流动研究 JSON" rows={18} spellCheck={false} value={draft} onChange={event => { reset(); setDraft(event.target.value); }} /></label>
        <div className={styles.actions}><button disabled={!draft || busy} onClick={downloadCSV}>下载当前原始 CSV</button></div>
        <details><summary>导入速度 CSV</summary><p>固定 SI 列名：measurement_id、acquisition_id、split、time_s、radius_m、velocity_m_s、std_m_s。calibration / holdout 的采集 ID 必须独立，时间须与触发序列对齐。</p>
          <label>速度数据类型<select value={origin} onChange={event => { reset(); setOrigin(event.target.value as typeof origin); }}><option value="">请选择来源</option><option value="measured">实测数据（用户声明）</option><option value="synthetic">合成数据</option></select></label>
          <label>速度来源标识<input value={source} onChange={event => { reset(); setSource(event.target.value); }} /></label>
          <label>速度 CSV<input type="file" accept=".csv,text/csv" disabled={!draft || !origin || !source.trim() || busy} onChange={event => void loadCSV(event.target.files?.[0])} /></label>
        </details>
        <div className={styles.actions}><button disabled={!draft || !studyId.trim() || busy} onClick={() => void perform(execute)}>{busy ? "计算中…" : "校准、验证并保存"}</button></div>
        <div className={styles.limits}><h3>不确定性与验证范围</h3><p>校准仅使用 calibration 速度，已知独立高斯测量误差；holdout 独立检查。均值、余弦、正弦压力系数的完整协方差保存在记录。</p><p>名义值及 8 个边际标准差矩形角点均执行粗细网格 DIR。角点检查不是联合置信区间或连续稳健性保证；未通过时没有已选设计。</p></div>
      </section>
      <section className={styles.output} aria-label="流动校准与验证证据" aria-busy={busy}>
        <h2>压力校准与设计证据</h2><p role="status" className={styles.status}>{message || (busy ? "执行后端校准、留出检查及全部不确定性场景…" : "载入合成示例或声明实验来源后导入速度测量。")}</p>
        {error && <p role="alert" className={styles.error}>{error}</p>}
        {result && fit && response && <>
          <p className={fit.passed ? styles.passed : styles.failed}>校准与独立留出：{fit.passed ? "通过" : "未通过"}</p>
          <p className={result.validation.selected_design_passed ? styles.passed : styles.failed}>{result.validation.selected_design_passed ? `已选设计：${result.selected_index}` : "未选出通过验证的设计"}</p>
          <p>数据来源：{result.provenance.input_origin === "synthetic" ? "合成数据" : "实测数据（用户声明）"}；{result.provenance.source_ref}</p>
          {fit.reasons.map(reason => <p key={reason} className={styles.failed}>{reason}</p>)}
          <table><caption>条件压力系数（Pa/m）与标准差</caption><thead><tr><th>分量</th><th>估计</th><th>标准差</th></tr></thead><tbody>{["均值", "余弦", "正弦"].map((name, i) => <tr key={name}><th scope="row">{name}</th><td>{format(fit.coefficients_pa_m?.[i])}</td><td>{format(fit.std_pa_m?.[i])}</td></tr>)}</tbody></table>
          <p>校准 χ²/(n−3)：{format(fit.calibration_reduced_chi2)}；留出最大 |z|：{format(fit.holdout_max_standardized_residual)}；留出 χ²/n：{format(fit.holdout_reduced_chi2)}</p>
          <table><caption>全部候选及压力场景</caption><thead><tr><th>TI (s)</th><th>完成场景</th><th>数值检查通过</th><th>最差观测差异</th><th>设计目标</th></tr></thead><tbody>{result.candidates.map(p => {
            const errors = p.scenarios.flatMap(s => typeof s.max_observation_refinement_error === "number" ? [s.max_observation_refinement_error] : []);
            return <tr key={p.index}><td>{p.design.inversion_time_s}</td><td>{p.scenarios.filter(s => s.completed).length}/9</td><td>{p.scenarios.filter(s => s.numerical_refinement_passed).length}/9</td><td>{format(errors.length ? Math.max(...errors) : null)}</td><td>{p.eligible ? "通过" : "未通过"}<div>{p.reasons.join("；")}</div></td></tr>;
          })}</tbody></table>
          {response.view && <><h3>{result.selected_index == null ? `未选中预览：候选 ${result.preview_index} 的名义压力 / 细网格` : "已选设计的名义压力 / 细网格"}</h3><Measurements view={response.view} validationLabel="此名义压力场景的物理目标" /></>}
          <div className={styles.provenance}><h3>原始数据与完整计算记录</h3><p>原始 CSV SHA256：{result.provenance.raw_file_sha256 ?? "未提供原始 CSV 归档"}</p><p>工作量：{result.provenance.estimated_work} / 预留 {result.provenance.reserved_work}</p><p>记录：{response.record.record_sha256}</p>
            <div className={styles.actions}><button disabled={busy} onClick={() => void perform(signal => replay(signal, response))}>回放完整流动研究</button><button onClick={() => download(new Blob([JSON.stringify(response.record)], { type: "application/json" }), `mrqlab-flow-${response.record.record_sha256.slice(0, 12)}.json`)}>下载完整流动记录</button></div>
            <Link href="/research/records">在本地实验记录中导入、核验与回放</Link>
          </div>
        </>}
      </section>
    </div>
  </div>;
}
