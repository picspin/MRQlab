"use client";
import React, { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { getScientificRecord, importScientificRecord, listScientificRecords, replayScientificRecord } from "../../../lib/api";
import type { ScientificList, ScientificRecord, ScientificResponse } from "../../../lib/scientific-records";
import Measurements from "../../../components/research/Measurements";
import { DeriveRadialStudy, DerivedRadialEvidence } from "../../../components/research/DerivedRadialStudy";
import styles from "../research.module.css";

const EMPTY: ScientificList = { total: 0, offset: 0, limit: 20, records: [] };
const STAGES: Record<string, string> = { question: "研究问题", parent_image_signal_record: "父图像与信号记录", typed_parameter_edits: "类型化参数修改", raw_velocity_measurements: "原始速度测量", conditional_pressure_calibration: "条件压力校准", parent_measurement_record: "父测量记录", design_and_inputs: "设计与输入", source_and_runtime: "源码与环境", computed_execution: "计算与候选", reported_validation: "目标验证" };
export default function ScientificRecordsPage() {
  const [filter, setFilter] = useState("");
  const [listing, setListing] = useState(EMPTY);
  const [response, setResponse] = useState<ScientificResponse | null>(null);
  const [replayed, setReplayed] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [message, setMessage] = useState("");
  const generation = useRef(0), controller = useRef<AbortController | null>(null);
  async function perform(action: (signal: AbortSignal) => Promise<void>) {
    const active = new AbortController(); controller.current?.abort(); controller.current = active;
    const id = ++generation.current; setBusy(true); setError(""); setMessage("");
    try { await action(active.signal); }
    catch (caught) { if (generation.current === id && !active.signal.aborted) setError(caught instanceof Error ? caught.message : "记录操作失败。"); }
    finally { if (generation.current === id) setBusy(false); }
  }
  async function refresh(signal: AbortSignal, offset = 0) {
    const list = await listScientificRecords(filter, offset, signal);
    if (!signal.aborted) setListing(list);
  }
  async function open(id: string, signal: AbortSignal) {
    setResponse(null); setReplayed(false);
    const result = await getScientificRecord(id, signal);
    if (signal.aborted) return;
    setResponse(result); setMessage("记录内容完整性通过。以下是历史报告，尚未在当前环境重算。");
  }
  useEffect(() => {
    void perform(async signal => {
      await refresh(signal);
      const id = new URLSearchParams(window.location.search).get("id");
      if (id && !signal.aborted) await open(id, signal);
    });
    return () => { generation.current++; controller.current?.abort(); };
    // Initial local list and optional record link; filters run only on request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  async function importFile(file?: File) {
    if (!file) return;
    setResponse(null); setReplayed(false);
    await perform(async signal => {
      if (file.size > 64 * 1024 * 1024) throw new Error("导入记录不能超过 64 MiB。较大文件请使用本地 CLI。");
      const record = JSON.parse(await file.text()) as ScientificRecord;
      if (signal.aborted) return;
      const result = await importScientificRecord(record, signal);
      if (signal.aborted) return;
      setResponse(result); setReplayed(false);
      await refresh(signal);
      if (!signal.aborted) setMessage("记录已导入本地，完整性通过；尚未执行科学计算回放。");
    });
  }
  async function replay() {
    if (!response) return; const identity = response.record.record_sha256;
    setReplayed(false);
    await perform(async signal => {
      const checked = await replayScientificRecord(identity, signal);
      if (signal.aborted) return;
      if (!checked.computational_replay_performed || checked.record_sha256 !== identity) throw new Error("服务器未确认完整计算回放一致。");
      setReplayed(true); setMessage("完整计算回放一致：全部结果、候选、阶段与记录哈希匹配。");
    });
  }
  function download() {
    if (!response) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(response.record, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = `mrqlab-record-${response.record.record_sha256.slice(0, 12)}.json`;
    document.body.appendChild(link); link.click(); link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const record = response?.record;
  const derived = useMemo(() => record?.summary.mode === "calibrated_radial_tse" ? JSON.parse(record.payload_json).derivation : null, [record?.payload_json, record?.summary.mode]);
  return <div className={styles.workbench}>
    <header className={styles.heading}><div><h1>本地实验记录</h1><p>把研究问题、设计、模型结果和验证依据保存在同一份可回放记录中。</p></div><Link className={styles.scope} href="/research">脉冲设计研究台</Link></header>
    <p className={styles.boundary}>教学 / 研究用途。历史报告、完整性检查与完整计算回放分别标注；不是扫描仪验证或临床质量认证。B/C 保持 parked。</p>
    <div className={styles.instrument}>
      <section className={styles.design} aria-label="已保存实验">
        <h2>已保存实验</h2><label>筛选实验编号<input value={filter} disabled={busy} onChange={e => setFilter(e.target.value)} placeholder="留空查看全部" /></label>
        <button disabled={busy} onClick={() => void perform(signal => refresh(signal))}>读取记录列表</button>
        <p>共 {listing.total} 条；列表仅为索引，打开后才检查完整记录。</p>
        {!listing.records.length && <p>尚无匹配记录。可在研究台或测量研究完成计算后保存，也可导入已有记录。</p>}
        <ol className={styles.recordList}>{listing.records.map(item => <li key={item.record_sha256}><button disabled={busy} aria-pressed={record?.record_sha256 === item.record_sha256} onClick={() => void perform(signal => open(item.record_sha256, signal))}>
          <strong>{item.summary.study_id}</strong><span>{item.summary.kind}  --  {item.summary.mode}</span><span>{item.summary.research_question}</span><small>历史目标报告：{item.summary.model_reported_passed ? "通过" : "未通过"}；{record?.record_sha256 === item.record_sha256 && replayed ? "当前会话已重算一致" : "尚未重算"}</small>
        </button></li>)}</ol>
        <div className={styles.actions}><button disabled={busy || listing.offset === 0} onClick={() => void perform(signal => refresh(signal, Math.max(0, listing.offset - 20)))}>上一页</button><button disabled={busy || listing.offset + listing.limit >= listing.total} onClick={() => void perform(signal => refresh(signal, listing.offset + 20))}>下一页</button></div>
        <label>导入完整实验记录<input type="file" accept="application/json,.json" disabled={busy} onChange={e => void importFile(e.target.files?.[0])} /></label>
      </section>
      <section className={styles.output} aria-label="记录与回放" aria-busy={busy}>
        <h2>记录与回放</h2><p role="status" className={styles.status}>{message || (busy ? "正在读取或计算…" : record ? "当前记录的完整性与计算回放状态见下方。" : "打开一条记录查看其证据。")}</p>
        {error && <p role="alert" className={styles.error}>{error}</p>}
        {record && <>
          <h3>{record.summary.research_question}</h3>
          <dl className={styles.recordChecks}><dt>内容完整性</dt><dd>已通过哈希检查</dd><dt>模型当时报告的目标</dt><dd>{record.summary.model_reported_passed ? "通过" : "未通过"}</dd><dt>当前环境完整计算回放</dt><dd>{replayed ? "已重算且一致" : "尚未确认"}</dd></dl>
          {record.summary.mode === "search" && record.summary.selected_index === null && <p>原记录未选出设计；全部候选保留在下表。</p>}
          {record.summary.mode === "search" && response.view && <p>下方展示候选 {(record.summary.selected_index ?? record.summary.candidates?.find(point => point.executable)?.index ?? 0) + 1} 的历史测量；展示不会改变原选择。</p>}
          <p>输入来源：{record.summary.input_origins.join("、")}。背景引用不会自动用于校准。</p>
          {record.summary.parent_record_sha256 && <button disabled={busy} onClick={() => void perform(signal => open(record.summary.parent_record_sha256!, signal))}>{record.summary.mode === "edited_tse" ? "打开父图像 / 信号记录" : "打开父测量记录"}</button>}
          <div className={styles.actions}><button disabled={busy} onClick={() => void replay()}>在当前环境完整重算</button><button disabled={busy} onClick={download}>导出完整实验记录</button></div>
          <ol className={styles.recordStages}>{record.stages.map(stage => <li key={stage.sha256}><strong>{STAGES[stage.stage] ?? stage.stage}</strong><code>{stage.sha256}</code></li>)}</ol>
          <div className={styles.scroll}><table><caption>完整候选与模型历史报告</caption><thead><tr><th>候选</th><th>计算完成</th><th>声明目标</th><th>说明</th></tr></thead><tbody>{record.summary.candidates?.map(point => <tr key={point.index}><td>{point.index + 1}{point.index === record.summary.selected_index ? "（原结果）" : ""}</td><td>{point.executable ? "是" : "否"}</td><td>{point.model_reported_passed ? "通过" : "未通过"}</td><td>{point.reasons?.join("；") ?? (point.reason ? JSON.stringify(point.reason) : "")}</td></tr>)}</tbody></table></div>
          {derived && <DerivedRadialEvidence evidence={derived} />}
          {derived && response.view && <p>下图仅展示名义情景的单次逆解；是否通过不确定性验证以上方全部情景为准。</p>}
          {response.view && <><h3>{replayed ? "重算一致的测量" : "历史记录中的测量（尚未重算）"}</h3><Measurements view={response.view} validationLabel={derived ? "仅名义情景的目标报告" : "模型当时的目标报告"} /></>}
          {record.summary.mode === "measured_tse" && <DeriveRadialStudy key={record.record_sha256} parent={record} onCreated={async result => {
            setResponse(result); setReplayed(false);
            await perform(async signal => { await refresh(signal); if (!signal.aborted) setMessage("派生实验已保存；全部不确定性情景的目标结果独立报告。"); });
          }} />}
          <section className={styles.provenance}><h3>可移交的来源与环境</h3><p>{record.summary.scope}</p><dl><dt>记录哈希</dt><dd>{record.record_sha256}</dd><dt>源码与依赖</dt><dd>{record.sources.sha256}</dd><dt>完整计算结果</dt><dd>{record.payload_sha256}</dd></dl>
            <details><summary>问题、设计与输入快照</summary><pre>{record.request_json}</pre></details><details><summary>运行环境与阶段依赖</summary><pre>{JSON.stringify({ runtime: record.runtime, stages: record.stages }, null, 2)}</pre></details>
          </section>
        </>}
      </section>
    </div>
  </div>;
}
