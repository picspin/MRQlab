import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import LabStudyPage from "../app/research/lab-study/page";
import { fetchLabStudyExample, replayLabStudy, runLabStudy } from "../lib/api";
import type { LabStudyRecord, LabStudyResponse } from "../lib/lab-study";
vi.mock("../lib/api", () => ({ fetchLabStudyExample: vi.fn(), replayLabStudy: vi.fn(), runLabStudy: vi.fn(), importLabEchoes: vi.fn() }));
const input = { dataset: { origin: "synthetic", source_ref: "synthetic:test" }, experiment: {}, candidates: [{ echoes: 2 }] };
const record: LabStudyRecord = {
  schema_version: "mrqlab-study-record-1", study_kind: "measured-tse", canonicalization: "typed-json-f64-v1", request: input, request_json: JSON.stringify(input),
  request_sha256: "a".repeat(64), result_sha256: "b".repeat(64), record_sha256: "c".repeat(64),
  sources: { files: {}, sha256: "d".repeat(64) }, runtime: {},
  result: { clinical_question: { research_question: "Measured-input test question" },
    calibration: [{ tissue_id: "target", t2_s: .04, t2_std_s: .0001, holdout_max_standardized_residual: .2, passed: true, reasons: [] }],
    candidates: [{ index: 0, design: { echoes: 2 }, executed: true, eligible: true, worst_psf_rms_voxels: .2, reasons: [], scenarios: [] }],
    selected_index: 0, validation: { calibration_and_holdout_passed: true, complete_budgeted_search: true, selected_design_passed: true },
    targets: {}, provenance: { estimated_work: 12000, reserved_work: 50000, stages: [] }, scope: "research only" },
};
const response: LabStudyResponse = { record, view: null };
beforeEach(() => { vi.resetAllMocks(); vi.mocked(fetchLabStudyExample).mockResolvedValue(input); vi.mocked(runLabStudy).mockResolvedValue(response); });
afterEach(cleanup);

it("does not invent measured data and executes an explicit synthetic example", async () => {
  render(<LabStudyPage />); expect(screen.getByRole("button", { name: "校准并验证设计" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "载入合成示例" })); await screen.findByText("已载入明确标记的合成 CPMG 示例。它不代表实际实验数据。");
  fireEvent.click(screen.getByRole("button", { name: "校准并验证设计" })); await screen.findByText("研究设计目标通过");
  expect(screen.getByText(/数据来源：合成示例/)).toBeInTheDocument();
  expect(runLabStudy).toHaveBeenCalledWith(input, expect.any(AbortSignal));
  expect(screen.getByLabelText("完整研究记录 JSON")).toHaveValue(JSON.stringify(record, null, 2));
});

it("retains failed holdout evidence and shows no selected design", async () => {
  const failed = structuredClone(record); failed.result.selected_index = null;
  failed.result.validation.calibration_and_holdout_passed = false; failed.result.validation.selected_design_passed = false;
  failed.result.calibration[0].passed = false; failed.result.calibration[0].reasons = ["independent holdout failed"];
  vi.mocked(runLabStudy).mockResolvedValue({ record: failed, view: null });
  render(<LabStudyPage />); fireEvent.change(screen.getByLabelText("实验研究 JSON"), { target: { value: JSON.stringify(input) } });
  fireEvent.click(screen.getByRole("button", { name: "校准并验证设计" })); await screen.findByText("未选出通过验证的设计");
  expect(screen.getByText("independent holdout failed")).toBeInTheDocument();
  expect(screen.queryByText("已选设计的图像与回波")).not.toBeInTheDocument();
});

it("computationally replays the entire record and exposes backend pin errors", async () => {
  vi.mocked(replayLabStudy).mockRejectedValue(new Error("replay runtime differs"));
  render(<LabStudyPage />); fireEvent.change(screen.getByLabelText("实验研究 JSON"), { target: { value: JSON.stringify(input) } });
  fireEvent.click(screen.getByRole("button", { name: "校准并验证设计" })); await screen.findByText("研究设计目标通过");
  fireEvent.click(screen.getByRole("button", { name: "回放完整研究" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("replay runtime differs");
  expect(replayLabStudy).toHaveBeenCalledWith(record, expect.any(AbortSignal));
  expect(screen.queryByText("研究设计目标通过")).not.toBeInTheDocument();
});

it("editing inputs cancels an old response and clears evidence", async () => {
  let finish!: (value: LabStudyResponse) => void;
  vi.mocked(runLabStudy).mockReturnValue(new Promise(resolve => { finish = resolve; }));
  render(<LabStudyPage />); const editor = screen.getByLabelText("实验研究 JSON");
  fireEvent.change(editor, { target: { value: JSON.stringify(input) } }); fireEvent.click(screen.getByRole("button", { name: "校准并验证设计" }));
  fireEvent.change(editor, { target: { value: "{}" } }); finish(response);
  await waitFor(() => expect(editor).toHaveValue("{}")); expect(screen.queryByText("Measured-input test question")).not.toBeInTheDocument();
});

it("invalid JSON never reaches the physics API", async () => {
  render(<LabStudyPage />); fireEvent.change(screen.getByLabelText("实验研究 JSON"), { target: { value: "{" } });
  fireEvent.click(screen.getByRole("button", { name: "校准并验证设计" })); await screen.findByRole("alert"); expect(runLabStudy).not.toHaveBeenCalled();
});
