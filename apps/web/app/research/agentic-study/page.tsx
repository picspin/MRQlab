"use client";
import React, { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { createScientificRecord, fetchContrastStudyExample, replayScientificRecord } from "../../../lib/api";
import type { ScientificPlan, ScientificResponse } from "../../../lib/scientific-records";
import { linkedRun, type LinkedReadout } from "../../../lib/linked-readout";
import { agenticInference, decimal, percentage, type AgenticInference } from "../../../lib/agentic-inference";
import Measurements from "../../../components/research/Measurements";
import styles from "../research.module.css";

const format = (value: number) => value.toPrecision(5);
const UNAVAILABLE: Record<string, string> = {
  per_tissue_t2_map: "每组织 T2 图",
  t1_weighted_modality: "T1 加权模态",
  tissue_classification: "组织自动分类",
  per_echo_coefficients: "逐回波组织系数",
  absolute_echo_amplitudes: "每组织绝对回波幅度",
};
function download(value: unknown, name: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value)], { type: "application/json" })), link = document.createElement("a");
  link.href = url; link.download = name; document.body.appendChild(link); link.click(); link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
// Own-property reads only: keys come from untyped JSON, so "__proto__" / "constructor" must never resolve to Object.prototype.
function ownValue<T>(map: Record<string, T>, key: string): T | undefined {
  return Object.prototype.hasOwnProperty.call(map, key) ? map[key] : undefined;
}
function checkLabel(key: string) {
  return ownValue({
    pair_integrity: "图像 / 信号完整性", complete_signal_read: "完整采集信号读取",
    parseval_energy_consistency: "Parseval 能量一致", echo_membership_declared: "回波成员已声明",
    static_partition_linear_model: "静态组织分区线性模型", identifiable_coefficient_basis: "可识别系数基",
    structure_proportions_normalized: "结构比例归一", image_proportions_normalized: "图像比例归一",
    modalities_complete: "模态代理完整",
  } as Record<string, string>, key) ?? key;
}

export default function AgenticStudyPage() {
  const [draft, setDraft] = useState(""), [parent, setParent] = useState<ScientificResponse | null>(null);
  const [response, setResponse] = useState<ScientificResponse | null>(null), [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [message, setMessage] = useState("");
  const generation = useRef(0), controller = useRef<AbortController | null>(null);
  useEffect(() => () => { generation.current++; controller.current?.abort(); }, []);
  function cancel() { generation.current++; controller.current?.abort(); setBusy(false); setError(""); setMessage(""); setResponse(null); }
  const parentRun = useMemo(() => parent ? linkedRun(parent) : null, [parent]);
  const pair = parentRun?.result.linked_readout as LinkedReadout | undefined;
  const inference: AgenticInference | null = response ? agenticInference(response) : null;
  async function perform(action: (signal: AbortSignal) => Promise<void>) {
    controller.current?.abort(); const active = new AbortController(); controller.current = active;
    const id = ++generation.current; setBusy(true); setError(""); setMessage("");
    try { await action(active.signal); }
    catch (caught) { if (generation.current === id && !active.signal.aborted) { setResponse(null); setError(caught instanceof Error ? caught.message : "Agent 信号推断失败。"); } }
    finally { if (generation.current === id) setBusy(false); }
  }
  async function loadExample(signal: AbortSignal) {
    const plan = await fetchContrastStudyExample(signal); if (signal.aborted) return;
    setDraft(JSON.stringify(plan, null, 2)); setParent(null); setReference(""); setResponse(null);
    setMessage("已载入合成结构、序列与对比剂参数；请先运行并保存父记录，再读取其完整采集信号。");
  }
  async function baseline(signal: AbortSignal) {
    setResponse(null);
    const plan = JSON.parse(draft) as ScientificPlan;
    if (!plan || plan.execution?.type !== "run" || plan.execution.kind !== "tse") throw new Error("基线须为 TSE 科学计划；agentic 推断使用已保存父记录。");
    const result = await createScientificRecord(plan, signal); if (signal.aborted) return;
    const run = linkedRun(result), linked = run.result.linked_readout as LinkedReadout | undefined;
    if (!linked || linked.structure.label_to_tissue_id.length < 2) throw new Error("父记录缺少至少两个声明组织的完整图像 / 信号。");
    setParent(result); setReference(linked.structure.label_to_tissue_id[0]); setResponse(null);
    setMessage("父记录已保存；图像与完整复数采集信号来自同一次计算。尚未推断组织模态。");
  }
  async function infer(signal: AbortSignal) {
    setResponse(null);
    if (!parent || !pair) throw new Error("先运行并保存包含完整图像 / 信号父记录。");
    const context = (JSON.parse(parent.record.request_json) as ScientificPlan).context;
    const result = await createScientificRecord({ context, execution: { type: "agentic_inference", parent_record_sha256: parent.record.record_sha256, ...(reference ? { reference_tissue_id: reference } : {}) } }, signal);
    if (signal.aborted) return;
    const value = agenticInference(result);  // retains the exact computed payload
    if (result.record.summary.mode !== "agentic_inference" || value.reference.tissue_id !== (reference || value.reference.tissue_id)) throw new Error("服务器返回的推断记录与请求的参考组织不一致。");
    setResponse(result); setMessage("推断已保存：读取完整复数采集信号，生成可识别比例与组织模态代理；未生成不可识别的绝对 T2 / T1 图。");
  }
  async function replay(signal: AbortSignal) {
    if (!response) return;
    try {
      const checked = await replayScientificRecord(response.record.record_sha256, signal); if (signal.aborted) return;
      if (!checked.computational_replay_performed || checked.record_sha256 !== response.record.record_sha256) throw new Error("服务器未确认完整回放一致。");
      setMessage("完整回放一致：父图像 / 信号、采集信号读取、比例、系数与验证摘要全部重算匹配。");
    } catch (caught) { setResponse(null); throw caught; }
  }
  const acquisition = inference?.proportions.acquisition;
  return <div className={styles.workbench}>
    <header className={styles.heading}><div><h1>Agent 信号推断与组织模态</h1><p>确定性数值推断读取完整采集信号，在声明结构上呈现参数比例，生成可审计的组织模态代理；类型化输出供后续 LLM 消费。</p></div><Link href="/research" className={styles.scope}>脉冲设计研究台</Link></header>
    <p className={styles.boundary}>教学 / 研究仿真；合成结构不代表真实解剖，不是患者诊断、剂量建议、扫描仪验证或临床质量认证。数值可识别性检查不等于物理或临床有效性。B/C 保持 parked。</p>
    <div className={styles.instrument}>
      <section className={styles.design} aria-label="父记录与推断参考">
        <h2>读取哪一段采集信号</h2>
        <p>父记录必须包含同源完整复数图像与采集向量、声明组织标签格及回波成员。推断只读这些已保存数据，不重新拟合或改写信号。</p>
        <button disabled={busy} onClick={() => void perform(loadExample)}>载入合成对比剂示例</button>
        <details><summary>完整基线计划与来源</summary><label>Agent 基线科学计划<textarea aria-label="Agent 基线科学计划" value={draft} rows={16} spellCheck={false} onChange={event => { cancel(); setParent(null); setReference(""); setDraft(event.target.value); }} /></label></details>
        <div className={styles.actions}><button disabled={busy || !draft} onClick={() => void perform(baseline)}>运行并保存父记录</button></div>
        {pair && <label>参考组织<select aria-label="参考组织" value={reference} onChange={event => { cancel(); setReference(event.target.value); setMessage("参考组织已改变；旧推断被隐藏，须按新参考重新推断。"); }}>{pair.structure.label_to_tissue_id.map(tissue => <option key={tissue} value={tissue}>{tissue}</option>)}</select></label>}
        <div className={styles.actions}><button disabled={busy || !parent} onClick={() => void perform(infer)}>从父记录推断组织模态</button></div>
        <div className={styles.limits}><h3>可识别边界</h3><p>完整组织分区中，非直流频率的组织傅里叶列和为零，因此每回波绝对幅度只确定到共同模；只有采样到直流点的回波可报告绝对幅度。跨回波相对差可拟合表观相对衰减，但不是每组织 T2。</p><p>结构比例来自声明的标签格，图像比例来自声明逆变换后的复数图像。两者都不代表实测解剖或组织分类。</p></div>
      </section>
      <section className={styles.output} aria-label="可识别比例与模态代理" aria-busy={busy}>
        <h2>可识别比例与模态代理</h2>
        <p role="status" className={styles.status}>{message || (busy ? "后端读取父记录、核对回波成员、求解可识别系数并生成模态代理…" : "等待已保存的完整图像 / 信号父记录。")}</p>
        {error && <p role="alert" className={styles.error}>{error}</p>}
        {inference && response?.view && <>
          <p>数值可识别性检查：<strong className={inference.validation.passed ? styles.passed : styles.failed}>{inference.validation.passed ? "通过" : "未通过"}</strong>。这只报告模型检查，不是物理、解剖或临床验证。</p>
          <Measurements view={response.view} validationLabel="数值可识别性检查" />
          <h3>结构层面比例呈现</h3>
          <table><caption>体素比例与重建图像信号占比（按声明组织标签）</caption><thead><tr><th>组织</th><th>体素</th><th>体素比例</th><th>图像能量占比</th><th>图像幅度占比</th></tr></thead><tbody>
            {inference.source.tissue_ids.map(tissue => { const structural = inference.proportions.structure[tissue], image = inference.proportions.image_signal[tissue]; return <tr key={tissue}><td>{tissue}</td><td>{structural.voxel_count}</td><td>{percentage(structural.voxel_fraction)}</td><td>{percentage(image.energy_fraction)}</td><td>{percentage(image.magnitude_fraction)}</td></tr>; })}
          </tbody></table>
          <h3>回波可识别性</h3>
          <table><caption>逐回波采样与静态分区模型残差</caption><thead><tr><th>回波</th><th>样本</th><th>秩</th><th>零空间维数</th><th>绝对幅度</th><th>相对残差</th></tr></thead><tbody>
            {inference.ingestion.echo_bins.map(entry => <tr key={entry.echo}><td>{entry.echo}</td><td>{entry.sample_count}</td><td>{entry.rank ?? "—"}</td><td>{entry.nullity ?? "—"}</td><td>{entry.absolute_amplitude_identified ? "可识别" : "仅相对"}</td><td>{entry.relative_residual === undefined ? "—" : format(entry.relative_residual)}</td></tr>)}
          </tbody></table>
          {acquisition?.available ? <>
            <h3>可识别逐回波系数</h3>
            <p>零共同模规范下的相对系数；同一回波内可比，跨回波绝对幅度不可直接比较。{acquisition.identifiability.gauge}</p>
            <table><caption>组织 × 回波系数</caption><thead><tr><th>组织</th>{inference.ingestion.echo_ids.map(echo => <th key={echo}>回波 {echo}</th>)}</tr></thead><tbody>
              {inference.source.tissue_ids.map(tissue => <tr key={tissue}><td>{tissue}</td>{inference.ingestion.echo_ids.map((echo, index) => { const value = acquisition.coefficients[tissue]?.[index]; return <td key={echo}>{value === undefined ? "—" : format(value)}</td>; })}</tr>)}
            </tbody></table>
            {Object.keys(acquisition.absolute_dc_echo).length > 0 && <details><summary>直流回波绝对幅度（唯一绝对可识别回波）</summary><table><thead><tr><th>回波</th><th>组织</th><th>绝对幅度</th></tr></thead><tbody>{Object.entries(acquisition.absolute_dc_echo).flatMap(([echo, values]) => Object.entries(values).map(([tissue, value]) => <tr key={`${echo}-${tissue}`}><td>{echo}</td><td>{tissue}</td><td>{format(value)}</td></tr>))}</tbody></table></details>}
            <h3>参考相对对比与表观衰减</h3>
            <p>参考组织：{inference.reference.tissue_id}（{inference.reference.definition}）。相对对比为零共同模差值；表观衰减是相对差的指数拟合，不是组织 T2。</p>
            <table><caption>相对对比、强度与拟合</caption><thead><tr><th>组织</th><th>首回波</th><th>末回波</th><th>表观相对衰减 (s)</th><th>拟合残差</th><th>相对强度</th></tr></thead><tbody>
              {inference.source.tissue_ids.map(tissue => { const contrast = ownValue(acquisition.contrast_vs_reference, tissue) ?? [], strength = ownValue(acquisition.relative_contrast_strength, tissue); return <tr key={tissue}><td>{tissue}</td><td>{contrast.length ? format(contrast[0]) : "—"}</td><td>{contrast.length ? format(contrast[contrast.length - 1]) : "—"}</td><td>{decimal(ownValue(acquisition.apparent_relative_contrast_decay_s, tissue) ?? null)}</td><td>{decimal(ownValue(acquisition.decay_fit_residual, tissue) ?? null)}</td><td>{strength === undefined ? "—" : format(strength)}</td></tr>; })}
            </tbody></table>
          </> : <p role="note">逐回波系数不可用：{acquisition?.reason}</p>}
          <h3>明确未生成的组织模态</h3>
          <ul>{inference.unavailable.map(item => <li key={item.item}>{ownValue(UNAVAILABLE, item.item) ?? item.item}：{item.reason}</li>)}</ul>
          <details><summary>九项数值检查</summary><dl className={styles.recordChecks}>{Object.entries(inference.validation.checks).map(([key, passed]) => <React.Fragment key={key}><dt>{checkLabel(key)}</dt><dd className={passed ? styles.passed : styles.failed}>{passed ? "通过" : "未通过"}</dd></React.Fragment>)}</dl></details>
          <div className={styles.provenance}><h3>来源与回放</h3><p>推断范围：{inference.scope}</p><p>检查范围：{inference.validation.scope}</p><p>图像 / 信号对 SHA256：{inference.source.pair_sha256}</p><p>推断 SHA256：{inference.inference_sha256}</p><p>当前记录：{response.record.record_sha256}</p><p>父记录：{response.record.summary.parent_record_sha256}</p><p>父图像 / 信号对：{response.record.summary.parent_pair_sha256}</p>
            <details><summary>完整推断载荷（含各项依据与限制）</summary><pre>{JSON.stringify(inference, null, 2)}</pre></details>
            <div className={styles.actions}><button disabled={busy} onClick={() => void perform(replay)}>完整回放当前记录</button><button onClick={() => download(inference, `mrqlab-agentic-${inference.inference_sha256.slice(0, 12)}.json`)}>下载推断 JSON</button><button onClick={() => download(response.record, `mrqlab-agentic-record-${response.record.record_sha256.slice(0, 12)}.json`)}>下载完整记录</button></div>
            <Link href={`/research/records?id=${response.record.record_sha256}`}>在本地实验记录中查看、导入与回放</Link>
          </div>
        </>}
        {!inference && !busy && <p className={styles.empty}>尚无可显示推断。先保存父记录，再选择参考组织并推断；任何基线或参考变化都会隐藏旧结果。</p>}
      </section>
    </div>
  </div>;
}
