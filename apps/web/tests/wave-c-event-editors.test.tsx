import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WorkbenchCockpit } from "../components/workbench/WorkbenchCockpit";
import { WorkspaceProvider, useWorkspace } from "../components/workspace/WorkspaceProvider";
import { WorkspaceShell } from "../components/workspace/WorkspaceShell";

const sequence = {
  name: "SE",
  duration: 0.02,
  channels: [
    { name: "rf_amp", events: [{ time: 0.001, value: 90 }] },
    { name: "gx", events: [{ time: 0.004, value: 20 }] },
    { name: "gy", events: [] },
    { name: "gz", events: [] },
    { name: "adc_gate", events: [{ time: 0.01, value: 1 }] },
  ],
};

const pulse = {
  id: "pulse", name: "Sinc", kind: "shaped_sinc", flip_angle_deg: 90, phase_deg: 0,
  duration_ms: 2.5, time_bandwidth: 4, slice_thickness_mm: 5,
  waveform_time: [-1, 1], waveform_b1: [0, 1], freq_axis_khz: [-1, 1],
  freq_response_mag: [0, 1], spatial_axis_mm: [-5, 5], slice_profile_mz: [1, 0],
  slice_profile_mxy: [0, 1], epg_transition_matrix: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
  peak_b1: 1, bw_khz: 2,
};

function json(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
}

function PhysicsCockpit() {
  const { setProfile } = useWorkspace();
  return <><button onClick={() => setProfile("physics")}>Physics</button><WorkbenchCockpit /></>;
}

describe("Wave C SequenceIR event editors", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/sequences/build")) return json(sequence);
      if (url.includes("/pulse/inspect")) return json(pulse);
      if (url.includes("/gradients/validate")) return json({ is_valid: false, violations: ["Amplitude 99.0 mT/m exceeds Gmax"], actual_slew_rate: 198, actual_amplitude: 99 });
      if (url.includes("/cockpit/signals")) return json({ signals: {}, delta_signal: 0, cnr_proxy: 0, relative_sar: 0, refocus_eff: 0 });
      return json({});
    }));
  });

  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  async function renderCockpit() {
    render(<WorkspaceProvider><PhysicsCockpit /></WorkspaceProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Physics" }));
    await screen.findByTestId("event-rf_amp-0");
  }

  it("opens an RF pulse editor and inspects changed flip angle", async () => {
    await renderCockpit();
    fireEvent.click(screen.getByTestId("event-rf_amp-0"));
    expect(screen.getByTestId("pulse-event-editor")).toBeVisible();
    expect(screen.getByTestId("pulse-duration")).toBeVisible();
    expect(screen.getByTestId("pulse-tbw")).toBeVisible();
    fireEvent.change(screen.getByTestId("pulse-fa"), { target: { value: "75" } });
    await waitFor(() => expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.some(([url, init]) =>
      String(url).includes("/pulse/inspect") && JSON.parse(String(init?.body)).flip_angle_deg === 75,
    )).toBe(true));
  });

  it("opens a gradient editor and renders backend violations", async () => {
    await renderCockpit();
    fireEvent.click(screen.getByTestId("event-gx-0"));
    expect(screen.getByTestId("gradient-event-editor")).toBeVisible();
    expect(screen.getByTestId("grad-duration")).toBeVisible();
    expect(screen.getByTestId("grad-ramp")).toBeVisible();
    fireEvent.change(screen.getByTestId("grad-amp"), { target: { value: "99" } });
    expect(await screen.findByText("Amplitude 99.0 mT/m exceeds Gmax")).toBeVisible();
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.some(([url, init]) => {
      if (!String(url).includes("/gradients/validate")) return false;
      const body = JSON.parse(String(init?.body));
      return body.grad?.amplitude_mt_m === 99 && body.amplitude_mt_m === undefined;
    })).toBe(true);
  });

  it("shows only a read-only ADC chip for an ADC event", async () => {
    await renderCockpit();
    fireEvent.click(screen.getByTestId("event-adc_gate-0"));
    expect(screen.getByTestId("adc-event-chip")).toBeVisible();
    expect(screen.queryByTestId("pulse-event-editor")).toBeNull();
    expect(screen.queryByTestId("gradient-event-editor")).toBeNull();
  });

  it("shows chrome v0.74.2", () => {
    render(<WorkspaceProvider><WorkspaceShell>content</WorkspaceShell></WorkspaceProvider>);
    expect(screen.getByTestId("version-tag")).toHaveTextContent("v0.74.2");
  });

  it("labels gradient duration/ramp as editor seeds, not SequenceIR", async () => {
    await renderCockpit();
    fireEvent.click(screen.getByTestId("event-gx-0"));
    expect(screen.getByTestId("editor-seed-note")).toHaveTextContent(/editor seed/i);
    expect(screen.getByTestId("editor-seed-note")).toHaveTextContent(/not SequenceIR/i);
  });

  it("loads physical G amplitude from SequenceIR when gradient_units is mt_m", async () => {
    const physical = {
      ...sequence,
      channels: sequence.channels.map((channel) =>
        channel.name === "gx" ? { ...channel, events: [{ time: 0.004, value: 12 }] } : channel,
      ),
      metadata: { gradient_units: "mt_m" },
    };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/sequences/build")) return json(physical);
      if (url.includes("/pulse/inspect")) return json(pulse);
      if (url.includes("/gradients/validate")) return json({ is_valid: true, violations: [], actual_slew_rate: 1, actual_amplitude: 12 });
      if (url.includes("/cockpit/signals")) return json({ signals: {}, delta_signal: 0, cnr_proxy: 0, relative_sar: 0, refocus_eff: 0 });
      return json({});
    }));
    await renderCockpit();
    fireEvent.click(screen.getByTestId("event-gx-0"));
    expect(screen.getByTestId("grad-amp")).toHaveValue(12);
    expect(screen.getByTestId("editor-seed-note")).toHaveTextContent(/SequenceIR amplitude is mT\/m/i);
    expect(screen.getByTestId("editor-seed-note")).not.toHaveTextContent(/timeline normalized value is not mT\/m/i);
    expect(screen.getByTestId("sequence-ir-timeline")).toHaveTextContent(/Gx\/Gy\/Gz mT\/m/i);
  });

  it("labels teaching timeline as SequenceIR 5-ch, not physical mT/m", async () => {
    await renderCockpit();
    expect(screen.getByTestId("sequence-ir-timeline")).toHaveTextContent(/SequenceIR 5-ch/i);
    expect(screen.getByTestId("sequence-ir-timeline")).not.toHaveTextContent(/mT\/m/i);
  });

  it("hydrates G duration/ramp from event overlay, not editor seeds", async () => {
    const overlayed = {
      ...sequence,
      channels: sequence.channels.map((channel) =>
        channel.name === "gx" ? { ...channel, events: [{ time: 0.004, value: 20 }] } : channel,
      ),
      metadata: {
        gradient_units: "mt_m",
        event_overlays: {
          "gx:0": { amplitude_mt_m: 20, duration_s: 0.002, ramp_time_s: 0.0004, unit: "mT_m" },
        },
      },
    };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/sequences/build")) return json(overlayed);
      if (url.includes("/pulse/inspect")) return json(pulse);
      if (url.includes("/gradients/validate")) return json({ is_valid: true, violations: [], actual_slew_rate: 1, actual_amplitude: 20 });
      if (url.includes("/cockpit/signals")) return json({ signals: {}, delta_signal: 0, cnr_proxy: 0, relative_sar: 0, refocus_eff: 0 });
      return json({});
    }));
    await renderCockpit();
    fireEvent.click(screen.getByTestId("event-gx-0"));
    expect(screen.getByTestId("grad-amp")).toHaveValue(20);
    expect(screen.getByTestId("grad-duration")).toHaveValue(2);
    expect(screen.getByTestId("grad-ramp")).toHaveValue(0.4);
    expect(screen.getByTestId("editor-seed-note")).toHaveTextContent(/duration\/ramp from overlay/i);
    expect(screen.getByTestId("editor-seed-note")).not.toHaveTextContent(/duration\/ramp = editor seed/i);
  });

  it("labels pulse duration/TBW/phase as editor seeds", async () => {
    await renderCockpit();
    fireEvent.click(screen.getByTestId("event-rf_amp-0"));
    expect(screen.getByTestId("editor-seed-note")).toHaveTextContent(/editor seed/i);
    expect(screen.getByTestId("editor-seed-note")).toHaveTextContent(/not SequenceIR/i);
  });

  it("fail-closes the gradient editor on validate reject", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/sequences/build")) return json(sequence);
      if (url.includes("/pulse/inspect")) return json(pulse);
      if (url.includes("/gradients/validate")) return new Response("validate down", { status: 500 });
      if (url.includes("/cockpit/signals")) return json({ signals: {}, delta_signal: 0, cnr_proxy: 0, relative_sar: 0, refocus_eff: 0 });
      return json({});
    }));
    await renderCockpit();
    fireEvent.click(screen.getByTestId("event-gx-0"));
    expect(await screen.findByTestId("gradient-validate-error")).toBeVisible();
    expect(screen.queryByTestId("gradient-validation-result")).toBeNull();
  });

  it("fail-closes the pulse editor on inspect reject without a fake 90° badge", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/sequences/build")) return json(sequence);
      if (url.includes("/pulse/inspect")) return new Response("inspect down", { status: 500 });
      if (url.includes("/gradients/validate")) return json({ is_valid: true, violations: [], actual_slew_rate: 1, actual_amplitude: 20 });
      if (url.includes("/cockpit/signals")) return json({ signals: {}, delta_signal: 0, cnr_proxy: 0, relative_sar: 0, refocus_eff: 0 });
      return json({});
    }));
    await renderCockpit();
    fireEvent.click(screen.getByTestId("event-rf_amp-0"));
    expect(await screen.findByTestId("pulse-inspect-error")).toBeVisible();
    expect(screen.queryByText(/Phase:\s*90/)).toBeNull();
  });

  it("clears the last gradient payload while a new validate is in flight", async () => {
    let release: (value: unknown) => void = () => {};
    const deferred = new Promise((resolve) => { release = resolve; });
    let validateCalls = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/sequences/build")) return json(sequence);
      if (url.includes("/pulse/inspect")) return json(pulse);
      if (url.includes("/gradients/validate")) {
        validateCalls += 1;
        if (validateCalls === 1) {
          return json({ is_valid: true, violations: [], actual_slew_rate: 1, actual_amplitude: 20 });
        }
        await deferred;
        return json({ is_valid: false, violations: ["late"], actual_slew_rate: 2, actual_amplitude: 99 });
      }
      if (url.includes("/cockpit/signals")) return json({ signals: {}, delta_signal: 0, cnr_proxy: 0, relative_sar: 0, refocus_eff: 0 });
      return json({});
    }));
    await renderCockpit();
    fireEvent.click(screen.getByTestId("event-gx-0"));
    expect(await screen.findByTestId("gradient-validation-result")).toHaveTextContent("VALID");
    fireEvent.change(screen.getByTestId("grad-amp"), { target: { value: "99" } });
    await waitFor(() => expect(screen.queryByTestId("gradient-validation-result")).toBeNull());
    expect(screen.getByTestId("gradient-validate-pending")).toBeVisible();
    release(undefined);
    expect(await screen.findByText("late")).toBeVisible();
  });
});
