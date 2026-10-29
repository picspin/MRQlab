import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import ResearchPage from "../app/research/page";
import { runResearch, searchResearch } from "../lib/api";
import type { ResearchRun } from "../lib/research";
vi.mock("../lib/api", () => ({ runResearch: vi.fn(), searchResearch: vi.fn() }));
const result: ResearchRun = {
  kind: "tse", result: { clinical_question: "Measured test question", scope: "research only", provenance: {} },
  view: { images: [], curves: [{ label: "tissue", x: [0, 1], y: [1, .8] }], x_label: "Time", y_label: "Signal", validation: { passed: false }, metrics: { NRMSE: .2 } },
  replay_request: { kind: "tse", parameters: { echoes: 4 }, expected_source_hash: "a".repeat(64) },
  source_hash: "a".repeat(64), result_hash: "b".repeat(64), runtime: { python: "3.15", numpy: "2" },
};
beforeEach(() => { vi.resetAllMocks(); });
afterEach(cleanup);
it("runs backend and replays the exact request", async () => {
  vi.mocked(runResearch).mockResolvedValue(result); render(<ResearchPage />);
  expect(screen.queryByText("Measured test question")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "运行仿真" })); await screen.findByText("目标未通过");
  fireEvent.click(screen.getByRole("button", { name: "回放此结果" })); await screen.findByText("回放一致：结果哈希匹配。");
  expect(vi.mocked(runResearch).mock.calls[1][0]).toEqual(result.replay_request);
});
it("clears previous measurements after a design edit", async () => {
  vi.mocked(runResearch).mockResolvedValue(result); render(<ResearchPage />);
  fireEvent.click(screen.getByRole("button", { name: "运行仿真" })); await screen.findByText("Measured test question");
  fireEvent.change(screen.getByLabelText("回波数"), { target: { value: "8" } });
  expect(screen.queryByText("Measured test question")).not.toBeInTheDocument();
  expect((screen.getByLabelText("完整参数 JSON") as HTMLTextAreaElement).value).toContain('"echoes": 8');
});
it("shows backend errors without fabricated measurements", async () => {
  vi.mocked(runResearch).mockRejectedValue(new Error("API unavailable")); render(<ResearchPage />);
  fireEvent.click(screen.getByRole("button", { name: "运行仿真" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("API unavailable");
  expect(screen.queryByRole("button", { name: "导出完整记录" })).not.toBeInTheDocument();
});
it("rejects invalid JSON before simulation", async () => {
  render(<ResearchPage />); fireEvent.change(screen.getByLabelText("完整参数 JSON"), { target: { value: "{" } });
  fireEvent.click(screen.getByRole("button", { name: "运行仿真" })); await screen.findByRole("alert");
  expect(runResearch).not.toHaveBeenCalled();
});
it("reports candidate execution and target validation separately", async () => {
  vi.mocked(searchResearch).mockResolvedValue({ replay_search: { kind: "tse", parameters: {}, candidates: [{ echoes: 4 }] }, search_hash: "c".repeat(64), best: { parameters: { echoes: 4 }, loss: .2, run: result }, candidates: [
    { parameters: { echoes: 3 }, feasible: false, reason: "timing invalid" },
    { parameters: { echoes: 4 }, feasible: true, loss: .2, run: result },
  ], objective: "declared model loss" });
  render(<ResearchPage />); fireEvent.click(screen.getByRole("button", { name: "比较候选设计" }));
  await screen.findByText("有限网格比较"); expect(screen.getByText("timing invalid")).toBeInTheDocument();
  expect(screen.getAllByText("未通过").length).toBeGreaterThan(0);
});
it("ignores stale responses after switching experiment", async () => {
  let finish!: (value: ResearchRun) => void;
  vi.mocked(runResearch).mockReturnValue(new Promise(resolve => { finish = resolve; })); render(<ResearchPage />);
  fireEvent.click(screen.getByRole("button", { name: "运行仿真" })); fireEvent.click(screen.getByRole("button", { name: "MRS basis fit" }));
  finish(result); await waitFor(() => expect(screen.getByLabelText("基组 J (Hz)")).toBeInTheDocument());
  expect(screen.queryByText("Measured test question")).not.toBeInTheDocument();
});


it("exports a complete candidate record and waits before revoking the object URL", async () => {
  const search = { replay_search: { kind: "tse" as const, parameters: {}, candidates: [{ echoes: 4 }], expected_source_hash: result.source_hash }, search_hash: "c".repeat(64),
    best: { parameters: { echoes: 4 }, loss: .2, run: result },
    candidates: [{ parameters: { echoes: 4 }, feasible: true, loss: .2, run: result }], objective: "model loss" };
  vi.mocked(searchResearch).mockResolvedValue(search);
  let exported: Blob | undefined;
  const create = vi.fn((blob: Blob) => { exported = blob; return "blob:test-record"; });
  const revoke = vi.fn();
  vi.stubGlobal("URL", { createObjectURL: create, revokeObjectURL: revoke });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    expect(this.isConnected).toBe(true); expect(this.download).toMatch(/mrqlab-tse/);
  });
  try {
    render(<ResearchPage />); fireEvent.click(screen.getByRole("button", { name: "比较候选设计" }));
    await screen.findByText("有限网格比较"); fireEvent.click(screen.getByRole("button", { name: "导出完整记录" }));
    expect(create).toHaveBeenCalled(); expect(revoke).not.toHaveBeenCalled(); expect(click).toHaveBeenCalled();
    const text = await new Promise<string>((resolve) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(exported!); });
    const record = JSON.parse(text); expect(record.search.search_hash).toBe(search.search_hash);
    expect(record.search.candidates).toHaveLength(1); expect(record.replay_request).toEqual(result.replay_request);
    await waitFor(() => expect(revoke).toHaveBeenCalledWith("blob:test-record"), { timeout: 2000 });
  } finally { click.mockRestore(); vi.unstubAllGlobals(); }
});

it("imports a pinned run without displaying it as a fresh measurement", async () => {
  vi.mocked(runResearch).mockResolvedValue(result);
  const file = new File(["record"], "replay.json", { type: "application/json" });
  Object.defineProperty(file, "text", { value: async () => JSON.stringify(result) });
  render(<ResearchPage />); fireEvent.change(screen.getByLabelText("导入回放记录"), { target: { files: [file] } });
  await screen.findByText("记录已载入。运行将核对源码指纹和结果哈希。");
  expect(screen.queryByText("Measured test question")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "运行导入回放" })); await screen.findByText("回放一致：结果哈希匹配。");
  expect(vi.mocked(runResearch).mock.calls[0][0]).toEqual(result.replay_request);
});


it("submits the explicitly selected NUFFT inverse and clears stale results", async () => {
  vi.mocked(runResearch).mockResolvedValue(result); render(<ResearchPage />);
  fireEvent.click(screen.getByRole("button", { name: "Radial inverse" }));
  fireEvent.change(screen.getByLabelText("重建方法"), { target: { value: "nufft_cgls" } });
  fireEvent.click(screen.getByRole("button", { name: "运行仿真" }));
  await screen.findByText("Measured test question");
  expect(vi.mocked(runResearch).mock.calls[0][0]).toMatchObject({ kind: "noncartesian", parameters: { reconstruction: "nufft_cgls" } });
  fireEvent.change(screen.getByLabelText("重建方法"), { target: { value: "cgls" } });
  expect(screen.queryByText("Measured test question")).not.toBeInTheDocument();
});
