import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WorkbenchCockpit } from "../components/workbench/WorkbenchCockpit";
import { WorkspaceProvider, useWorkspace } from "../components/workspace/WorkspaceProvider";

const sequence = { name: "SE", duration: .02, channels: [
  { name: "rf_amp", events: [{ time: .001, value: 90 }] },
  { name: "gx", events: [{ time: .004, value: 1 }] }, { name: "gy", events: [] }, { name: "gz", events: [] },
  { name: "adc_gate", events: [{ time: .01, value: 1 }] },
] };
const pulse = { name: "Sinc", flip_angle_deg: 90, phase_deg: 0, duration_ms: 2.5, time_bandwidth: 4, slice_thickness_mm: 5,
  waveform_time: [-1, 1], waveform_b1: [0, 1], freq_axis_khz: [-1, 1], freq_response_mag: [0, 1], spatial_axis_mm: [-5, 5],
  slice_profile_mxy: [0, 1], epg_transition_matrix: [] };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
function PhysicsCockpit() { const { setProfile } = useWorkspace(); return <><button onClick={() => setProfile("physics")}>Physics</button><WorkbenchCockpit /></>; }

describe("Wave E SequenceIR write-back", () => {
  beforeEach(() => vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
    const url = String(input);
    if (url.includes("/sequences/build")) return json(sequence);
    if (url.includes("/pulse/inspect")) return json(pulse);
    if (url.includes("/gradients/validate")) return json({ is_valid: true, violations: [], actual_slew_rate: 1, actual_amplitude: 20 });
    if (url.includes("/sequences/patch")) return json(sequence);
    if (url.includes("/cockpit/signals")) return json({ signals: {}, delta_signal: 0, cnr_proxy: 0, relative_sar: 0, refocus_eff: 0 });
    return json({});
  })));
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
  async function open() { render(<WorkspaceProvider><PhysicsCockpit /></WorkspaceProvider>); fireEvent.click(screen.getByRole("button", { name: "Physics" })); await screen.findByTestId("event-rf_amp-0"); }

  it("applies RF through /sequences/patch with the IR, event ref, and patch", async () => {
    await open(); fireEvent.click(screen.getByTestId("event-rf_amp-0"));
    await waitFor(() => expect(screen.getByTestId("event-apply")).toBeEnabled()); fireEvent.click(screen.getByTestId("event-apply"));
    await waitFor(() => expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.some(([url, init]) => {
      if (!String(url).includes("/sequences/patch")) return false;
      const body = JSON.parse(String(init?.body));
      return body.ir.channels[0].events[0].value === 90 && body.event.channel === "rf_amp" && body.event.index === 0 && body.patch.flip_angle_deg === 90;
    })).toBe(true));
  });

  it("keeps the previous gradient timeline value after patch 422", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(async (input: RequestInfo) => {
      const url = String(input); if (url.includes("/sequences/patch")) return json({ detail: "illegal slew" }, 422);
      if (url.includes("/sequences/build")) return json(sequence); if (url.includes("/gradients/validate")) return json({ is_valid: true, violations: [], actual_slew_rate: 1, actual_amplitude: 20 });
      if (url.includes("/cockpit/signals")) return json({ signals: {} }); return json(pulse);
    });
    await open(); fireEvent.click(screen.getByTestId("event-gx-0")); await waitFor(() => expect(screen.getByTestId("event-apply")).toBeEnabled());
    fireEvent.click(screen.getByTestId("event-apply")); expect(await screen.findByTestId("gradient-validate-error")).toBeVisible();
    expect(screen.getByTestId("event-gx-0")).toHaveAttribute("data-value", "1");
  });

  it("does not offer Apply for ADC", async () => { await open(); fireEvent.click(screen.getByTestId("event-adc_gate-0")); expect(screen.queryByTestId("event-apply")).toBeNull(); });
});
