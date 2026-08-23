import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WorkbenchCockpit } from "../components/workbench/WorkbenchCockpit";
import { WorkspaceProvider, useWorkspace } from "../components/workspace/WorkspaceProvider";

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
});
