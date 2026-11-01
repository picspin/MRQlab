import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import RecordsPage from "../app/research/records/page";
import SaveScientificRecord from "../components/research/SaveScientificRecord";
import { createScientificRecord, getScientificRecord, importScientificRecord, listScientificRecords, replayScientificRecord } from "../lib/api";
import type { ScientificRecord, ScientificResponse } from "../lib/scientific-records";
vi.mock("../lib/api", () => ({ createScientificRecord: vi.fn(), getScientificRecord: vi.fn(), importScientificRecord: vi.fn(), listScientificRecords: vi.fn(), replayScientificRecord: vi.fn() }));
const id = "a".repeat(64);
const record: ScientificRecord = {
  schema_version: "mrqlab-scientific-record-1", record_sha256: id, request_json: '{"context":{"research_question":"Saved pulse question"}}', payload_json: '{"full":"complex scientific data"}',
  request_sha256: "b".repeat(64), payload_sha256: "c".repeat(64), api_source_hash: "d".repeat(64), sources: { sha256: "e".repeat(64), files: {} }, runtime: { python: "3.12" },
  summary: { study_id: "phantom-01", research_question: "Saved pulse question", mode: "run", kind: "tse", selected_index: 0, model_reported_passed: false, candidate_count: 1, input_origins: ["authored_model_inputs"], scope: "research only", candidates: [{ index: 0, executable: true, model_reported_passed: false }] },
  stages: [{ stage: "question", parents: [], value_sha256: id, sha256: id }],
};
const response: ScientificResponse = { record, verification: { integrity_passed: true, computational_replay_performed: false },
  view: { images: [], curves: [], x_label: "Echo", y_label: "Signal", metrics: { Error: .2 }, validation: { passed: false } } };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listScientificRecords).mockResolvedValue({ total: 1, offset: 0, limit: 20, records: [{ record_sha256: id, created_ns: 1, bytes: 1024, summary: record.summary, integrity_checked: false, computational_replay_performed: false }] });
  vi.mocked(getScientificRecord).mockResolvedValue(response);
  vi.mocked(importScientificRecord).mockResolvedValue(response);
});
afterEach(cleanup);

it("identifies an edited image/signal parent without labelling it measured calibration", async () => {
  const child = structuredClone(response); child.record.summary.mode = "edited_tse"; child.record.summary.parent_record_sha256 = "f".repeat(64);
  vi.mocked(getScientificRecord).mockResolvedValueOnce(child).mockResolvedValue(response);
  render(<RecordsPage />); fireEvent.click(await screen.findByRole("button", { name: /phantom-01/ }));
  const parentButton = await screen.findByRole("button", { name: "打开父图像 / 信号记录" });
  expect(screen.queryByRole("button", { name: "打开父测量记录" })).not.toBeInTheDocument();
  fireEvent.click(parentButton);
  await waitFor(() => expect(getScientificRecord).toHaveBeenLastCalledWith("f".repeat(64), expect.any(AbortSignal)));
});

it("opens persistent history without presenting integrity as scientific replay", async () => {
  render(<RecordsPage />); fireEvent.click(await screen.findByRole("button", { name: /phantom-01/ }));
  await screen.findByText("历史记录中的测量（尚未重算）");
  expect(screen.getByText("尚未确认")).toBeInTheDocument();
  expect(replayScientificRecord).not.toHaveBeenCalled();
  vi.mocked(replayScientificRecord).mockResolvedValue({ integrity_passed: true, computational_replay_performed: true, record_sha256: id, payload_sha256: record.payload_sha256, summary: record.summary });
  fireEvent.click(screen.getByRole("button", { name: "在当前环境完整重算" }));
  await screen.findByText("完整计算回放一致：全部结果、候选、阶段与记录哈希匹配。");
  expect(screen.getByText("重算一致的测量")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /phantom-01/ })).toHaveTextContent("当前会话已重算一致");
});

it("retains historical status and source error when current replay fails", async () => {
  vi.mocked(replayScientificRecord).mockRejectedValue(new Error("source manifest differs"));
  render(<RecordsPage />); fireEvent.click(await screen.findByRole("button", { name: /phantom-01/ }));
  await screen.findByText("历史记录中的测量（尚未重算）");
  fireEvent.click(screen.getByRole("button", { name: "在当前环境完整重算" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("source manifest differs");
  expect(screen.getByText("尚未确认")).toBeInTheDocument();
});

it("aborts a pending record load on unmount and ignores its delayed response", async () => {
  let finish!: (value: ScientificResponse) => void;
  vi.mocked(getScientificRecord).mockReturnValue(new Promise(resolve => { finish = resolve; }));
  render(<RecordsPage />); fireEvent.click(await screen.findByRole("button", { name: /phantom-01/ }));
  expect(screen.getByRole("button", { name: "读取记录列表" })).toBeDisabled();
  const signal = vi.mocked(getScientificRecord).mock.calls[0][1];
  expect(signal?.aborted).toBe(false);
  cleanup(); expect(signal?.aborted).toBe(true);
  finish(response);
  await Promise.resolve();
  expect(screen.queryByText("Saved pulse question")).not.toBeInTheDocument();
});

it("imports a full portable record and keeps it un-replayed", async () => {
  const file = new File(["record"], "import.json", { type: "application/json" });
  Object.defineProperty(file, "text", { value: async () => JSON.stringify(record) });
  render(<RecordsPage />); await screen.findByRole("button", { name: /phantom-01/ });
  fireEvent.change(screen.getByLabelText("导入完整实验记录"), { target: { files: [file] } });
  await screen.findByText("记录已导入本地，完整性通过；尚未执行科学计算回放。");
  expect(vi.mocked(importScientificRecord).mock.calls[0][0].payload_json).toBe(record.payload_json);
  expect(screen.getByText("尚未确认")).toBeInTheDocument();
});

it("saves by recomputing the exact source-pinned execution and expected result", async () => {
  vi.mocked(createScientificRecord).mockResolvedValue(response);
  render(<SaveScientificRecord question="Pulse question" execution={{ type: "run", kind: "tse", parameters: {}, expected_source_hash: "d".repeat(64) }} expectedHash="expected-result" />);
  expect(screen.getByRole("button", { name: "重新计算并保存记录" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("实验编号"), { target: { value: "phantom-01" } });
  fireEvent.change(screen.getByLabelText("目标依据"), { target: { value: "Declared research threshold" } });
  fireEvent.click(screen.getByRole("button", { name: "重新计算并保存记录" }));
  await screen.findByRole("link", { name: id.slice(0, 12) });
  expect(vi.mocked(createScientificRecord).mock.calls[0][0]).toMatchObject({ expected_execution_hash: "expected-result", execution: { type: "run", expected_source_hash: "d".repeat(64) } });
});

it("exports lossless request and payload strings in the complete record", async () => {
  let blob: Blob | undefined;
  vi.stubGlobal("URL", { createObjectURL: (b: Blob) => { blob = b; return "blob:record"; }, revokeObjectURL: vi.fn() });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  try {
    render(<RecordsPage />); fireEvent.click(await screen.findByRole("button", { name: /phantom-01/ }));
    await screen.findByRole("button", { name: "导出完整实验记录" });
    fireEvent.click(screen.getByRole("button", { name: "导出完整实验记录" }));
    const text = await new Promise<string>(resolve => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(blob!); });
    expect(JSON.parse(text).payload_json).toBe(record.payload_json);
    expect(JSON.parse(text).request_json).toBe(record.request_json);
  } finally { click.mockRestore(); vi.unstubAllGlobals(); }
});

it("shows a failed-only search without inventing a selected design", async () => {
  const failed: ScientificResponse = { ...response, record: { ...record, summary: { ...record.summary, mode: "search", selected_index: null,
    candidates: [{ index: 0, executable: false, model_reported_passed: false, reason: "invalid timing" }, { index: 1, executable: true, model_reported_passed: false }] } } };
  vi.mocked(getScientificRecord).mockResolvedValue(failed);
  render(<RecordsPage />); fireEvent.click(await screen.findByRole("button", { name: /phantom-01/ }));
  await screen.findByText("原记录未选出设计；全部候选保留在下表。");
  expect(screen.getByText("下方展示候选 2 的历史测量；展示不会改变原选择。")).toBeInTheDocument();
  expect(screen.getByText('"invalid timing"')).toBeInTheDocument();
});
