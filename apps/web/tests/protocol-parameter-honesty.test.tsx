import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkbenchCockpit } from "../components/workbench/WorkbenchCockpit";
import { WorkspaceProvider, useWorkspace } from "../components/workspace/WorkspaceProvider";

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });
function Harness() {
  const { setProfile } = useWorkspace();
  return <><button onClick={() => setProfile("physics")}>Physics profile</button><WorkbenchCockpit /></>;
}

describe("protocol parameter honesty", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("labels all four unwired controls and omits them from run payloads", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/sequences/build")) return json({ name: "TSE", duration: .1, channels: [], metadata: {} });
      if (url.includes("/cockpit/signals")) return json({ signals: {} });
      if (url.includes("/clinical-recipes")) return json({ recipes: [] });
      return json({ schema_version: "1.0", experiment_id: "x", observations: [] });
    }));
    render(<WorkspaceProvider><Harness /></WorkspaceProvider>);
    expect(screen.getByTestId("clinical-acceleration-state")).toHaveTextContent("local only · not in execution plan");
    fireEvent.click(screen.getByRole("button", { name: "Physics profile" }));
    fireEvent.click(screen.getByTestId("edit-mode-toggle"));
    expect(screen.getByTestId("readout-width-state")).toHaveTextContent("local only · not in execution plan");
    expect(screen.getByTestId("partial-fourier-state")).toHaveTextContent("local only · not in execution plan");
    expect(screen.getByTestId("adc-bw-slider-seed")).toHaveTextContent("seed · not wired");
    fireEvent.click(screen.getByTestId("run-experiment-btn"));
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    for (const [url, init] of (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls) {
      if (String(url).includes("/experiments/run")) {
        expect(String(init?.body)).not.toMatch(/adc_bw|bandwidth_hz|acceleration|readout_width|partial_fourier/i);
      }
    }
  });
});
