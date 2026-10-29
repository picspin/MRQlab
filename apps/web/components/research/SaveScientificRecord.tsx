"use client";
import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { createScientificRecord } from "../../lib/api";
import type { ScientificExecution } from "../../lib/scientific-records";
import styles from "../../app/research/research.module.css";

export default function SaveScientificRecord({ execution, expectedHash, question }: { execution: ScientificExecution; expectedHash: string; question: string }) {
  const [studyId, setStudyId] = useState("");
  const [researchQuestion, setResearchQuestion] = useState(question);
  const [rationale, setRationale] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function save() {
    const active = new AbortController(); controller.current?.abort(); controller.current = active;
    setBusy(true); setError(""); setSaved("");
    try {
      const response = await createScientificRecord({ context: { study_id: studyId.trim(), research_question: researchQuestion.trim(), target_rationale: rationale.trim(), intended_use: "research" },
        execution, expected_execution_hash: expectedHash }, active.signal);
      if (active.signal.aborted) return;
      setSaved(response.record.record_sha256);
    } catch (caught) { if (!active.signal.aborted) setError(caught instanceof Error ? caught.message : "记录保存失败。"); }
    finally { if (!active.signal.aborted) setBusy(false); }
  }
  function edit(action: () => void) { action(); setSaved(""); setError(""); }
  return <section className={styles.provenance} aria-label="保存到本地实验记录">
    <h3>保存到本地实验记录</h3><p>填写研究问题和目标依据。后端会重新计算、核对当前结果哈希，再保存不可覆盖的完整记录。</p>
    <div className={styles.recordFields}>
      <label>实验编号<input value={studyId} disabled={busy} onChange={e => edit(() => setStudyId(e.target.value))} placeholder="例如 phantom-t2-01" /></label>
      <label>记录研究问题<textarea value={researchQuestion} disabled={busy} rows={2} onChange={e => edit(() => setResearchQuestion(e.target.value))} /></label>
      <label>目标依据<textarea value={rationale} disabled={busy} rows={2} onChange={e => edit(() => setRationale(e.target.value))} placeholder="说明研究目标、阈值依据及其适用范围" /></label>
    </div>
    <button disabled={busy || !studyId.trim() || !researchQuestion.trim() || !rationale.trim()} onClick={() => void save()}>{busy ? "重新计算并保存中…" : "重新计算并保存记录"}</button>
    {error && <p role="alert" className={styles.error}>{error}</p>}
    {saved && <p role="status">完整记录已保存：<Link href={`/research/records?id=${saved}`}>{saved.slice(0, 12)}</Link>。模型是否达到目标仍按原结果报告。</p>}
  </section>;
}
