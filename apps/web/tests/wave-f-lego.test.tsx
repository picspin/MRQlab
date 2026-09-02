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

  it("shows chrome v0.76", () => {
    render(<WorkspaceProvider><WorkspaceShell>content</WorkspaceShell></WorkspaceProvider>);
    expect(screen.getByTestId("version-tag")).toHaveTextContent("v0.76");
  });
});
