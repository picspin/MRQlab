import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import ContrastStudyPage from "../app/research/contrast-study/page";
import { createScientificRecord, fetchContrastStudyExample, replayScientificRecord } from "../lib/api";
import type { LinkedReadout } from "../lib/linked-readout";
import type { ResearchRun } from "../lib/research";
import type { ScientificPlan, ScientificResponse } from "../lib/scientific-records";

vi.mock("../lib/api", () => ({ createScientificRecord: vi.fn(), fetchContrastStudyExample: vi.fn(), replayScientificRecord: vi.fn() }));
const context = { study_id: "contrast-test", research_question: "Synthetic contrast question", target_rationale: "Retain target failure" };
const plan: ScientificPlan = { context, execution: { type: "run", kind: "tse", parameters: { refocusing_angle: 140 } } };
const pair: LinkedReadout = { schema_version: "mrqlab-image-signal-pair-1", pair_sha256: "d".repeat(64), image: { shape: [2, 2], axes: ["y", "x"], values: { real: [1, 1, 1, 1], imag: [0, 0, 0, 0] }, value_unit: "a.u." }, signal_vector: { values: { real: [4, 0, 0, 0], imag: [0, 0, 0, 0] }, grid_indices: [[0, 0], [0, 1], [1, 0], [1, 1]], normalized_coordinates: [], coordinate_unit: "cycles/voxel", sample_times_s: [.01, .011, .02, .021], time_unit: "s", echo_numbers: [1, 1, 2, 2], timing_model: "ideal echo-held line" }, structure: { label_to_tissue_id: ["white_matter", "gray_matter"], origin: "synthetic" }, controls: [{ field: "rf.refocusing_start_deg", value: 140, unit: "deg" }, { field: "tissue.concentration_mmol_l", tissue_id: "gray_matter", value: .2, unit: "mmol/L", min: 0, max: 1 }] };
const run: ResearchRun = { kind: "tse", source_hash: "a".repeat(64), result_hash: "b".repeat(64), runtime: { python: "test", numpy: "test" }, replay_request: { kind: "tse", parameters: {} }, result: { clinical_question: context.research_question, scope: "research", provenance: { physical: [] }, linked_readout: pair }, view: { images: [], curves: [], x_label: "sample", y_label: "signal", metrics: {}, validation: { passed: false } } };
const parent: ScientificResponse = { record: { schema_version: "mrqlab-scientific-record-1", record_sha256: "c".repeat(64), request_json: JSON.stringify(plan), payload_json: JSON.stringify(run), request_sha256: "e".repeat(64), payload_sha256: "f".repeat(64), api_source_hash: "a".repeat(64), sources: { sha256: "a".repeat(64), files: {} }, runtime: {}, stages: [], summary: { study_id: context.study_id, research_question: context.research_question, mode: "run", kind: "tse", selected_index: 0, model_reported_passed: false, candidate_count: 1, input_origins: ["synthetic"], scope: "research" } }, view: run.view, verification: { integrity_passed: true, computational_replay_performed: false } };
beforeEach(() => { vi.resetAllMocks(); vi.mocked(fetchContrastStudyExample).mockResolvedValue(plan); vi.mocked(createScientificRecord).mockResolvedValue(parent); });
afterEach(cleanup);
async function load() { render(<ContrastStudyPage />); fireEvent.click(screen.getByRole("button", { name: "载入合成对比剂示例" })); await screen.findByText(/已载入合成结构/); }
async function baseline() { await load(); fireEvent.click(screen.getByRole("button", { name: "运行并保存基线" })); await screen.findByRole("heading", { name: "Agent 信号向量" }); }

it("runs an explicit synthetic baseline with shared images and complete complex vectors", async () => {
  render(<ContrastStudyPage />); expect(screen.getByRole("button", { name: "运行并保存基线" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "载入合成对比剂示例" })); await screen.findByText(/已载入合成结构/);
  fireEvent.click(screen.getByRole("button", { name: "运行并保存基线" })); await screen.findByRole("heading", { name: "Agent 信号向量" });
  expect(createScientificRecord).toHaveBeenCalledWith(plan, expect.any(AbortSignal));
  expect(screen.getByText(/完整 4 个复数样本/)).toBeInTheDocument();
  expect(screen.getAllByText("未通过").length).toBeGreaterThan(0);
});

it("concentration controls invoke the same typed parent-derived computation contract", async () => {
  await baseline();
  const child = structuredClone(parent); child.record.record_sha256 = "0".repeat(64); child.record.summary.mode = "edited_tse"; child.record.summary.parent_record_sha256 = parent.record.record_sha256;
  child.record.payload_json = JSON.stringify({ run }); vi.mocked(createScientificRecord).mockResolvedValueOnce(child);
  fireEvent.change(screen.getByLabelText("组织浓度 gray_matter"), { target: { value: ".4" } });
  expect(screen.queryByRole("heading", { name: "Agent 信号向量" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "重算父记录并应用修改" })); await screen.findByText(/父记录已完整重算/);
  expect(createScientificRecord).toHaveBeenLastCalledWith({ context, execution: { type: "edited_tse", parent_record_sha256: parent.record.record_sha256, updates: [{ field: "tissue.concentration_mmol_l", tissue_id: "gray_matter", value: .4 }] } }, expect.any(AbortSignal));
  expect(screen.getByText(`父记录：${parent.record.record_sha256}`)).toBeInTheDocument();
});

it("empty parameter input never becomes a silent zero concentration", async () => {
  await baseline(); fireEvent.change(screen.getByLabelText("组织浓度 gray_matter"), { target: { value: "" } });
  fireEvent.click(screen.getByRole("button", { name: "重算父记录并应用修改" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("请输入有限且有明确单位的参数"); expect(createScientificRecord).toHaveBeenCalledTimes(1);
});

it("editing the baseline aborts old output and cannot show stale images", async () => {
  let finish!: (r: ScientificResponse) => void; vi.mocked(createScientificRecord).mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
  await load(); fireEvent.click(screen.getByRole("button", { name: "运行并保存基线" }));
  fireEvent.change(screen.getByLabelText("对比剂基线计划"), { target: { value: "{}" } }); finish(parent);
  await waitFor(() => expect(screen.getByLabelText("对比剂基线计划")).toHaveValue("{}"));
  expect(screen.queryByRole("heading", { name: "Agent 信号向量" })).not.toBeInTheDocument();
});

it("invalid initial plans never reach the physics API", async () => {
  await load(); fireEvent.change(screen.getByLabelText("对比剂基线计划"), { target: { value: "{}" } });
  fireEvent.click(screen.getByRole("button", { name: "运行并保存基线" })); await screen.findByRole("alert");
  expect(createScientificRecord).not.toHaveBeenCalled();
});

it("full current-record replay requires an explicit matching backend receipt", async () => {
  await baseline(); vi.mocked(replayScientificRecord).mockResolvedValue({ integrity_passed: true, computational_replay_performed: true, record_sha256: parent.record.record_sha256, payload_sha256: "f".repeat(64), summary: parent.record.summary });
  fireEvent.click(screen.getByRole("button", { name: "完整回放当前记录" })); await screen.findByText(/完整回放一致：父记录/);
  expect(replayScientificRecord).toHaveBeenCalledWith(parent.record.record_sha256, expect.any(AbortSignal));
});

it("source or runtime replay failure clears the displayed pair", async () => {
  await baseline(); vi.mocked(replayScientificRecord).mockRejectedValue(new Error("source changed"));
  fireEvent.click(screen.getByRole("button", { name: "完整回放当前记录" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("source changed");
  expect(screen.queryByRole("heading", { name: "Agent 信号向量" })).not.toBeInTheDocument();
});
