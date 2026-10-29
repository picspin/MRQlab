import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { DeriveRadialStudy, DerivedRadialEvidence } from "../components/research/DerivedRadialStudy";
import { createScientificRecord } from "../lib/api";
import type { ScientificRecord, ScientificResponse } from "../lib/scientific-records";
vi.mock("../lib/api", () => ({ createScientificRecord: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
const parent = { record_sha256: "a".repeat(64), summary: { study_id: "calibration-01", mode: "measured_tse" } } as ScientificRecord;

it("creates a derived record from the exact parent ID without an editable T2 override", async () => {
  const saved = { record: { record_sha256: "b".repeat(64) } } as ScientificResponse;
  vi.mocked(createScientificRecord).mockResolvedValue(saved);const onCreated = vi.fn();
  render(<DeriveRadialStudy parent={parent} onCreated={onCreated} />);
  expect(screen.getByRole("button", { name: "计算并保存派生实验" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("派生目标依据"), { target: { value: "Retain strict targets and the measured uncertainty corners." } });
  fireEvent.click(screen.getByRole("button", { name: "计算并保存派生实验" }));
  await vi.waitFor(() => expect(onCreated).toHaveBeenCalledWith(saved));
  expect(vi.mocked(createScientificRecord).mock.calls[0][0]).toMatchObject({ execution: { type: "calibrated_radial_tse", parent_record_sha256: parent.record_sha256 } });
  expect(screen.queryByLabelText("基组 T2")).not.toBeInTheDocument();
});

it("rejects malformed study JSON before creating a derived computation", async () => {
  render(<DeriveRadialStudy parent={parent} onCreated={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("派生目标依据"), { target: { value: "Declared target rationale" } });
  fireEvent.change(screen.getByLabelText("派生候选 JSON"), { target: { value: "[]" } });
  fireEvent.click(screen.getByRole("button", { name: "计算并保存派生实验" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("候选与预算必须是 JSON 对象");
  expect(createScientificRecord).not.toHaveBeenCalled();
});

it("shows nominal success and corner failures as distinct evidence with physical units", () => {
  render(<DerivedRadialEvidence evidence={{ parameter_bindings: [{ tissue_id: "white_matter", value: .04, unit: "s", standard_uncertainty_s: .0001, stress_interval_s: [.0398, .0402] }],
    validation: { calibration_and_holdout_passed: true, parent_result_revalidated: true, calibrated_parameters_applied: true, complete_budgeted_search: true, selected_design_passed: false },
    provenance: { estimated_work: 100, reserved_work: 200, planned_work: 200 }, candidates: [{ index: 0, scenarios: [
      { name: "nominal", sample_t2_s: [.04, .12], basis_t2_s: [.04, .12], executable: true, passed: true, run: { quality: { nrmse: 1e-8 }, validation: { coefficient_error: 5e-7 } } },
      { name: "corner-0", sample_t2_s: [.0398, .119], basis_t2_s: [.04, .12], executable: true, passed: false, run: { quality: { nrmse: .01 }, validation: { coefficient_error: .04 } } },
    ] }] }} />);
  expect(screen.getByText("T2 参数绑定（记录单位为秒）")).toBeInTheDocument();
  expect(screen.getByText("1 / nominal").closest("tr")).toHaveTextContent("通过");
  expect(screen.getByText("1 / corner-0").closest("tr")).toHaveTextContent("未通过");
  expect(screen.getByText("40.000")).toBeInTheDocument();
});
