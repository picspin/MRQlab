import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkspaceProvider, useWorkspace } from "../components/workspace/WorkspaceProvider";
import { WorkbenchCockpit } from "../components/workbench/WorkbenchCockpit";
import { SlabStackView } from "../components/workbench/SlabStackView";
import { SequenceIRTimeline } from "../components/workbench/SequenceIRTimeline";
import type { SequenceIR } from "../lib/sequence-ir";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function PhysicsWorkbench() {
  const { setProfile } = useWorkspace();
  return (
    <div>
      <button onClick={() => setProfile("physics")}>Set Physics</button>
      <WorkbenchCockpit />
    </div>
  );
}

describe("Wave B/D: remaining review gaps", () => {
  it("renders clinical slab rectangles whose height follows thickness and gap is empty space", () => {
    render(
      <SlabStackView
        sliceCount={4}
        sliceThickMm={8}
        sliceGapMm={4}
        isInterleaved
        cursorIndex={2}
        onSelect={() => undefined}
      />,
    );
    const slices = screen.getAllByTestId(/slab-slice-/);
    expect(slices).toHaveLength(4);
    const gaps = screen.getAllByTestId(/slab-gap-/);
    expect(gaps).toHaveLength(3);
    expect(Number(slices[0].getAttribute("data-thick-mm"))).toBe(8);
    expect(Number(gaps[0].getAttribute("data-gap-mm"))).toBe(4);
    expect(screen.getByTestId("slab-extent")).toHaveTextContent("44.0mm");
  });

  it("exposes Clinical TR and Physics excitation FA + ADC bandwidth on the Control Bank", () => {
    render(
      <WorkspaceProvider>
        <PhysicsWorkbench />
      </WorkspaceProvider>,
    );
    expect(screen.getByTestId("clinical-tr-slider")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Set Physics/i }));
    expect(screen.getByTestId("physics-excite-fa-slider")).toBeVisible();
    expect(screen.getByTestId("physics-adc-bw-slider")).toBeVisible();
    expect(screen.getByTestId("physics-refocus-fa-slider")).toBeVisible();
  });

  it("paints compiled SequenceIR as five teaching channels instead of the 16-stick cartoon", () => {
    const ir: SequenceIR = {
      name: "TSE",
      duration: 0.12,
      metadata: { template: "TSE", te: 0.01, tr: 0.12, echoes: 2 },
      channels: [
        { name: "rf_amp", events: [{ time: 0, value: 90 }, { time: 0.005, value: 150 }] },
        { name: "gx", events: [{ time: 0.008, value: 1 }, { time: 0.01, value: 0 }] },
        { name: "gy", events: [] },
        { name: "gz", events: [{ time: 0, value: 1 }, { time: 0.001, value: 0 }] },
        { name: "adc_gate", events: [{ time: 0.01, value: 1 }, { time: 0.012, value: 0 }] },
      ],
    };
    render(<SequenceIRTimeline sequence={ir} />);
    expect(screen.getByTestId("sequence-ir-timeline")).toBeVisible();
    expect(screen.getByTestId("ch-rf_amp")).toBeVisible();
    expect(screen.getByTestId("ch-gx")).toBeVisible();
    expect(screen.getByTestId("ch-gy")).toBeVisible();
    expect(screen.getByTestId("ch-gz")).toBeVisible();
    expect(screen.getByTestId("ch-adc_gate")).toBeVisible();
    expect(screen.getByTestId("timeline-duration")).toHaveTextContent("120.0 ms");
    expect(screen.queryByText(/16-stick/i)).toBeNull();
  });
});
