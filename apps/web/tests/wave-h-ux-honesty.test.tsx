import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkspaceProvider, useWorkspace } from "../components/workspace/WorkspaceProvider";
import { WorkspaceShell } from "../components/workspace/WorkspaceShell";
import { WorkbenchCockpit } from "../components/workbench/WorkbenchCockpit";

const sequence = { name: "TSE", duration: .02, channels: [
  { name: "rf_amp", events: [{ time: .001, value: 90 }] },
  { name: "gx", events: [{ time: .004, value: 1 }] },
  { name: "gy", events: [] }, { name: "gz", events: [] }, { name: "adc_gate", events: [] },
] };
const result = { schema_version: "1.0", experiment_id: "recipe", observations: [
  { id: "signal", kind: "signal", data: [1] },
  { id: "configurations", kind: "configurations", data: [[[1, .5], [.2, .1], [.8, .4]], [[.7, .3], [.1, .05], [.6, .2]]] },
] };
const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });

function PhysicsCockpit({ recipe }: { recipe?: string } = {}) {
  const { setProfile } = useWorkspace();
  return <><button onClick={() => setProfile("physics")}>Physics profile</button><WorkbenchCockpit initialRecipeId={recipe} /></>;
}

function mockApi(runResult: unknown = result) {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
    const url = String(input);
    if (url.includes("/sequences/build")) return json(sequence);
    if (url.includes("/experiments/run-from-recipe")) return json(runResult);
    if (url.includes("/cockpit/signals")) return json({ signals: {}, delta_signal: 0, cnr_proxy: 0, relative_sar: 0, refocus_eff: 0 });
    if (url.includes("/gradients/validate")) return json({ is_valid: true, violations: [], actual_slew_rate: 1, actual_amplitude: 1 });
    return json({});
  }));
}

describe("Wave H UX honesty", () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it("uses equal clinical quad rows", () => {
    mockApi(); render(<WorkspaceProvider><WorkbenchCockpit /></WorkspaceProvider>);
    expect(screen.getByTestId("clinical-quad-grid")).toHaveStyle({ gridTemplateRows: "1fr 1fr" });
  });

  it("awaits real configurations, then renders RUN pathways", async () => {
    mockApi(); render(<WorkspaceProvider><PhysicsCockpit /></WorkspaceProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Physics profile" }));
    fireEvent.click(screen.getByRole("button", { name: /EPG/ }));
    expect(screen.getByTestId("epg-awaiting")).toBeVisible();
    fireEvent.click(screen.getByTestId("run-experiment-btn"));
    expect(await screen.findByTestId("epg-pathways")).toBeVisible();
  });

  it("shows an origin-true Bloch HUD and honest seed label", () => {
    mockApi(); render(<WorkspaceProvider><PhysicsCockpit /></WorkspaceProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Physics profile" }));
    fireEvent.click(screen.getByRole("button", { name: /ROTATING/ }));
    expect(screen.getByTestId("bloch-hud")).toBeVisible();
    expect(screen.getByTestId("bloch-seed-label")).toBeVisible();
  });

  it("demotes pulse and exposes oscilloscope inspectors", () => {
    mockApi(); render(<WorkspaceProvider><PhysicsCockpit /></WorkspaceProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Physics profile" }));
    expect(screen.queryByTestId("pulse-tab-btn")).toBeNull();
    expect(screen.getByTestId("inspect-rf-btn")).toBeVisible();
    expect(screen.getByTestId("inspect-g-btn")).toBeVisible();
  });

  it("ignores an older compose response that arrives last", async () => {
    let releaseFirst!: (response: Response) => void;
    const first = new Promise<Response>((resolve) => { releaseFirst = resolve; });
    let composeCalls = 0;
    mockApi();
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/sequences/compose")) return ++composeCalls === 1 ? first : json({ ...sequence, name: "newest" });
      if (url.includes("/sequences/build")) return json(sequence);
      if (url.includes("/cockpit/signals")) return json({ signals: {}, delta_signal: 0, cnr_proxy: 0, relative_sar: 0, refocus_eff: 0 });
      return json({});
    });
    render(<WorkspaceProvider><PhysicsCockpit /></WorkspaceProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Physics profile" }));
    fireEvent.click(screen.getByTestId("catalog-excite_sinc"));
    fireEvent.click(screen.getByTestId("catalog-trap_gx"));
    await waitFor(() => expect(screen.getByTestId("sequence-ir-timeline")).toHaveTextContent("newest"));
    releaseFirst(json({ ...sequence, name: "stale" }));
    await Promise.resolve();
    expect(screen.getByTestId("sequence-ir-timeline")).toHaveTextContent("newest");
  });

  it("shows chrome v0.66.4", () => {
    render(<WorkspaceProvider><WorkspaceShell>content</WorkspaceShell></WorkspaceProvider>);
    expect(screen.getByTestId("version-tag")).toHaveTextContent("v0.66.4");
  });

  it("awaits z_spectrum then plots backend arrays", async () => {
    const spectrum = {
      schema_version: "1.0",
      experiment_id: "recipe:cest_amide_z_spectrum",
      observations: [
        {
          id: "z_spectrum",
          kind: "z_spectrum",
          data: {
            offset_ppm: [-5, 0, 3.5, 5],
            Z: [0.9, 0.2, 0.55, 0.88],
            normalization: "unsaturated_control",
            mode: "pulsed",
            duty_cycle: 20 * .05 / 1.95,
          },
          provenance: { engine: "epg-x", assumptions: ["cest_z_spectrum_applied"] },
        },
        { id: "mtr_asym", kind: "mtr_asym", data: { offset_ppm: [3.5, 5], MTR_asym: [0.12, 0.02] } },
      ],
    };
    mockApi(spectrum);
    render(<WorkspaceProvider><PhysicsCockpit /></WorkspaceProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Physics profile" }));
    fireEvent.click(screen.getByTestId("spectrum-tab-btn"));
    expect(screen.getByTestId("spectrum-awaiting")).toBeVisible();
    fireEvent.click(screen.getByTestId("run-experiment-btn"));
    expect(await screen.findByTestId("spectrum-plot")).toBeVisible();
    expect(screen.getByTestId("spectrum-plot")).toHaveTextContent(/unsaturated_control/);
    expect(screen.getByTestId("spectrum-mode")).toHaveTextContent(/pulsed/);
  });

  it("clinical spatial viewport rejects z_spectrum", async () => {
    mockApi({
      schema_version: "1.0",
      experiment_id: "recipe:cest_amide_z_spectrum",
      observations: [
        { id: "z_spectrum", kind: "z_spectrum", data: { offset_ppm: [0], Z: [1], normalization: "unsaturated_control" } },
      ],
    });
    render(<WorkspaceProvider><WorkbenchCockpit initialRecipeId="cest_amide_z_spectrum" /></WorkspaceProvider>);
    fireEvent.click(screen.getByTestId("run-experiment-btn"));
    expect(await screen.findByTestId("clinical-rejects-z-spectrum")).toBeVisible();
    expect(screen.queryByTestId("clinical-quad-grid")).toBeNull();
    expect(screen.queryByTestId("spectrum-plot")).toBeNull();
  });

  it("CEST physics seam is CEST, not SE, and hides the TSE echo train", () => {
    mockApi();
    render(<WorkspaceProvider><PhysicsCockpit recipe="cest_amide_pulsed_z_spectrum" /></WorkspaceProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Physics profile" }));
    expect(screen.getByTestId("physics-seam")).toHaveTextContent("SEAM: CEST");
    expect(screen.getByTestId("physics-seam")).not.toHaveTextContent("SEAM: SE");
    expect(screen.queryByTestId("echo-train-rail")).toBeNull();
    expect(screen.getByText("k=0 water")).toBeVisible();
    expect(screen.getByText("EPG-X CEST")).toBeVisible();
    expect(screen.getByTestId("spectrum-control-honesty")).toBeVisible();
    expect(screen.queryByTestId("physics-excite-fa-slider")).toBeNull();
    expect(screen.getByTestId("spectrum-awaiting")).toBeVisible();
    expect(screen.queryByTestId("kspace-tab-btn")).toBeNull();
    expect(screen.queryByRole("button", { name: /TEST PHANTOM/ })).toBeNull();
    expect(screen.getByTestId("display-header-title")).toHaveTextContent("SPECTRUM");
    expect(screen.getByTestId("display-header-title")).not.toHaveTextContent("TIMELINE");
  });
});
