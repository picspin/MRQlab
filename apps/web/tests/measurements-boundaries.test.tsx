import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import Measurements from "../components/research/Measurements";
import type { ResearchRun } from "../lib/research";

const valid: ResearchRun["view"] = {
  images: [], curves: [{ label: "signal", x: [0, 1], y: [1, .8] }], x_label: "Time", y_label: "Signal",
  validation: { passed: true }, metrics: { score: .8 },
};
afterEach(cleanup);
function rejectsView(view: unknown) {
  render(<Measurements view={view as ResearchRun["view"]} />);
  expect(screen.getByRole("alert")).toHaveTextContent("记录载荷缺少可安全显示的测量结构。");
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
}

it("rejects inherited validation labels such as an own __proto__ JSON key", () => {
  const validation = JSON.parse('{"passed":true,"__proto__":1}');
  rejectsView({ ...valid, validation });
});
it("rejects a curve large enough to overflow spread-based SVG range calculation", () => {
  const values = Array(150000).fill(1);
  rejectsView({ ...valid, curves: [{ label: "large", x: values, y: values }] });
});
it("rejects aggregate curve points beyond the renderer budget", () => {
  const values = Array(6000).fill(1);
  rejectsView({ ...valid, curves: [{ label: "a", x: values, y: values }, { label: "b", x: values, y: values }] });
});
it("rejects unmatched y tails that would distort the plotted scale", () => {
  rejectsView({ ...valid, curves: [{ label: "signal", x: [.01, .02], y: [1, .8, 1e12] }] });
});
it("rejects a numeric validation field whose key is inherited by the label map", () => {
  const validation = JSON.parse('{"passed":true,"constructor":1}');
  rejectsView({ ...valid, validation });
});
it("renders a valid view with paired curve samples", () => {
  render(<Measurements view={valid} />);
  expect(screen.getByRole("img", { name: "Signal versus Time" })).toBeInTheDocument();
  expect(screen.getByRole("table", { name: "目标与测量" })).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
