import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WorkbenchCockpit } from "../components/workbench/WorkbenchCockpit";
import { WorkspaceProvider, useWorkspace } from "../components/workspace/WorkspaceProvider";
import { WorkspaceShell } from "../components/workspace/WorkspaceShell";

const oldSequence = { name: "SE", duration: .02, channels: [
  { name: "rf_amp", events: [{ time: .001, value: 45 }] }, { name: "gx", events: [] },
  { name: "gy", events: [] }, { name: "gz", events: [] }, { name: "adc_gate", events: [] },
] };
const composed = { ...oldSequence, name: "Lego sequence", channels: oldSequence.channels.map((channel) =>
  channel.name === "rf_amp" ? { ...channel, events: [{ time: 0, value: 90 }] } : channel), metadata: { blocks: [] } };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
function PhysicsCockpit() { const { setProfile } = useWorkspace(); return <><button onClick={() => setProfile("physics")}>Physics</button><WorkbenchCockpit /></>; }

describe("Wave F Lego constructor", () => {
  beforeEach(() => vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
    const url = String(input);
    if (url.includes("/sequences/build")) return json(oldSequence);
    if (url.includes("/sequences/compose")) return json(composed);
    if (url.includes("/cockpit/signals")) return json({ signals: {} });
    return json({});
  })));
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
  async function open() { render(<WorkspaceProvider><PhysicsCockpit /></WorkspaceProvider>); fireEvent.click(screen.getByRole("button", { name: "Physics" })); await screen.findByTestId("event-rf_amp-0"); }

  it("places excite through compose with a backend block list", async () => {
    await open(); fireEvent.click(screen.getByTestId("catalog-excite_sinc"));
    await waitFor(() => expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.some(([url, init]) => {
      if (!String(url).includes("/sequences/compose")) return false;
      const body = JSON.parse(String(init?.body));
      return body.blocks.length === 1 && body.blocks[0].kind === "excite_sinc" && body.channels === undefined;
    })).toBe(true));
  });

  it("keeps previous IR when compose returns 422", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(async (input: RequestInfo) => {
      const url = String(input); if (url.includes("/sequences/compose")) return json({ detail: "overlap" }, 422);
      if (url.includes("/sequences/build")) return json(oldSequence); if (url.includes("/cockpit/signals")) return json({ signals: {} }); return json({});
    });
    await open(); fireEvent.click(screen.getByTestId("catalog-excite_sinc"));
    expect(await screen.findByRole("alert")).toHaveTextContent("STATUS ERROR");
    expect(screen.getByTestId("event-rf_amp-0")).toHaveAttribute("data-value", "45");
  });

  it("labels Lego as physical G after compose opt-in, not TEACHING BLOCKS", async () => {
    const physical = {
      ...composed,
      channels: composed.channels.map((channel) =>
        channel.name === "gx" ? { ...channel, events: [{ time: 0.001, value: 20 }] } : channel,
      ),
      metadata: { gradient_units: "mt_m", blocks: [] },
    };
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/sequences/compose")) return json(physical);
      if (url.includes("/sequences/build")) return json(oldSequence);
      if (url.includes("/cockpit/signals")) return json({ signals: {} });
      return json({});
    });
    await open();
    expect(screen.getByTestId("sequence-lego")).toHaveTextContent(/TEACHING BLOCKS/i);
    fireEvent.click(screen.getByTestId("catalog-trap_gx"));
    await waitFor(() => expect(screen.getByTestId("sequence-lego")).toHaveTextContent(/PHYSICAL G · mT\/m/i));
    expect(screen.getByTestId("sequence-lego")).not.toHaveTextContent(/TEACHING BLOCKS/i);
  });

  function transfer() {
    const data: Record<string, string> = {};
    return {
      setData: (type: string, value: string) => { data[type] = value; },
      getData: (type: string) => data[type] ?? "",
    };
  }

  function dropOn(channel: string, dt: { getData: (type: string) => string; setData: (type: string, value: string) => void }, x = 183) {
    const node = screen.getByTestId(`ch-${channel}`);
    const event = new Event("drop", { bubbles: true, cancelable: true });
    Object.defineProperty(event, "dataTransfer", { value: dt });
    Object.defineProperty(event, "clientX", { value: x });
    Object.defineProperty(event, "offsetX", { value: x });
    node.dispatchEvent(event);
  }

  it("drags excite onto RF at a known x and posts snapped t0, not click-append", async () => {
    await open();
    const dt = transfer();
    fireEvent.dragStart(screen.getByTestId("catalog-excite_sinc"), { dataTransfer: dt });
    dropOn("rf_amp", dt, 183);
    await waitFor(() => expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.some(([url, init]) => {
      if (!String(url).includes("/sequences/compose")) return false;
      const body = JSON.parse(String(init?.body));
      return body.blocks.length === 1 && body.blocks[0].kind === "excite_sinc"
        && body.blocks[0].t0_s === 0.005 && body.channels === undefined;
    })).toBe(true));
  });

  it("does not compose when trap_gx is dropped on RF", async () => {
    await open();
    const before = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.filter(([url]) => String(url).includes("/sequences/compose")).length;
    const dt = transfer();
    fireEvent.dragStart(screen.getByTestId("catalog-trap_gx"), { dataTransfer: dt });
    dropOn("rf_amp", dt, 183);
    await Promise.resolve();
    const after = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.filter(([url]) => String(url).includes("/sequences/compose")).length;
    expect(after).toBe(before);
    expect(screen.getByTestId("event-rf_amp-0")).toHaveAttribute("data-value", "45");
  });

  it("keeps previous IR when a drag compose returns 422", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/sequences/compose")) return json({ detail: "overlap" }, 422);
      if (url.includes("/sequences/build")) return json(oldSequence);
      if (url.includes("/cockpit/signals")) return json({ signals: {} });
      return json({});
    });
    await open();
    const dt = transfer();
    fireEvent.dragStart(screen.getByTestId("catalog-excite_sinc"), { dataTransfer: dt });
    dropOn("rf_amp", dt, 183);
    expect(await screen.findByRole("alert")).toHaveTextContent("STATUS ERROR");
    expect(screen.getByTestId("event-rf_amp-0")).toHaveAttribute("data-value", "45");
  });

  it("shows chrome v0.76.4", () => {
    render(<WorkspaceProvider><WorkspaceShell>content</WorkspaceShell></WorkspaceProvider>);
    expect(screen.getByTestId("version-tag")).toHaveTextContent("v0.76.4");
  });

  it("keeps patched RF params on the next Lego compose", async () => {
    const pulse = {
      name: "Sinc", flip_angle_deg: 75, phase_deg: 30, duration_ms: 3, time_bandwidth: 6, slice_thickness_mm: 5,
      waveform_time: [-1, 1], waveform_b1: [0, 1], freq_axis_khz: [-1, 1], freq_response_mag: [0, 1],
      spatial_axis_mm: [-5, 5], slice_profile_mxy: [0, 1], epg_transition_matrix: [],
    };
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/sequences/compose")) {
        const body = JSON.parse(String(init?.body));
        const rf = body.blocks.find((block: { kind: string }) => block.kind.endsWith("sinc"));
        return json({
          name: "Lego sequence",
          duration: 0.02,
          channels: [
            { name: "rf_amp", events: rf ? [{ time: rf.t0_s, value: rf.params.flip_angle_deg }] : [] },
            { name: "rf_phase", events: rf ? [{ time: rf.t0_s, value: rf.params.phase_deg }] : [] },
            { name: "gx", events: [] }, { name: "gy", events: [] }, { name: "gz", events: [] },
            { name: "adc_gate", events: [] },
          ],
          metadata: { blocks: body.blocks, event_overlays: rf ? { "rf_amp:0": rf.params } : {} },
        });
      }
      if (url.includes("/sequences/patch")) {
        const body = JSON.parse(String(init?.body));
        const patchedBlocks = (body.ir.metadata?.blocks ?? []).map((block: { kind: string; params: Record<string, number> }, index: number) =>
          index === 0 && block.kind.endsWith("sinc") ? { ...block, params: { ...block.params, ...body.patch } } : block,
        );
        return json({
          ...body.ir,
          channels: body.ir.channels.map((channel: { name: string; events: Array<{ time: number; value: number }> }) =>
            channel.name === "rf_amp"
              ? { ...channel, events: [{ ...channel.events[0], value: body.patch.flip_angle_deg }] }
              : channel.name === "rf_phase"
                ? { ...channel, events: [{ ...channel.events[0], value: body.patch.phase_deg }] }
                : channel,
          ),
          metadata: {
            ...body.ir.metadata,
            blocks: patchedBlocks,
            event_overlays: { "rf_amp:0": body.patch },
          },
        });
      }
      if (url.includes("/pulse/inspect")) return json(pulse);
      if (url.includes("/sequences/build")) return json(oldSequence);
      if (url.includes("/cockpit/signals")) return json({ signals: {} });
      return json({});
    });
    await open();
    fireEvent.click(screen.getByTestId("catalog-excite_sinc"));
    await screen.findByTestId("event-rf_amp-0");
    fireEvent.click(screen.getByTestId("event-rf_amp-0"));
    fireEvent.change(screen.getByTestId("pulse-fa"), { target: { value: "75" } });
    fireEvent.change(screen.getByTestId("pulse-phase"), { target: { value: "30" } });
    fireEvent.change(screen.getByTestId("pulse-duration"), { target: { value: "3" } });
    fireEvent.change(screen.getByTestId("pulse-tbw"), { target: { value: "6" } });
    await waitFor(() => expect(screen.getByTestId("event-apply")).toBeEnabled());
    fireEvent.click(screen.getByTestId("event-apply"));
    await waitFor(() => expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.some(([url]) =>
      String(url).includes("/sequences/patch"),
    )).toBe(true));
    fireEvent.click(screen.getByTestId("catalog-trap_gx"));
    await waitFor(() => expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.some(([url, init]) => {
      if (!String(url).includes("/sequences/compose")) return false;
      const body = JSON.parse(String(init?.body));
      return body.blocks.length === 2
        && body.blocks[0].kind === "excite_sinc"
        && body.blocks[0].params.flip_angle_deg === 75
        && body.blocks[0].params.phase_deg === 30
        && body.blocks[0].params.duration_s === 0.003
        && body.blocks[0].params.time_bandwidth === 6
        && body.blocks[1].kind === "trap_gx";
    })).toBe(true));
  });

  it("keeps patched G params on the next Lego compose", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/sequences/compose")) {
        const body = JSON.parse(String(init?.body));
        const gradients = body.blocks.filter((item: { kind: string }) => item.kind.startsWith("trap_"));
        return json({
          name: "Lego sequence", duration: 0.02,
          channels: [
            { name: "rf_amp", events: [] }, { name: "rf_phase", events: [] },
            { name: "gx", events: gradients.map((item: { t0_s: number; params: { amplitude_mt_m: number } }) => ({ time: item.t0_s, value: item.params.amplitude_mt_m })) },
            { name: "gy", events: [] }, { name: "gz", events: [] }, { name: "adc_gate", events: [] },
          ],
          metadata: { gradient_units: "mt_m", blocks: body.blocks, event_overlays: gradients.length ? { "gx:0": gradients[0].params } : {} },
        });
      }
      if (url.includes("/sequences/patch")) {
        const body = JSON.parse(String(init?.body));
        const patchedBlocks = body.ir.metadata.blocks.map((item: { kind: string; params: Record<string, number> }) =>
          item.kind === "trap_gx" ? { ...item, params: { ...item.params, ...body.patch } } : item,
        );
        return json({ ...body.ir, metadata: { ...body.ir.metadata, blocks: patchedBlocks, event_overlays: { "gx:0": body.patch } } });
      }
      if (url.includes("/gradients/validate")) return json({ is_valid: true, violations: [], actual_slew_rate: 1, actual_amplitude: 14 });
      if (url.includes("/sequences/build")) return json(oldSequence);
      if (url.includes("/cockpit/signals")) return json({ signals: {} });
      return json({});
    });
    await open();
    fireEvent.click(screen.getByTestId("catalog-trap_gx"));
    await screen.findByTestId("event-gx-0");
    fireEvent.click(screen.getByTestId("event-gx-0"));
    fireEvent.change(screen.getByTestId("grad-amp"), { target: { value: "14" } });
    fireEvent.change(screen.getByTestId("grad-duration"), { target: { value: "2" } });
    fireEvent.change(screen.getByTestId("grad-ramp"), { target: { value: "0.3" } });
    await waitFor(() => expect(screen.getByTestId("event-apply")).toBeEnabled());
    fireEvent.click(screen.getByTestId("event-apply"));
    await waitFor(() => expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.some(([url]) => String(url).includes("/sequences/patch"))).toBe(true));
    fireEvent.click(screen.getByTestId("catalog-excite_sinc"));
    await waitFor(() => expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.some(([url, init]) => {
      if (!String(url).includes("/sequences/compose")) return false;
      const body = JSON.parse(String(init?.body));
      return body.blocks.length === 2 && body.blocks[0].kind === "trap_gx"
        && body.blocks[0].params.amplitude_mt_m === 14 && body.blocks[0].params.duration_s === 0.002
        && body.blocks[0].params.ramp_time_s === 0.0003 && body.blocks[1].kind === "excite_sinc";
    })).toBe(true));
  });
});
