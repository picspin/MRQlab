import React from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import AgenticStudyPage from "../app/research/agentic-study/page";
import { createScientificRecord, fetchContrastStudyExample, replayScientificRecord } from "../lib/api";
import type { AgenticInference } from "../lib/agentic-inference";
import type { LinkedReadout } from "../lib/linked-readout";
import type { ResearchRun } from "../lib/research";
import type { ScientificPlan, ScientificResponse } from "../lib/scientific-records";

vi.mock("../lib/api", () => ({ createScientificRecord: vi.fn(), fetchContrastStudyExample: vi.fn(), replayScientificRecord: vi.fn() }));
const context = { study_id: "agentic-test", research_question: "Which identifiable proportions follow from this complete acquisition?", target_rationale: "Retain identifiability gaps" };
const plan: ScientificPlan = { context, execution: { type: "run", kind: "tse", parameters: { refocusing_angle: 140 } } };
const pair: LinkedReadout = { schema_version: "mrqlab-linked-image-vector-1", canonicalization: "typed-json-f64-v1", provenance: { adapter: "test", source_sha256: "a".repeat(64), inputs_sha256: "b".repeat(64), runtime: { python: "test" }, origin: "synthetic", source_refs: ["white_matter", "gray_matter"].map(tissue_id => ({ tissue_id, source_ref: `synthetic:${tissue_id}`, origin: "synthetic", state: { fraction: .5 } })) }, links: [], scope: "research", pair_sha256: "d".repeat(64), image: { id: "image", index_unit: "voxel", flatten_order: "C", display: "magnitude", shape: [2, 2], axes: ["y", "x"], values: { real: [1, 1, 1, 1], imag: [0, 0, 0, 0] }, value_unit: "a.u." }, signal_vector: { id: "signal", axis: "acquisition_sample", value_unit: "a.u.", complex_convention: "real + i*imag", grid_index_axes: ["y", "x"], values: { real: [0, 0, 0, 4], imag: [0, 0, 0, 0] }, grid_indices: [[0, 0], [0, 1], [1, 0], [1, 1]], normalized_coordinates: [[-.5, -.5], [-.5, 0], [0, -.5], [0, 0]], coordinate_unit: "cycles/voxel", sample_times_s: [.01, .011, .02, .021], time_unit: "s", extensions: { echo_numbers: [1, 1, 2, 2] }, timing_model: "ideal echo-held line" }, structure: { shape: [2, 2], label_grid: [[0, 1], [0, 1]], label_to_tissue_id: ["white_matter", "gray_matter"], origin: "synthetic" }, controls: [] };
const run: ResearchRun = { kind: "tse", source_hash: "a".repeat(64), result_hash: "b".repeat(64), runtime: { python: "test", numpy: "test" }, replay_request: { kind: "tse", parameters: {} }, result: { clinical_question: context.research_question, scope: "research", provenance: { physical: [] }, linked_readout: pair }, view: { images: [], curves: [], x_label: "sample", y_label: "signal", metrics: {}, validation: { passed: false } } };
const parent: ScientificResponse = { record: { schema_version: "mrqlab-scientific-record-1", record_sha256: "c".repeat(64), request_json: JSON.stringify(plan), payload_json: JSON.stringify(run), request_sha256: "e".repeat(64), payload_sha256: "f".repeat(64), api_source_hash: "a".repeat(64), sources: { sha256: "a".repeat(64), files: {} }, runtime: {}, stages: [], summary: { study_id: context.study_id, research_question: context.research_question, mode: "run", kind: "tse", selected_index: 0, model_reported_passed: false, candidate_count: 1, input_origins: ["synthetic"], scope: "research" } }, view: run.view, verification: { integrity_passed: true, computational_replay_performed: false } };
const bins = [{ echo: 1, sample_count: 2, mean_time_s: .01, kspace_energy: 8, rank: 2, nullity: 0, absolute_amplitude_identified: true, relative_residual: 0 }, { echo: 2, sample_count: 2, mean_time_s: .02, kspace_energy: 2, rank: 1, nullity: 1, absolute_amplitude_identified: false, relative_residual: 1e-16 }];
const inference: AgenticInference = { schema_version: "mrqlab-agentic-tissue-inference-1", canonicalization: "typed-json-f64-v1", source: { pair_sha256: pair.pair_sha256, linked_schema_version: pair.schema_version, adapter: "test", origin: "synthetic", source_sha256: "a".repeat(64), inputs_sha256: "b".repeat(64), runtime: { python: "test" }, image_id: "image", signal_id: "signal", shape: [2, 2], axes: ["y", "x"], tissue_ids: ["white_matter", "gray_matter"], structure_origin: "synthetic", linked_scope: "research" }, ingestion: { sample_count: 4, voxel_count: 4, complete_unique_grid_indices: true, signal_energy: 16, image_energy: 4, parseval_signal_energy: 4, parseval_image_energy: 4, parseval_relative_error: 0, transform_max_absolute_error: 0, echo_ids: [1, 2], echo_times_s: [.01, .02], echo_bins: bins }, proportions: { structure: { white_matter: { voxel_count: 2, voxel_fraction: .5 }, gray_matter: { voxel_count: 2, voxel_fraction: .5 } }, image_signal: { white_matter: { energy: 3, energy_fraction: .75, magnitude: 1.5, magnitude_fraction: .75 }, gray_matter: { energy: 1, energy_fraction: .25, magnitude: .5, magnitude_fraction: .25 } }, acquisition: { available: true, reason: null, echo_ids: [1, 2], echo_bins: bins, coefficients: { white_matter: [1, .8], gray_matter: [.3, .2] }, contrast_vs_reference: { white_matter: [0, 0], gray_matter: [-.7, -.6] }, relative_contrast_strength: { white_matter: 0, gray_matter: .7 }, apparent_relative_contrast_decay_s: { white_matter: null, gray_matter: .05 }, decay_fit_residual: { white_matter: null, gray_matter: 0 }, absolute_dc_echo: { "1": { white_matter: 1.2, gray_matter: .4 } }, identifiability: { gauge: "zero-common-mode relative coefficients", common_mode: "identified only by a sampled DC point; at most one echo", per_tissue_absolute_amplitudes: "not identifiable for echoes without the DC sample", per_tissue_t2: "not inferred from relative differences" } } }, reference: { tissue_id: "white_matter", definition: "first declared tissue" }, modalities: [{ id: "structure_voxel_share", label: "Structure voxel share", kind: "structure_proportion", shape: [2, 2], axes: ["y", "x"], values: [1, 0, 1, 0], value_unit: "relative a.u.; per-structure constant", min: 0, max: 1, basis: "declared labels", note: "not measured anatomy" }, { id: "image_signal_share", label: "Reconstructed image signal share", kind: "signal_proportion", shape: [2, 2], axes: ["y", "x"], values: [1, .33333, 1, .33333], value_unit: "relative a.u.; per-structure constant", min: .33333, max: 1, basis: "complex image energy", note: "no anatomy" }, { id: "late_relative_contrast", label: "Relative contrast vs white_matter (last echo)", kind: "relative_contrast", shape: [2, 2], axes: ["y", "x"], values: [0, -1, 0, -1], value_unit: "relative a.u.; per-structure constant", min: -1, max: 0, basis: "relative coefficients", note: "absolute T2 unidentified" }], unavailable: [{ item: "per_tissue_t2_map", reason: "only relative coefficients are identifiable" }, { item: "t1_weighted_modality", reason: "one declared TR does not identify T1" }], validation: { passed: true, checks: { pair_integrity: true, complete_signal_read: true, parseval_energy_consistency: true, echo_membership_declared: true, static_partition_linear_model: true, identifiable_coefficient_basis: true, structure_proportions_normalized: true, image_proportions_normalized: true, modalities_complete: true }, tolerances: { parseval_relative_error: 1e-9 }, scope: "numerical identifiability checks only; not physics, anatomy or clinical validation" }, limits: { max_samples: 65536, max_tissues: 16, max_echoes: 64 }, scope: "agent-readable inference; no diagnosis", inference_sha256: "9".repeat(64) };
const view: ResearchRun["view"] = { images: [{ label: "Structure voxel share", width: 2, height: 2, values: [1, 0, 1, 0], scale_group: "structure" }], curves: [{ label: "white_matter", x: [.01, .02], y: [1, .8] }], x_label: "Echo time (s)", y_label: "Identifiable relative coefficient", metrics: { "Complete complex samples read": 4, "Parseval relative error": 0 }, validation: { passed: true } };
function child(value: AgenticInference = inference): ScientificResponse {
  const record = structuredClone(parent.record);
  record.record_sha256 = "0".repeat(64); record.payload_json = JSON.stringify({ inference: value });
  record.summary = { ...record.summary, mode: "agentic_inference", kind: "agentic_inference", model_reported_passed: value.validation.passed, parent_record_sha256: parent.record.record_sha256, parent_pair_sha256: pair.pair_sha256, inference_sha256: value.inference_sha256 };
  // Deep-clone the shared view fixture so a test mutating a nested entry cannot poison later tests.
  return { record, view: { ...structuredClone(view), validation: { passed: value.validation.passed } }, verification: { integrity_passed: true, computational_replay_performed: false } };
}
beforeEach(() => { vi.resetAllMocks(); vi.mocked(fetchContrastStudyExample).mockResolvedValue(plan); vi.mocked(createScientificRecord).mockResolvedValue(parent); });
afterEach(cleanup);
async function load() { render(<AgenticStudyPage />); fireEvent.click(screen.getByRole("button", { name: "载入合成对比剂示例" })); await screen.findByText(/已载入合成结构/); }
async function baseline() { await load(); fireEvent.click(screen.getByRole("button", { name: "运行并保存父记录" })); await screen.findByText(/父记录已保存/); }

it("reads the saved complete acquisition and renders identifiable proportions and modality proxies", async () => {
  await load();
  expect(screen.getByRole("button", { name: "从父记录推断组织模态" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "运行并保存父记录" })); await screen.findByText(/父记录已保存/);
  expect(screen.getByLabelText("参考组织")).toHaveValue("white_matter");
  vi.mocked(createScientificRecord).mockResolvedValueOnce(child());
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" })); await screen.findByText(/推断已保存/);
  expect(createScientificRecord).toHaveBeenLastCalledWith({ context, execution: { type: "agentic_inference", parent_record_sha256: parent.record.record_sha256, reference_tissue_id: "white_matter" } }, expect.any(AbortSignal));
  expect(screen.getByRole("heading", { name: "结构层面比例呈现" })).toBeInTheDocument();
  expect(screen.getAllByText("75.000%").length).toBeGreaterThan(0);
  expect(screen.getAllByText("25.000%").length).toBeGreaterThan(0);
  expect(screen.getAllByText("可识别").length).toBeGreaterThan(0);
  expect(screen.getAllByText("仅相对").length).toBeGreaterThan(0);
  expect(screen.getByText("0.050000")).toBeInTheDocument();
  expect(screen.getByText(/每组织 T2 图：only relative coefficients/)).toBeInTheDocument();
  expect(screen.getByText(new RegExp("数值可识别性检查："))).toBeInTheDocument();
  expect(screen.queryByText("组织 × 回波系数")).toBeInTheDocument();
});

it("changing the reference hides stale output and sends the explicit reference on re-inference", async () => {
  await baseline(); vi.mocked(createScientificRecord).mockResolvedValueOnce(child());
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" })); await screen.findByText(/推断已保存/);
  expect(screen.getByRole("heading", { name: "结构层面比例呈现" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("参考组织"), { target: { value: "gray_matter" } });
  expect(screen.queryByRole("heading", { name: "结构层面比例呈现" })).not.toBeInTheDocument();
  const gray = structuredClone(inference); gray.reference = { tissue_id: "gray_matter", definition: "explicit request" };
  vi.mocked(createScientificRecord).mockResolvedValueOnce(child(gray));
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" })); await screen.findByText(/参考组织：gray_matter/);
  expect(createScientificRecord).toHaveBeenLastCalledWith({ context, execution: { type: "agentic_inference", parent_record_sha256: parent.record.record_sha256, reference_tissue_id: "gray_matter" } }, expect.any(AbortSignal));
});

it("keeps missing echo coefficients explicit instead of fabricating an acquisition table", async () => {
  await baseline();
  const missing = structuredClone(inference);
  missing.ingestion.echo_ids = []; missing.ingestion.echo_bins = [];
  missing.proportions.acquisition = { ...missing.proportions.acquisition, available: false, reason: "signal_vector.extensions.echo_numbers is not declared", echo_ids: [], echo_bins: [], coefficients: {}, contrast_vs_reference: {}, relative_contrast_strength: {}, apparent_relative_contrast_decay_s: {}, decay_fit_residual: {}, absolute_dc_echo: {} };
  missing.validation = { ...missing.validation, passed: false, checks: { ...missing.validation.checks, echo_membership_declared: false, static_partition_linear_model: false, identifiable_coefficient_basis: false } };
  missing.unavailable = [{ item: "per_echo_coefficients", reason: "signal_vector.extensions.echo_numbers is not declared" }];
  vi.mocked(createScientificRecord).mockResolvedValueOnce(child(missing));
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" })); await screen.findByText(/推断已保存/);
  expect(screen.getByRole("note")).toHaveTextContent("逐回波系数不可用：signal_vector.extensions.echo_numbers is not declared");
  expect(screen.queryByText("组织 × 回波系数")).not.toBeInTheDocument();
  expect(screen.getAllByText("未通过").length).toBeGreaterThan(0);
  expect(screen.getByText(/逐回波组织系数：signal_vector.extensions.echo_numbers/)).toBeInTheDocument();
});

it("a record without an inference payload is rejected and leaves no old result", async () => {
  await baseline();
  const malformed = structuredClone(child()); malformed.record.payload_json = JSON.stringify({});
  vi.mocked(createScientificRecord).mockResolvedValueOnce(malformed);
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("记录缺少可识别的 agentic 推断载荷");
  expect(screen.queryByRole("heading", { name: "结构层面比例呈现" })).not.toBeInTheDocument();
});

it("a schema-matching payload without proportions is rejected before rendering and leaves no old result", async () => {
  await baseline(); vi.mocked(createScientificRecord).mockResolvedValueOnce(child());
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" })); await screen.findByText(/推断已保存/);
  const { proportions: _omitted, ...withoutProportions } = structuredClone(inference) as unknown as Record<string, unknown>;
  vi.mocked(createScientificRecord).mockResolvedValueOnce(child(withoutProportions as unknown as AgenticInference));
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("记录载荷缺少推断渲染所需的比例结构。");
  expect(screen.queryByRole("heading", { name: "结构层面比例呈现" })).not.toBeInTheDocument();
});

it("a schema-matching payload missing a declared tissue's proportions is rejected before rendering", async () => {
  await baseline();
  const partial = structuredClone(inference); delete (partial.proportions.image_signal as Record<string, unknown>).gray_matter;
  vi.mocked(createScientificRecord).mockResolvedValueOnce(child(partial));
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("记录载荷缺少推断渲染所需的比例结构。");
  expect(screen.queryByRole("heading", { name: "结构层面比例呈现" })).not.toBeInTheDocument();
});

it("a schema-matching available payload without coefficient maps is rejected before rendering", async () => {
  await baseline();
  const noCoefficients = structuredClone(inference) as unknown as Record<string, Record<string, Record<string, unknown>>>;
  delete noCoefficients.proportions.acquisition.contrast_vs_reference;
  vi.mocked(createScientificRecord).mockResolvedValueOnce(child(noCoefficients as unknown as AgenticInference));
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("记录载荷缺少推断渲染所需的比例结构。");
  expect(screen.queryByRole("heading", { name: "结构层面比例呈现" })).not.toBeInTheDocument();
});

async function rejectsMalformedNested(mutate: (value: Record<string, any>) => void) {
  await baseline(); vi.mocked(createScientificRecord).mockResolvedValueOnce(child());
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" })); await screen.findByText(/推断已保存/);
  const malformed = structuredClone(inference) as unknown as Record<string, any>;
  mutate(malformed);
  vi.mocked(createScientificRecord).mockResolvedValueOnce(child(malformed as unknown as AgenticInference));
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("记录载荷缺少推断渲染所需的比例结构。");
  expect(screen.queryByRole("heading", { name: "结构层面比例呈现" })).not.toBeInTheDocument();
}

it("a coefficient value of the wrong type is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedNested(value => { value.proportions.acquisition.coefficients.white_matter[0] = "bad"; });
});

it("an echo-bin entry of the wrong type is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedNested(value => { value.ingestion.echo_bins[0] = null; });
});

it("a null unavailable entry is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedNested(value => { value.unavailable = [null]; });
});

it("an unavailable reason that is not a string is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedNested(value => { value.unavailable[0].reason = { bad: true }; });
});

it("an echo-bin relative_residual of the wrong type is rejected before rendering", async () => {
  await rejectsMalformedNested(value => { value.ingestion.echo_bins[0].relative_residual = "bad"; });
});

it("an echo-bin rank that is an object is rejected before rendering", async () => {
  await rejectsMalformedNested(value => { value.ingestion.echo_bins[0].rank = { bad: true }; });
});

it("an echo-bin nullity that is an object is rejected before rendering", async () => {
  await rejectsMalformedNested(value => { value.ingestion.echo_bins[0].nullity = { bad: true }; });
});

it("a null absolute_dc_echo entry is rejected before rendering", async () => {
  await rejectsMalformedNested(value => { value.proportions.acquisition.absolute_dc_echo["1"] = null; });
});

it("an absolute_dc_echo tissue value of the wrong type is rejected before rendering", async () => {
  await rejectsMalformedNested(value => { value.proportions.acquisition.absolute_dc_echo["1"].white_matter = "bad"; });
});

it("a relative_contrast_strength value of the wrong type is rejected before rendering", async () => {
  await rejectsMalformedNested(value => { value.proportions.acquisition.relative_contrast_strength.white_matter = "bad"; });
});

it("an apparent_relative_contrast_decay_s value of the wrong type is rejected before rendering", async () => {
  await rejectsMalformedNested(value => { value.proportions.acquisition.apparent_relative_contrast_decay_s.gray_matter = "bad"; });
});

it("a decay_fit_residual value of the wrong type is rejected before rendering", async () => {
  await rejectsMalformedNested(value => { value.proportions.acquisition.decay_fit_residual.gray_matter = "bad"; });
});

it("a structure voxel_count of the wrong type is rejected before rendering", async () => {
  await rejectsMalformedNested(value => { value.proportions.structure.white_matter.voxel_count = { bad: true }; });
});

it("a reference definition that is not a string is rejected before rendering", async () => {
  await rejectsMalformedNested(value => { value.reference.definition = { bad: true }; });
});

it("an ingestion echo id that is an object is rejected before rendering", async () => {
  await rejectsMalformedNested(value => { value.ingestion.echo_ids[0] = { bad: true }; });
});

it("an unavailable acquisition reason that is an object is rejected before rendering", async () => {
  await rejectsMalformedNested(value => {
    value.proportions.acquisition.available = false;
    value.proportions.acquisition.reason = { bad: true };
  });
});

it("coefficient maps replaced with arrays are rejected before rendering", async () => {
  await rejectsMalformedNested(value => {
    value.proportions.acquisition.coefficients = [[1, .8], [.3, .2]];
    value.proportions.acquisition.contrast_vs_reference = [];
  });
});

it("a valid payload with every nested rendered surface still renders all acquisition tables", async () => {
  await baseline(); vi.mocked(createScientificRecord).mockResolvedValueOnce(child());
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" })); await screen.findByText(/推断已保存/);
  expect(screen.getByRole("heading", { name: "回波可识别性" })).toBeInTheDocument();
  expect(screen.getByText("组织 × 回波系数")).toBeInTheDocument();
  expect(screen.getByText("直流回波绝对幅度（唯一绝对可识别回波）")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "参考相对对比与表观衰减" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "明确未生成的组织模态" })).toBeInTheDocument();
});

it("legitimate payloads still render after nested validation", async () => {
  await baseline(); vi.mocked(createScientificRecord).mockResolvedValueOnce(child());
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" })); await screen.findByText(/推断已保存/);
  expect(screen.getByRole("heading", { name: "结构层面比例呈现" })).toBeInTheDocument();
});

it("the intro describes deterministic numerical inference rather than an LLM reading the signal", () => {
  render(<AgenticStudyPage />);
  expect(screen.getByText(/确定性数值推断读取完整采集信号/)).toBeInTheDocument();
  expect(screen.queryByText(/LLM 直接读取/)).not.toBeInTheDocument();
});

it("full replay needs an explicit matching receipt and hides output on failure", async () => {
  await baseline(); vi.mocked(createScientificRecord).mockResolvedValueOnce(child());
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" })); await screen.findByText(/推断已保存/);
  vi.mocked(replayScientificRecord).mockResolvedValue({ integrity_passed: true, computational_replay_performed: true, record_sha256: "0".repeat(64), payload_sha256: "f".repeat(64), summary: child().record.summary });
  fireEvent.click(screen.getByRole("button", { name: "完整回放当前记录" })); await screen.findByText(/完整回放一致/);
  expect(replayScientificRecord).toHaveBeenCalledWith("0".repeat(64), expect.any(AbortSignal));
  expect(screen.getByRole("heading", { name: "结构层面比例呈现" })).toBeInTheDocument();
  vi.mocked(replayScientificRecord).mockRejectedValueOnce(new Error("source changed"));
  fireEvent.click(screen.getByRole("button", { name: "完整回放当前记录" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("source changed");
  expect(screen.queryByRole("heading", { name: "结构层面比例呈现" })).not.toBeInTheDocument();
});

it("editing the baseline aborts old output and disables inference", async () => {
  await baseline(); vi.mocked(createScientificRecord).mockResolvedValueOnce(child());
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" })); await screen.findByText(/推断已保存/);
  fireEvent.change(screen.getByLabelText("Agent 基线科学计划"), { target: { value: "{}" } });
  expect(screen.queryByRole("heading", { name: "结构层面比例呈现" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "从父记录推断组织模态" })).toBeDisabled();
});

it("invalid initial plans never reach the physics API", async () => {
  await load(); fireEvent.change(screen.getByLabelText("Agent 基线科学计划"), { target: { value: "{}" } });
  fireEvent.click(screen.getByRole("button", { name: "运行并保存父记录" })); await screen.findByRole("alert");
  expect(createScientificRecord).not.toHaveBeenCalled();
});

// Major 1: label lookups must read own properties only. Keys arrive as untyped JSON, so "__proto__" and "constructor" must render as raw text.
it.each(["__proto__", "constructor"])("an unavailable item named %s renders its raw key instead of crashing", async name => {
  await baseline();
  const value = structuredClone(inference);
  value.unavailable = [{ item: name, reason: "probe" }];
  vi.mocked(createScientificRecord).mockResolvedValueOnce(child(value));
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" })); await screen.findByText(/推断已保存/);
  expect(screen.getByText(`${name}：probe`)).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it.each(["__proto__", "constructor"])("a validation check named %s renders its raw key instead of crashing", async name => {
  await baseline();
  const value = structuredClone(inference);
  value.validation.checks = JSON.parse(`{"${name}": true}`);
  vi.mocked(createScientificRecord).mockResolvedValueOnce(child(value));
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" })); await screen.findByText(/推断已保存/);
  expect(screen.getByText(name, { selector: "dt" }).nextElementSibling).toHaveTextContent("通过");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

// Major 2: a tissue whose own entry is missing from one per-tissue map must render "—" rather than read an inherited prototype value.
// Tissue names are injected as own JSON keys; each map is removed in isolation so every map is covered on its own.
const contrastMaps = ["contrast_vs_reference", "relative_contrast_strength", "apparent_relative_contrast_decay_s", "decay_fit_residual"] as const;
// Column index in "相对对比、强度与拟合" (组织=0) and the text a missing own entry must render as.
const renderedCell: Record<(typeof contrastMaps)[number], { index: number; text: string }> = {
  contrast_vs_reference: { index: 1, text: "—" }, relative_contrast_strength: { index: 5, text: "—" },
  apparent_relative_contrast_decay_s: { index: 3, text: "不可识别" }, decay_fit_residual: { index: 4, text: "不可识别" },
};
function withTissue(from: string, to: string): AgenticInference {
  return JSON.parse(JSON.stringify(inference).split(`"${from}"`).join(`"${to}"`));
}
it.each(contrastMaps.flatMap(map => ["__proto__", "constructor"].map(name => [map, name] as const)))("a missing own %s entry for tissue %s renders as a dash instead of inherited values", async (map, name) => {
  await baseline();
  const value = withTissue("gray_matter", name);
  Reflect.deleteProperty(value.proportions.acquisition[map], name);
  vi.mocked(createScientificRecord).mockResolvedValueOnce(child(value));
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" })); await screen.findByText(/推断已保存/);
  const table = screen.getByRole("table", { name: "相对对比、强度与拟合" });
  const row = within(table).getByText(name, { selector: "td" }).closest("tr")!;
  const cell = renderedCell[map];
  expect(within(row).getAllByRole("cell")[cell.index]).toHaveTextContent(cell.text);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

// Major 3: outer response fields the page renders must be validated before the response is committed.
async function rejectsMalformedResponse(mutate: (response: ScientificResponse) => void) {
  await baseline(); vi.mocked(createScientificRecord).mockResolvedValueOnce(child());
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" })); await screen.findByText(/推断已保存/);
  const malformed = child(); mutate(malformed);
  vi.mocked(createScientificRecord).mockResolvedValueOnce(malformed);
  fireEvent.click(screen.getByRole("button", { name: "从父记录推断组织模态" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("记录载荷缺少推断渲染所需的比例结构。");
  expect(screen.queryByRole("heading", { name: "结构层面比例呈现" })).not.toBeInTheDocument();
}
it("a non-numeric view metric is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedResponse(response => { const view = response.view as unknown as Record<string, unknown>; view.metrics = { ...(view.metrics as object), bad: { bad: true } }; });
});
it("a non-string record_sha256 is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedResponse(response => { (response.record as unknown as Record<string, unknown>).record_sha256 = { bad: true }; });
});
it("a non-string parent_record_sha256 is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedResponse(response => { (response.record.summary as unknown as Record<string, unknown>).parent_record_sha256 = { bad: true }; });
});
it("a non-string parent_pair_sha256 is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedResponse(response => { (response.record.summary as unknown as Record<string, unknown>).parent_pair_sha256 = { bad: true }; });
});

// Major 4 (Codex review of 1b0d458): Measurements consumes the complete outer view, so every field it reads must be
// validated before the response is committed. Each mutation keeps the inference payload valid and breaks one field only.
const malformedView = (response: ScientificResponse): Record<string, any> => response.view as unknown as Record<string, any>;
it("a null view.images is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedResponse(response => { malformedView(response).images = null; });
});
it("a null view.curves is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedResponse(response => { malformedView(response).curves = null; });
});
it("a null image values array is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedResponse(response => { malformedView(response).images[0].values = null; });
});
it("a non-string image label is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedResponse(response => { malformedView(response).images[0].label = { bad: true }; });
});
it("a curve whose y array is shorter than x is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedResponse(response => {
    const curve = malformedView(response).curves[0];
    expect(curve.x.length).toBeGreaterThan(0);
    curve.y = [];
  });
});
it("a non-string curve label is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedResponse(response => { malformedView(response).curves[0].label = { bad: true }; });
});
it("a non-string x_label is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedResponse(response => { malformedView(response).x_label = { bad: true }; });
});
it("a non-string y_label is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedResponse(response => { malformedView(response).y_label = { bad: true }; });
});
it("a null view.validation is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedResponse(response => { malformedView(response).validation = null; });
});
it("a view without metrics is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedResponse(response => { delete malformedView(response).metrics; });
});

// Major 5 (Codex review of c6fce75): a finite validation entry named after an Object.prototype member
// passed the value-only check, then resolved to an inherited object in the renderer's target-label table
// and crashed React. Finite values alone are not enough; inherited target names must be rejected.
it.each(["__proto__", "constructor"])("a numeric validation entry named %s is rejected before rendering and leaves no old result", async name => {
  await rejectsMalformedResponse(response => {
    malformedView(response).validation = JSON.parse(`{"passed":true,"${name}":1}`);
  });
});

// Major 6 (Codex review of c6fce75): Measurements flattens every curve and spreads it into Math.min/Math.max,
// so an unbounded point count crashes rendering with "Maximum call stack size exceeded". Bound both each
// curve and the combined count (the renderer computes one extent across all curves).
it("a single curve beyond the bounded preview point count is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedResponse(response => {
    const curve = malformedView(response).curves[0];
    const xs = Array.from({ length: 150000 }, (_, index) => index);
    curve.x = xs; curve.y = xs.slice();
  });
});
it("curves within the per-curve limit whose combined point count exceeds the preview bound are rejected before rendering and leave no old result", async () => {
  await rejectsMalformedResponse(response => {
    const xs = Array.from({ length: 6000 }, (_, index) => index);
    malformedView(response).curves = [{ label: "a", x: xs, y: xs.slice() }, { label: "b", x: xs, y: xs.slice() }];
  });
});

// Minor (Codex review of c6fce75): every y value participates in the vertical axis extent even though the
// value table only indexes y[0..x.length-1]; a longer y therefore silently rescales the plotted curve.
it("a curve whose y array is longer than x is rejected before rendering and leaves no old result", async () => {
  await rejectsMalformedResponse(response => {
    const curve = malformedView(response).curves[0];
    expect(curve.x).toEqual([.01, .02]);
    curve.y = [1, .8, 1e12];
  });
});
