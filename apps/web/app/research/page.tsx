"use client";
import React, { useEffect, useRef, useState } from "react";
import { runResearch, searchResearch } from "../../lib/api";
import { ResearchKind, ResearchRequest, ResearchRun, ResearchSearch, STUDIES } from "../../lib/research";
import styles from "./research.module.css";
import Link from "next/link";
import Measurements from "../../components/research/Measurements";
import SaveScientificRecord from "../../components/research/SaveScientificRecord";

const KINDS = Object.keys(STUDIES) as ResearchKind[];
const format = (value: number) => Number.isInteger(value) ? String(value) : value.toPrecision(5);

export default function ResearchPage() {
  const [kind, setKind] = useState<ResearchKind>("tse");
  const [parameters, setParameters] = useState(JSON.stringify(STUDIES.tse.defaults, null, 2));
  const [run, setRun] = useState<ResearchRun | null>(null);
  const [search, setSearch] = useState<ResearchSearch | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [importedSearch, setImportedSearch] = useState<{ request: ResearchSearch["replay_search"]; hash: string } | null>(null);
  const [pin, setPin] = useState<string | undefined>();
  const [expectedResult, setExpectedResult] = useState<string | undefined>();
  const pending = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const study = STUDIES[kind];
  useEffect(() => () => pending.current?.abort(), []);
  function clearWork() {
    generation.current += 1; pending.current?.abort(); setBusy(false); setRun(null); setSearch(null); setError(""); setMessage("");
  }
  function edit(value: string) { clearWork(); setParameters(value); setPin(undefined); setExpectedResult(undefined); setImportedSearch(null); }
  function choose(next: ResearchKind) { clearWork(); setKind(next); setParameters(JSON.stringify(STUDIES[next].defaults, null, 2)); setPin(undefined); setExpectedResult(undefined); setImportedSearch(null); }
  function parse(): Record<string, unknown> {
    const value: unknown = JSON.parse(parameters);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("参数必须是 JSON 对象。");
    return value as Record<string, unknown>;
  }
  function field(key: string) { try { return String(parse()[key] ?? ""); } catch { return ""; } }
  function update(key: string, value: string) {
    try { edit(JSON.stringify({ ...parse(), [key]: value === "" ? null : Number(value) }, null, 2)); }
    catch { setError("先修正完整参数中的 JSON，再修改数值。"); }
  }
  async function execute(mode: "run" | "search" | "replay" | "replay-search") {
    pending.current?.abort(); const control = new AbortController(); pending.current = control;
    const id = ++generation.current; setBusy(true); setError(""); setMessage("");
    const original = run;
    try {
      const request: ResearchRequest = mode === "replay" && original ? original.replay_request : { kind, parameters: parse(), expected_source_hash: pin };
      if (mode === "search" || mode === "replay-search") {
        const searchRequest = mode === "replay-search" && search ? search.replay_search : importedSearch?.request ?? { ...request, candidates: study.candidates };
        const expectedSearch = mode === "replay-search" ? search?.search_hash : importedSearch?.hash;
        const response = await searchResearch(searchRequest, control.signal);
        if (generation.current !== id) return;
        const displayed = response.best?.run ?? response.candidates.find(point => point.run)?.run ?? null;
        setSearch(response); setRun(displayed);
        if (displayed) setParameters(JSON.stringify(displayed.replay_request.parameters, null, 2));
        setImportedSearch(null); setPin(undefined); setExpectedResult(undefined);
        setMessage(expectedSearch ? (response.search_hash === expectedSearch ? "候选比较回放一致：全部候选与选择哈希匹配。" : "候选比较回放不一致，请检查运行环境。") : response.best ? "有限网格搜索完成；所选设计的目标验证单独报告。" : response.candidates.some(point => point.feasible) ? "候选可执行，但没有设计通过全部目标。展示首个可执行候选。" : "没有可执行候选。请检查预算与时序。");
      } else {
        const response = await runResearch(request, control.signal);
        if (generation.current !== id) return;
        setRun(response); setSearch(null);
        const expected = mode === "replay" ? original?.result_hash : expectedResult;
        setMessage(expected ? (response.result_hash === expected ? "回放一致：结果哈希匹配。" : "回放不一致：结果哈希不匹配，请检查运行环境。") : "仿真完成。请查看目标验证与模型边界。");
      }
    } catch (caught) {
      if (generation.current !== id || control.signal.aborted) return;
      setRun(null); setSearch(null); setError(caught instanceof Error ? caught.message : "请求失败。检查本地仿真 API 是否可用。");
    } finally { if (generation.current === id) setBusy(false); }
  }
  async function importRecord(file?: File) {
    if (!file) return;
    clearWork(); const importId = generation.current;
    try {
      if (file.size > 64 * 1024 * 1024) throw new Error("记录超过 64 MiB。请使用本地 API/脚本回放较大的完整记录。");
      const record = JSON.parse(await file.text());
      if (generation.current !== importId) return;
      const request = record.replay_request;
      if (!request || !KINDS.includes(request.kind) || !request.parameters || typeof request.parameters !== "object" || Array.isArray(request.parameters) || !/^[a-f0-9]{64}$/.test(request.expected_source_hash) || !/^[a-f0-9]{64}$/.test(record.result_hash)) throw new Error("记录缺少有效的研究类型、参数或源码指纹。");
      if (record.search && (record.search.replay_search?.kind !== request.kind || record.search.replay_search?.expected_source_hash !== request.expected_source_hash || !/^[a-f0-9]{64}$/.test(record.search.search_hash))) throw new Error("搜索记录与所选实验的类型或源码指纹不一致。");
      clearWork(); setKind(request.kind); setParameters(JSON.stringify(request.parameters, null, 2)); setPin(request.expected_source_hash); setExpectedResult(record.result_hash);
      setImportedSearch(record.search?.replay_search && record.search?.search_hash ? { request: record.search.replay_search, hash: record.search.search_hash } : null);
      setMessage("记录已载入。运行将核对源码指纹和结果哈希。");
    } catch (caught) { if (generation.current === importId) setError(caught instanceof Error ? caught.message : "无法读取研究记录。"); }
  }
  function download() {
    if (!run) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify({ ...run, ...(search ? { search } : {}) }, null, 2)], { type: "application/json" }));
    const a = document.createElement("a"); a.href = url; a.download = `mrqlab-${run.kind}-${run.result_hash.slice(0, 12)}.json`;
    document.body.appendChild(a); a.click(); a.remove();
    // WebKit may start the download after the click task finishes.
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <div className={styles.workbench}>
    <header className={styles.heading}><div><h1>脉冲设计研究台</h1><p>从研究问题到设计、仿真、参数搜索、目标验证与回放。</p></div><Link className={styles.scope} href="/research/lab-study">实验测量到设计验证</Link></header>
    <p className={styles.boundary}>不作为扫描仪验证或临床质量认证。Milestone B / C 保持 parked。 <Link href="/research/records">本地实验记录</Link></p>
    <nav aria-label="研究实验" className={styles.kinds}>{KINDS.map(item => <button key={item} aria-pressed={item === kind} onClick={() => choose(item)}>{STUDIES[item].title}</button>)}</nav>
    <div className={styles.instrument}>
      <section className={styles.design} aria-label="研究设计">
        <h2>问题与设计</h2><p>{study.question}</p>
        {kind === "noncartesian" && <label>重建方法<select aria-label="重建方法" value={field("reconstruction")} onChange={event => { try { edit(JSON.stringify({ ...parse(), reconstruction: event.target.value }, null, 2)); } catch { setError("先修正完整参数 JSON。"); } }}><option value="cgls">精确 DFT / CGLS（参考）</option><option value="nufft_cgls">FINUFFT / CGLS（需可选依赖）</option><option value="gridding">线性 gridding（近似）</option></select></label>}
        {kind === "radial_tse" && <label>傅里叶后端<select aria-label="傅里叶后端" value={field("backend")} onChange={event => { try { edit(JSON.stringify({ ...parse(), backend: event.target.value }, null, 2)); } catch { setError("先修正完整参数 JSON。"); } }}><option value="exact">精确 DFT（参考）</option><option value="finufft">FINUFFT（需可选依赖，检查预算）</option></select></label>}
        {kind === "mrs_press" && <label>拟合基组<select aria-label="拟合基组" value={field("basis_mode")} onChange={event => { try { edit(JSON.stringify({ ...parse(), basis_mode: event.target.value }, null, 2)); } catch { setError("先修正完整参数 JSON。"); } }}><option value="volume">三维体积积分</option><option value="center">中心点（失配对照）</option></select></label>}
        {kind === "mrs_quantum" && <label>弛豫基组<select aria-label="弛豫基组" value={field("basis_mode")} onChange={event => { try { edit(JSON.stringify({ ...parse(), basis_mode: event.target.value }, null, 2)); } catch { setError("先修正完整参数 JSON。"); } }}><option value="matched">匹配实际准备与 TR</option><option value="equilibrium">完全恢复（失配对照）</option></select></label>}
        {study.fields.map(input => <label key={input.key}>{input.label}<input type="number" step={input.step} value={field(input.key)} placeholder="使用模型默认值" onChange={event => update(input.key, event.target.value)} /></label>)}
        <details><summary>完整参数与自定义体模</summary><p>未提供的值使用模型默认值。可编辑 RF、组织、目标、预算与体模；服务器验证所有输入。</p><textarea aria-label="完整参数 JSON" rows={15} value={parameters} onChange={event => edit(event.target.value)} spellCheck={false} /></details>
        <div className={styles.actions}><button disabled={busy} onClick={() => void execute("run")}>{busy ? "计算中…" : pin ? "运行导入回放" : "运行仿真"}</button><button disabled={busy} onClick={() => void execute("search")}>{importedSearch ? "回放导入候选比较" : "比较候选设计"}</button></div>
        <details><summary>搜索网格</summary><p>优化仅比较以下候选，按模型声明的损失选择。目标通过与可执行性分别报告。</p><pre>{JSON.stringify(study.candidates, null, 2)}</pre></details>
        <div className={styles.limits}><h3>默认验证目标</h3><p>{study.validation}</p><h3>模型边界与缺口</h3><p>{study.limit}</p></div>
        <label className={styles.import}>导入回放记录<input type="file" accept="application/json,.json" onChange={event => void importRecord(event.target.files?.[0])} /></label>
      </section>
      <section className={styles.output} aria-label="测量与验证" aria-busy={busy}>
        <div className={styles.outputHead}><h2>测量与验证</h2>{run && <span className={run.view.validation.passed ? styles.passed : styles.failed}>{run.view.validation.passed ? "目标通过" : "目标未通过"}</span>}</div>
        <p role="status" className={styles.status}>{message || (busy ? "后端正在执行物理模型与验证…" : "")}</p>
        {error && <p role="alert" className={styles.error}>{error}</p>}
        {!run && !busy && !error && <div className={styles.empty}><h3>先定义实验，再观察信号。</h3><p>运行后显示后端实测图像或频谱、验证结果和可回放记录。更改设计会清除旧结果。</p></div>}
        {run && <><p className={styles.question}>{run.result.clinical_question}</p><Measurements view={run.view} />
          {(kind === "pulsatile_flow" || kind === "flow_epi") && run.result.gates && <section className={styles.search}><h3>触发决策与实际完成</h3>{run.view.curves.length === 0 && <p>没有完整读出；未生成血液或壁组织测量值。</p>}<p>安排准备只依据已到达的触发；下一触发到达后才能中断。中断前已执行的 RF 继续影响后续自旋。</p><div className={styles.scroll}><table><thead><tr><th>触发 (s)</th><th>过去 RR 估计 (s)</th><th>已安排准备</th><th>完整读出</th><th>中断/拒绝原因</th></tr></thead><tbody>{run.result.gates.map(gate => <tr key={gate.trigger}><td>{format(gate.decision_s)}</td><td>{format(gate.rr_estimate_s)}</td><td>{gate.scheduled ? "是" : "否"}</td><td>{gate.accepted ? "是" : "否"}</td><td>{gate.rejection ?? "—"}</td></tr>)}</tbody></table></div></section>}
          {kind === "flow_epi" && run.result.readout_status && <section className={styles.search}><h3>实际 EPI 样本与编码对</h3>
            <p>中断前的样本保留；缺失 k 空间不补零生成图像。流速是完整异号复图像的包裹相位差，必须结合信号有效性图；不是单个时刻的直接流速测量。</p>
            {run.view.validation.completed_encoding_pairs === 0 && <p>没有完整异号编码对；未生成流速或流量测量。</p>}
            <div className={styles.scroll}><table><thead><tr><th>触发编号</th><th>编码极性</th><th>ADC 样本 / 完整网格</th><th>完成图像</th><th>停止阶段</th></tr></thead><tbody>{run.result.readout_status.map(row => <tr key={row.trigger}><td>{row.trigger + 1}</td><td>{row.encoding_sign > 0 ? "+" : "−"}</td><td>{row.adc_samples} / {row.expected_samples}</td><td>{row.completed ? "是" : "否"}</td><td>{row.stage}</td></tr>)}</tbody></table></div>
          </section>}
          {kind === "mrs_quantum" && run.result.quantum_diagnostics && <section className={styles.search}><h3>量子弛豫与重复采集</h3>
            <p>准备：{run.result.quantum_diagnostics.preparation === "periodic" ? "完整 TR 周期稳态" : "有限次 dummy 扫描"}；基组：{run.result.quantum_diagnostics.basis_mode === "matched" ? "匹配实际准备与 TR" : "完全恢复（失配对照）"}。数值核对{run.result.quantum_diagnostics.numerical_refinement_passed ? "通过" : "未通过"}；信号量、残差和保留信号目标单独判定。</p>
            <dl><dt>TR / ADC 结束 / 恢复 (s)</dt><dd>{format(run.result.quantum_diagnostics.timing.repetition_s)} / {format(run.result.quantum_diagnostics.timing.adc_end_s)} / {format(run.result.quantum_diagnostics.timing.recovery_s)}</dd>
              <dt>周期返回误差</dt><dd>{format(run.result.quantum_diagnostics.max_periodic_return_error)}</dd><dt>最小密度本征值</dt><dd>{format(run.result.quantum_diagnostics.minimum_density_eigenvalue)}</dd></dl>
            <div className={styles.scroll}><table><thead><tr><th>教学分量</th><th>作者信号量</th><th>恢复信号量</th><th>相对完全恢复的信号范数</th></tr></thead><tbody>{run.result.quantum_diagnostics.components.map(row => <tr key={row.name}><td>{row.name}</td><td>{format(row.authored_amount)}</td><td>{format(row.recovered_amount)}</td><td>{format(row.signal_fraction)}</td></tr>)}</tbody></table></div>
            <p>局部 Lindblad 浴在每个 RF、自由演化、ADC 和恢复区间作用。读出后采用理想独立自旋去相位；尚未与三维 PRESS 或真实 crusher 耦合。信号量不是临床浓度。</p>
          </section>}
          {kind === "cest_memory" && run.result.memory_diagnostics && <section className={styles.search}><h3>有限 RF 与记忆核收敛</h3>
            <p>数值加密核对：{run.result.memory_diagnostics.numerical_refinement_passed ? "通过" : "未通过"}。该结果与上方 CEST/NOE 对比目标独立；零频偏按显式选定的时间核计算，不自动截断吸收率或替换线型。</p>
            <dl><dt>粗 / 细时间单元</dt><dd>{run.result.memory_diagnostics.coarse_steps} / {run.result.memory_diagnostics.refined_steps}</dd>
              <dt>全时序归一化差</dt><dd>{format(run.result.memory_diagnostics.normalized_trace_difference)}</dd><dt>积分记忆核差</dt><dd>{format(run.result.memory_diagnostics.lag_kernel_error)}</dd>
              <dt>保留历史 (s)</dt><dd>{format(run.result.memory_diagnostics.retained_history_s)}</dd><dt>脉冲间清空历史</dt><dd>{run.result.memory_diagnostics.inter_pulse_reset ? "是" : "否"}</dd></dl>
            <p>完整 RF 采样、各对照的水/半固体时序和历史哈希保存在记录中。分子先验与数值网格在候选搜索中固定。</p>
          </section>}
          <section className={styles.provenance}><h3>验证与回放记录</h3><p>{run.result.scope}</p><dl><dt>源码指纹</dt><dd>{run.source_hash}</dd><dt>结果哈希</dt><dd>{run.result_hash}</dd><dt>运行环境</dt><dd>Python {run.runtime.python} / NumPy {run.runtime.numpy}</dd></dl>
            <div className={styles.actions}><button disabled={busy} onClick={() => void execute("replay")}>回放此结果</button><button disabled={busy} onClick={download}>导出完整记录</button></div>
            <details><summary>设计、时序与 provenance</summary><pre>{JSON.stringify({ replay: run.replay_request, provenance: run.result.provenance, validation: run.view.validation }, null, 2)}</pre></details>
          </section></>}
        {run && <SaveScientificRecord key={`${run.source_hash}:${search?.search_hash ?? run.result_hash}`} question={run.result.clinical_question}
          execution={search ? { type: "search", ...search.replay_search } : { type: "run", ...run.replay_request }} expectedHash={search?.search_hash ?? run.result_hash} />}
        {search && <section className={styles.search}><h3>有限网格比较</h3><button disabled={busy} onClick={() => void execute("replay-search")}>回放候选比较</button><p>{search.objective}</p><div className={styles.scroll}><table><thead><tr><th>参数</th><th>可执行</th><th>损失</th><th>目标</th></tr></thead><tbody>{search.candidates.map((point, i) => <tr key={i}><td>{JSON.stringify(point.parameters)}</td><td>{point.feasible ? "是" : String(point.reason)}</td><td>{point.loss == null ? "—" : format(point.loss)}</td><td>{point.run ? point.run.view.validation.passed ? "通过" : "未通过" : "未运行"}</td></tr>)}</tbody></table></div></section>}
      </section>
    </div>
  </div>;
}
