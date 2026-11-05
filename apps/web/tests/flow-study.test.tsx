import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import FlowStudyPage from "../app/research/flow-study/page";
import { createScientificRecord, fetchFlowStudyExample, importFlowVelocity, replayScientificRecord } from "../lib/api";
import type { FlowStudyInput } from "../lib/flow-study";
import type { ScientificResponse } from "../lib/scientific-records";

vi.mock("../lib/api", () => ({ createScientificRecord: vi.fn(), fetchFlowStudyExample: vi.fn(), importFlowVelocity: vi.fn(), replayScientificRecord: vi.fn() }));
const input: FlowStudyInput = { research_question: "Conditional velocity question", target_rationale: "Independent holdout", dataset: { origin: "synthetic", source_ref: "synthetic:test", measurements: [] } };
const result = { calibration: { passed: true, reasons: [], coefficients_pa_m: [100, 194, -49], std_pa_m: [1, 2, 2], calibration_reduced_chi2: .1, holdout_max_standardized_residual: .2, holdout_reduced_chi2: .1 },
  validation: { calibration_and_holdout_passed: true, complete_budget_reserved: true, selected_design_passed: false }, selected_index: null, preview_index: 0,
  candidates: [{ index: 0, design: { inversion_time_s: .9 }, executed: true, eligible: false, reasons: ["physical targets failed"], scenarios: Array.from({ length: 9 }, () => ({ completed: true, numerical_refinement_passed: true, max_observation_refinement_error: .003, passed: false })) }],
  provenance: { input_origin: "synthetic", source_ref: "synthetic:test", raw_file_sha256: "a".repeat(64), estimated_work: 123, reserved_work: 1000 } };
const response: ScientificResponse = { record: { schema_version: "mrqlab-scientific-record-1", record_sha256: "b".repeat(64), request_json: "{}", payload_json: JSON.stringify({ flow_study: result }), request_sha256: "c".repeat(64), payload_sha256: "d".repeat(64), api_source_hash: "e".repeat(64), sources: { sha256: "f".repeat(64), files: {} }, runtime: {}, stages: [], summary: { study_id: "test", research_question: input.research_question, mode: "measured_flow", kind: "measured_flow", selected_index: null, model_reported_passed: false, candidate_count: 1, input_origins: ["synthetic"], scope: "research" } }, view: null, verification: { integrity_passed: true, computational_replay_performed: false } };
beforeEach(() => { vi.resetAllMocks(); vi.mocked(fetchFlowStudyExample).mockResolvedValue(input); vi.mocked(createScientificRecord).mockResolvedValue(response); });
afterEach(cleanup);
async function load() { render(<FlowStudyPage />); fireEvent.click(screen.getByRole("button", { name: "载入合成速度示例" })); await screen.findByText(/已载入合成速度 CSV 示例/); }
async function run() { await load(); fireEvent.click(screen.getByRole("button", { name: "校准、验证并保存" })); await screen.findByText("未选出通过验证的设计"); }

it("requires explicit input and saves the complete measured-flow plan", async () => {
  render(<FlowStudyPage />); expect(screen.getByRole("button", { name: "校准、验证并保存" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "载入合成速度示例" })); await screen.findByText(/已载入合成速度/);
  fireEvent.click(screen.getByRole("button", { name: "校准、验证并保存" })); await screen.findByText("校准与独立留出：通过");
  expect(createScientificRecord).toHaveBeenCalledWith({ context: { study_id: "velocity-dir-pilot", research_question: input.research_question, target_rationale: input.target_rationale }, execution: { type: "measured_flow", study: input } }, expect.any(AbortSignal));
});

it("keeps calibration, numerical checks and failed physical design separate", async () => {
  await run(); expect(screen.getByText("校准与独立留出：通过")).toBeInTheDocument();
  expect(screen.getAllByText("9/9")).toHaveLength(2); expect(screen.getByText(/physical targets failed/)).toBeInTheDocument();
  expect(screen.getByText(/数据来源：合成数据/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /本地实验记录中导入/ })).toHaveAttribute("href", "/research/records");
});

it("reports independent computational replay only after backend completion", async () => {
  vi.mocked(replayScientificRecord).mockResolvedValue({ integrity_passed: true, computational_replay_performed: true, record_sha256: response.record.record_sha256, payload_sha256: "d".repeat(64), summary: response.record.summary });
  await run(); fireEvent.click(screen.getByRole("button", { name: "回放完整流动研究" }));
  await screen.findByText(/完整计算回放一致/);
  expect(replayScientificRecord).toHaveBeenCalledWith(response.record.record_sha256, expect.any(AbortSignal));
});

it("runtime replay errors clear the prior evidence", async () => {
  vi.mocked(replayScientificRecord).mockRejectedValue(new Error("runtime differs")); await run();
  fireEvent.click(screen.getByRole("button", { name: "回放完整流动研究" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("runtime differs");
  expect(screen.queryByText("校准与独立留出：通过")).not.toBeInTheDocument();
});

it("editing input aborts a response and cannot attach stale evidence", async () => {
  let finish!: (value: ScientificResponse) => void;
  vi.mocked(createScientificRecord).mockReturnValue(new Promise(resolve => { finish = resolve; }));
  await load(); fireEvent.click(screen.getByRole("button", { name: "校准、验证并保存" }));
  fireEvent.change(screen.getByLabelText("流动研究 JSON"), { target: { value: "{}" } }); finish(response);
  await waitFor(() => expect(screen.getByLabelText("流动研究 JSON")).toHaveValue("{}"));
  expect(screen.queryByText("校准与独立留出：通过")).not.toBeInTheDocument();
});

it("malformed JSON never reaches the scientific runner", async () => {
  await load(); fireEvent.change(screen.getByLabelText("流动研究 JSON"), { target: { value: "{" } });
  fireEvent.click(screen.getByRole("button", { name: "校准、验证并保存" })); await screen.findByRole("alert");
  expect(createScientificRecord).not.toHaveBeenCalled();
});

it("requires an explicit dataset origin and preserves imported raw bytes", async () => {
  await load(); fireEvent.change(screen.getByLabelText("速度数据类型"), { target: { value: "" } });
  expect(screen.getByLabelText("速度 CSV")).toBeDisabled();
  fireEvent.change(screen.getByLabelText("速度数据类型"), { target: { value: "measured" } });
  const bytes = new TextEncoder().encode("time_s,velocity_m_s\r\n0,0.1\r\n");
  const file = new File([bytes], "velocity.csv", { type: "text/csv" });
  Object.defineProperty(file, "arrayBuffer", { value: async () => bytes.buffer });
  const dataset = { ...input.dataset, origin: "measured" as const, raw_csv_base64: btoa(new TextDecoder().decode(bytes)) };
  vi.mocked(importFlowVelocity).mockResolvedValue(dataset);
  fireEvent.change(screen.getByLabelText("速度 CSV"), { target: { files: [file] } });
  await screen.findByText(/已保留 CSV 原始字节与哈希/);
  expect(importFlowVelocity).toHaveBeenCalledWith({ csv_base64: dataset.raw_csv_base64, source_ref: input.dataset.source_ref, origin: "measured" }, expect.any(AbortSignal));
  expect(JSON.parse((screen.getByLabelText("流动研究 JSON") as HTMLTextAreaElement).value).dataset).toEqual(dataset);
});
