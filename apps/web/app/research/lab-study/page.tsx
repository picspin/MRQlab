"use client";
import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { fetchLabStudyExample, importLabEchoes, replayLabStudy, runLabStudy } from "../../../lib/api";
import type { LabStudyRecord, LabStudyResponse, StudyInput } from "../../../lib/lab-study";
import Measurements from "../../../components/research/Measurements";
import styles from "../research.module.css";
const format = (n: number) => n.toPrecision(5);

export default function LabStudyPage() {
  const [draft, setDraft] = useState("");
  const [response, setResponse] = useState<LabStudyResponse | null>(null);
  const [imported, setImported] = useState<LabStudyRecord | null>(null);
  const [origin, setOrigin] = useState<"measured" | "synthetic" | "">("");
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const current = useRef(0), controller = useRef<AbortController | null>(null);
  useEffect(() => () => { current.current++; controller.current?.abort(); }, []);
  function reset() { current.current++; controller.current?.abort(); setBusy(false); setResponse(null); setImported(null); setError(""); setMessage(""); }
  function edit(value: string) { reset(); setDraft(value); }
  function parse(): StudyInput {
    const value: unknown = JSON.parse(draft);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("研究输入必须是 JSON 对象。");
    return value as StudyInput;
  }
  async function perform(action: (signal: AbortSignal) => Promise<void>) {
    controller.current?.abort(); const active = new AbortController(); controller.current = active;
    const id = ++current.current; setBusy(true); setError(""); setResponse(null); setMessage("");
    try { await action(active.signal); }
    catch (caught) { if (id === current.current && !active.signal.aborted) setError(caught instanceof Error ? caught.message : "请求失败。"); }
    finally { if (id === current.current) setBusy(false); }
  }
  async function loadExample(signal: AbortSignal) {
    const input = await fetchLabStudyExample(signal); if (signal.aborted) return;
    setDraft(JSON.stringify(input, null, 2)); setImported(null); setOrigin("synthetic");
    setMessage("已载入明确标记的合成 CPMG 示例。它不代表实际实验数据。");
  }
  async function execute(signal: AbortSignal, replay?: LabStudyRecord) {
    const result = replay ? await replayLabStudy(replay, signal) : await runLabStudy(parse(), signal);
    if (signal.aborted) return;
    setResponse(result); setImported(null);
    setMessage(replay ? "完整计算回放一致：测量、校准、全部候选和验证记录均匹配。" : "校准、独立验证与候选设计检查已完成。未通过时不返回已选设计。");
  }
  async function loadRecord(file?: File) {
    if (!file) return; reset(); const id = current.current;
    try {
      if (file.size > 16000000) throw new Error("单个研究记录不能超过 16 MB。");
      const record = JSON.parse(await file.text()) as LabStudyRecord;
      if (id !== current.current) return;
      if (record.schema_version !== "mrqlab-study-record-1" || !record.request || !/^[a-f0-9]{64}$/.test(record.record_sha256)) throw new Error("不是有效的实验研究记录。");
      setImported(record); setDraft(JSON.stringify(record.request, null, 2));
      setMessage("记录已载入，尚未验证。执行计算回放会检查完整性、源码、运行环境和数值结果。");
    } catch (caught) { if (id === current.current) setError(caught instanceof Error ? caught.message : "无法读取记录。"); }
  }
  async function loadCSV(file?: File) {
    if (!file) return;
    await perform(async signal => {
      if (!origin || !source.trim()) throw new Error("先声明测量来源和实测/合成标记。");
      if (file.size > 1000000) throw new Error("测量 CSV 不能超过 1 MB。");
      const input = parse(); const bytes = new Uint8Array(await file.arrayBuffer()); if (signal.aborted) return;
      const chunks: string[] = [];
      for (let start = 0; start < bytes.length; start += 8192) chunks.push(String.fromCharCode(...Array.from(bytes.subarray(start, start + 8192))));
      const encoded = btoa(chunks.join(""));
      const previous = input.dataset as { echo_spacing_s?: number; tr_s?: number } | undefined;
      const dataset = await importLabEchoes({ csv_base64: encoded, source_ref: source, origin,
        echo_spacing_s: previous?.echo_spacing_s ?? .008, tr_s: previous?.tr_s ?? .4 }, signal);
      if (signal.aborted) return;
      setDraft(JSON.stringify({ ...input, dataset }, null, 2)); setImported(null);
      setMessage("测量已导入并保留原文件哈希；运行前仍需通过组织绑定和独立留出检查。");
    });
  }
  function download(record: LabStudyRecord) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = `mrqlab-study-${record.record_sha256.slice(0, 12)}.json`;
    document.body.appendChild(link); link.click(); link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const record = response?.record;
  const dataset = record?.request.dataset as { origin: string; source_ref: string } | undefined;
  return <div className={styles.workbench}>
    <header className={styles.heading}><div><h1>从实验测量到设计验证</h1><p>独立 CPMG 数据校准 T2，再通过既有 EPG / TSE / PSF 链比较脉冲设计。</p></div><Link href="/research" className={styles.scope}>脉冲设计研究台</Link></header>
    <p className={styles.boundary}>教学 / 研究仿真。不是扫描仪验证或临床质量认证；B/C 保持 parked。当前支持两类组织的理想 180° CPMG 测量。</p>
    <div className={styles.instrument}>
      <section className={styles.design} aria-label="实验数据与设计">
        <h2>实验输入</h2><p>使用既有 ExperimentGraph 声明研究问题、T1/PD 先验、组织绑定、候选及目标。校准只更新 T2。</p>
        <button disabled={busy} onClick={() => void perform(loadExample)}>载入合成示例</button>
        <label>完整实验与测量 JSON<textarea aria-label="实验研究 JSON" rows={18} value={draft} onChange={event => edit(event.target.value)} spellCheck={false} /></label>
        <details><summary>导入实验测量 CSV</summary><p>列名固定为 measurement_id、acquisition_id、tissue_id、split、echo_time_s、signal_a_u、std_a_u。split 使用 calibration / holdout；采集 ID 必须独立。</p>
          <label>数据类型<select aria-label="测量数据类型" value={origin} onChange={event => { reset(); setOrigin(event.target.value as typeof origin); }}><option value="">请选择来源</option><option value="measured">实测数据（用户声明）</option><option value="synthetic">合成数据</option></select></label>
          <label>来源标识<input aria-label="测量来源标识" value={source} onChange={event => { reset(); setSource(event.target.value); }} placeholder="实验记录编号或本地来源" /></label>
          <label>测量 CSV<input type="file" accept=".csv,text/csv" disabled={!draft || !origin || !source.trim() || busy} onChange={event => void loadCSV(event.target.files?.[0])} /></label>
        </details>
        <div className={styles.actions}><button disabled={busy || !draft} onClick={() => void perform(signal => execute(signal, imported ?? undefined))}>{busy ? "计算中…" : imported ? "执行完整计算回放" : "校准并验证设计"}</button></div>
        <label>导入研究记录<input type="file" accept=".json,application/json" onChange={event => void loadRecord(event.target.files?.[0])} /></label>
        <div className={styles.limits}><h3>校准与验证边界</h3><p>带已知标准差的独立高斯噪声、有符号实数信号和单指数 T2。使用独立采集的留出数据；不拟合重建图像增益。</p><p>T2 标准不确定度为局部线性近似；矩形角点是压力测试，不是联合置信区间。T1、PD 和临床迁移有效性没有从这些数据得到校准。</p></div>
      </section>
      <section className={styles.output} aria-label="校准与设计证据" aria-busy={busy}>
        <h2>校准、独立验证与设计选择</h2><p role="status" className={styles.status}>{message || (busy ? "后端执行测量模型、留出检查与完整候选网格…" : "等待明确来源的测量或合成示例。")}</p>
        {error && <p role="alert" className={styles.error}>{error}</p>}
        {record && <>
          <p>{record.result.clinical_question.research_question}</p>
          {dataset && <p>数据来源：{dataset.origin === "synthetic" ? "合成示例" : "实测（用户声明）"}；{dataset.source_ref}</p>}
          <p className={record.result.validation.selected_design_passed ? styles.passed : styles.failed}>{record.result.validation.selected_design_passed ? "研究设计目标通过" : "未选出通过验证的设计"}</p>
          <div className={styles.scroll}><table><caption>T2 校准与独立留出</caption><thead><tr><th>组织</th><th>T2 (ms)</th><th>标准不确定度 (ms)</th><th>留出最大标准化残差</th><th>模型检查</th></tr></thead><tbody>{record.result.calibration.map(fit => <tr key={fit.tissue_id}><td>{fit.tissue_id}</td><td>{format(fit.t2_s * 1000)}</td><td>{fit.t2_std_s === null ? "不可辨识" : format(fit.t2_std_s * 1000)}</td><td>{format(fit.holdout_max_standardized_residual)}</td><td>{fit.passed ? "通过" : fit.reasons.join("；")}</td></tr>)}</tbody></table></div>
          <div className={styles.scroll}><table><caption>名义参数与全部 T2 不确定性角点</caption><thead><tr><th>设计</th><th>最差 PSF RMS (voxel)</th><th>满足全部目标</th><th>说明</th></tr></thead><tbody>{record.result.candidates.map(point => <tr key={point.index}><td>{JSON.stringify(point.design)}</td><td>{point.worst_psf_rms_voxels === undefined ? "未完成" : format(point.worst_psf_rms_voxels)}</td><td>{point.eligible ? "是" : "否"}</td><td>{point.index === record.result.selected_index ? "已选设计" : point.reasons.join("；")}</td></tr>)}</tbody></table></div>
          {response.view && <><h3>已选设计的图像与回波</h3><Measurements view={response.view} validationLabel="与理想均值参考图像一致性" /></>}
          <section className={styles.provenance}><h3>完整研究记录</h3><p>{record.result.scope}</p><p>模拟工作量 {record.result.provenance.estimated_work}；保守预算预留 {record.result.provenance.reserved_work}。RF 指标为教学能量代理，不是 SAR。</p><dl><dt>源码与依赖清单</dt><dd>{record.sources.sha256}</dd><dt>结果哈希</dt><dd>{record.result_sha256}</dd><dt>记录哈希</dt><dd>{record.record_sha256}</dd></dl>
            <div className={styles.actions}><button disabled={busy} onClick={() => void perform(signal => execute(signal, record))}>回放完整研究</button><button onClick={() => download(record)}>导出研究记录</button></div>
            <details><summary>完整记录 JSON（可复制保存）</summary><textarea aria-label="完整研究记录 JSON" readOnly rows={16} value={JSON.stringify(record, null, 2)} /></details>
            <details><summary>阶段依赖与实际阈值</summary><pre>{JSON.stringify({ stages: record.result.provenance.stages, targets: record.result.targets, validation: record.result.validation, runtime: record.runtime }, null, 2)}</pre></details>
          </section>
        </>}
      </section>
    </div>
  </div>;
}
