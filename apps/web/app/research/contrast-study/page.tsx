"use client";
import React, { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { createScientificRecord, fetchContrastStudyExample, replayScientificRecord } from "../../../lib/api";
import type { ScientificPlan, ScientificResponse } from "../../../lib/scientific-records";
import { linkedRun, type LinkedReadout, type TSEEdit } from "../../../lib/linked-readout";
import Measurements from "../../../components/research/Measurements";
import styles from "../research.module.css";

const format = (value: number) => value.toPrecision(5);
const LABELS: Record<TSEEdit["field"], string> = { "rf.refocusing_start_deg": "起始重聚焦角", "rf.refocusing_end_deg": "末端重聚焦角", "timing.tr_s": "TR", "timing.echo_spacing_s": "回波间隔", "encoding.order": "理想 ky 编码顺序", "tissue.concentration_mmol_l": "组织浓度" };
const controlKey = (c: LinkedReadout["controls"][number]) => `${c.field}:${c.tissue_id ?? ""}`;
function download(value: unknown, name: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value)], { type: "application/json" })), link = document.createElement("a");
  link.href = url; link.download = name; document.body.appendChild(link); link.click(); link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function ContrastStudyPage() {
  const [draft, setDraft] = useState(""), [response, setResponse] = useState<ScientificResponse | null>(null);
  const [changes, setChanges] = useState<Record<string, string>>({}), [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [message, setMessage] = useState("");
  const generation = useRef(0), controller = useRef<AbortController | null>(null);
  useEffect(() => () => { generation.current++; controller.current?.abort(); }, []);
  function cancel() { generation.current++; controller.current?.abort(); setBusy(false); setError(""); setMessage(""); setVisible(false); }
  const run = useMemo(() => response ? linkedRun(response) : null, [response]);
  const pair = run?.result.linked_readout as LinkedReadout | undefined;
  async function perform(action: (signal: AbortSignal) => Promise<void>) {
    controller.current?.abort(); const active = new AbortController(); controller.current = active;
    const id = ++generation.current; setBusy(true); setError(""); setMessage(""); setVisible(false);
    try { await action(active.signal); }
    catch (caught) { if (generation.current === id && !active.signal.aborted) setError(caught instanceof Error ? caught.message : "组织状态研究失败。"); }
    finally { if (generation.current === id) setBusy(false); }
  }
  function accept(value: ScientificResponse) { setResponse(value); setChanges({}); setVisible(true); }
  async function loadExample(signal: AbortSignal) {
    const plan = await fetchContrastStudyExample(signal); if (signal.aborted) return;
    setDraft(JSON.stringify(plan, null, 2)); setResponse(null); setChanges({}); setMessage("已载入合成结构、浓度及弛豫率系数；没有患者数据或临床剂量建议。");
  }
  async function baseline(signal: AbortSignal) {
    const plan = JSON.parse(draft) as ScientificPlan;
    if (!plan || plan.execution?.type !== "run" || plan.execution.kind !== "tse") throw new Error("基线须为 TSE 科学计划；修改使用已保存父记录。");
    const result = await createScientificRecord(plan, signal); if (signal.aborted) return;
    accept(result); setMessage("基线已保存。图像与完整复数信号来自同一次计算；模型目标结果单独报告。");
  }
  async function apply(signal: AbortSignal) {
    if (!response || !pair) throw new Error("先计算并保存父图像 / 信号记录。");
    const updates: TSEEdit[] = pair.controls.filter(c => controlKey(c) in changes && changes[controlKey(c)] !== String(c.value)).map(c => {
      const text = changes[controlKey(c)], value = c.field === "encoding.order" ? text : Number(text);
      if (!text.trim() || (typeof value === "number" && !Number.isFinite(value))) throw new Error("请输入有限且有明确单位的参数。");
      return { field: c.field, value, ...(c.tissue_id ? { tissue_id: c.tissue_id } : {}) };
    });
    if (!updates.length) throw new Error("没有参数变化。");
    const context = (JSON.parse(response.record.request_json) as ScientificPlan).context;
    const result = await createScientificRecord({ context, execution: { type: "edited_tse", parent_record_sha256: response.record.record_sha256, updates } }, signal);
    if (signal.aborted) return;
    accept(result); setMessage("父记录已完整重算，参数修改已生成新的图像 / 信号记录。父记录保持不变；这不表示设计目标通过。");
  }
  async function replay(signal: AbortSignal) {
    if (!response) return;
    const checked = await replayScientificRecord(response.record.record_sha256, signal); if (signal.aborted) return;
    if (!checked.computational_replay_performed || checked.record_sha256 !== response.record.record_sha256) throw new Error("服务器未确认完整回放一致。");
    setVisible(true); setMessage("完整回放一致：父记录、类型化修改、图像与复数信号全部匹配。");
  }
  const changed = Object.keys(changes).length > 0;
  return <div className={styles.workbench}>
    <header className={styles.heading}><div><h1>组织状态与图像 / 信号</h1><p>相同参数、相同计算：人可读的 MR 仿真图像与 Agent 可读的完整复数信号。</p></div><Link href="/research" className={styles.scope}>脉冲设计研究台</Link></header>
    <p className={styles.boundary}>教学 / 研究模型；合成结构不代表真实解剖。不是患者诊断、剂量建议、扫描仪验证或临床质量认证。B/C 保持 parked。</p>
    <div className={styles.instrument}>
      <section className={styles.design} aria-label="组织与脉冲控制">
        <h2>声明组织状态</h2><p>有效 R1 / R2 = 基线 1/T1 / 1/T2 + 对应弛豫率系数 × 组织浓度。系数仅适用于声明的磁场、温度、介质及浓度范围。</p>
        <button disabled={busy} onClick={() => void perform(loadExample)}>载入合成对比剂示例</button>
        <details><summary>完整基线计划与来源</summary><label>基线科学计划<textarea aria-label="对比剂基线计划" value={draft} rows={16} spellCheck={false} onChange={event => { cancel(); setDraft(event.target.value); setResponse(null); setChanges({}); }} /></label></details>
        <div className={styles.actions}><button disabled={busy || !draft} onClick={() => void perform(baseline)}>运行并保存基线</button></div>
        {pair && <><h2>基于当前父记录修改</h2><p>这些控件与 Agent 使用同一个类型化修改契约。提交后重新计算全部输出，不直接修改图像或信号数组；最多连续修改三代。</p>
          {pair.controls.map(c => <label key={controlKey(c)}>{LABELS[c.field]}{c.tissue_id ? ` · ${c.tissue_id}` : ""} ({c.unit})
            {c.field === "encoding.order" ? <select aria-label={LABELS[c.field]} value={changes[controlKey(c)] ?? String(c.value)} onChange={event => { cancel(); setChanges(previous => ({ ...previous, [controlKey(c)]: event.target.value })); }}><option value="centric">centric</option><option value="linear">linear</option></select> : <input aria-label={`${LABELS[c.field]}${c.tissue_id ? ` ${c.tissue_id}` : ""}`} type="number" step="any" min={c.min} max={c.max} value={changes[controlKey(c)] ?? String(c.value)} onChange={event => { cancel(); setChanges(previous => ({ ...previous, [controlKey(c)]: event.target.value })); }} />}
          </label>)}
          <div className={styles.actions}><button disabled={busy || !changed} onClick={() => void perform(apply)}>重算父记录并应用修改</button></div>
        </>}
        <div className={styles.limits}><h3>当前物理范围</h3><p>复用周期 EPG、理想硬 CPMG 与组织逐回波 Fourier 编码。单个回波中心幅度在整行 ADC 内保持不变；此处不支持物理梯度波形修改或窗内 Bloch 演化。</p><p>当前为静态、均匀每组织浓度；不推断药代动力学、T2* / 磁敏感性或对比剂导致的扩散 / 交换变化。实测标记只表示用户声明。</p></div>
      </section>
      <section className={styles.output} aria-label="关联图像与完整信号" aria-busy={busy}>
        <h2>同源图像与 Signal Vector</h2><p role="status" className={styles.status}>{message || (busy ? "后端执行组织状态绑定、EPG、编码、重建及来源记录…" : changed ? "参数已改变，图像与信号须重算后才能显示。" : "等待明确来源的组织与序列参数。")}</p>
        {error && <p role="alert" className={styles.error}>{error}</p>}
        {visible && pair && run && response && <>
          <p>模型目标报告：<strong className={response.record.summary.model_reported_passed ? styles.passed : styles.failed}>{response.record.summary.model_reported_passed ? "通过" : "未通过"}</strong>。内容完整性及计算回放不替代目标验证。</p>
          <Measurements view={run.view} validationLabel="平坦回波参考图像一致性" />
          <h3>Agent 信号向量</h3><p>完整 {pair.signal_vector.values.real.length} 个复数样本，按实际理想 ADC 顺序排列；网格坐标单位 {pair.signal_vector.coordinate_unit}，时间单位 {pair.signal_vector.time_unit}。</p>
          <p>{pair.signal_vector.timing_model}</p>
          <table><caption>前 8 个样本；完整向量与图像可下载</caption><thead><tr><th>样本</th><th>时间 (s)</th><th>Re</th><th>Im</th><th>网格索引</th></tr></thead><tbody>{pair.signal_vector.values.real.slice(0, 8).map((value, i) => <tr key={i}><td>{i}</td><td>{format(pair.signal_vector.sample_times_s[i])}</td><td>{format(value)}</td><td>{format(pair.signal_vector.values.imag[i])}</td><td>{pair.signal_vector.grid_indices[i].join(", ")}</td></tr>)}</tbody></table>
          <div className={styles.provenance}><h3>来源与双向参数控制</h3><p>{pair.structure.origin}</p><p>图像 / 信号关系 SHA256：{pair.pair_sha256}</p><p>当前记录：{response.record.record_sha256}</p>{response.record.summary.parent_record_sha256 && <p>父记录：{response.record.summary.parent_record_sha256}</p>}
            <details><summary>完整组织状态与物理依据</summary><pre>{JSON.stringify({ design: run.result.design, physical: run.result.provenance.physical }, null, 2)}</pre></details>
            <div className={styles.actions}><button disabled={busy} onClick={() => void perform(replay)}>完整回放当前记录</button><button onClick={() => download(pair, `mrqlab-image-signal-${pair.pair_sha256.slice(0, 12)}.json`)}>下载图像与 Signal Vector</button><button onClick={() => download(response.record, `mrqlab-controlled-tse-${response.record.record_sha256.slice(0, 12)}.json`)}>下载完整父子记录</button></div>
            <Link href={`/research/records?id=${response.record.record_sha256}`}>在本地实验记录中查看、导入与回放</Link>
          </div>
        </>}
      </section>
    </div>
  </div>;
}
