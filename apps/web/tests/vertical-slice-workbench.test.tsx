import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { WorkspaceShell } from "../components/workspace/WorkspaceShell";
import { WorkspaceProvider, useWorkspace } from "../components/workspace/WorkspaceProvider";
import { WorkbenchCockpit } from "../components/workbench/WorkbenchCockpit";

describe("Web Vertical Slice: Taxonomy, Dual Persona, Single Large Display & Retromorphism", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders top-level taxonomy (EXPLORE, WORKBENCH, LABS, AI LAB)", () => {
    render(
      <WorkspaceProvider>
        <WorkspaceShell>
          <div>Content</div>
        </WorkspaceShell>
      </WorkspaceProvider>
    );
    expect(screen.getByRole("link", { name: /EXPLORE/i })).toBeVisible();
    expect(screen.getByRole("link", { name: /WORKBENCH/i })).toBeVisible();
    expect(screen.getByRole("link", { name: /LABS/i })).toBeVisible();
    expect(screen.getByText(/AI LAB/i)).toBeVisible();
  });

  it("supports switching WorkspaceProfile (Clinical vs Physics mode)", () => {
    function TestComponent() {
      const { profile, setProfile } = useWorkspace();
      return (
        <div>
          <span data-testid="profile-indicator">{profile}</span>
          <button onClick={() => setProfile("physics")}>Switch to Physics</button>
        </div>
      );
    }

    render(
      <WorkspaceProvider>
        <TestComponent />
      </WorkspaceProvider>
    );

    expect(screen.getByTestId("profile-indicator").textContent).toBe("clinical");
    fireEvent.click(screen.getByRole("button", { name: /Switch to Physics/i }));
    expect(screen.getByTestId("profile-indicator").textContent).toBe("physics");
  });

  it("renders Single Large Display with Retromorphic Instrument Shell (Bay, Display, Control Bank, Status Rail)", () => {
    render(
      <WorkspaceProvider>
        <WorkbenchCockpit />
      </WorkspaceProvider>
    );

    // Retromorphic Instrument elements
    expect(screen.getByTestId("instrument-bay")).toBeVisible();
    expect(screen.getByTestId("active-lens-display")).toBeVisible();
    expect(screen.getByTestId("control-bank")).toBeVisible();
    expect(screen.getByTestId("status-rail")).toBeVisible();

    // In clinical mode (default), Clinical Contrast & Tissue targets are prominent
    expect(screen.getByText(/Brain T2/i)).toBeVisible();
    expect(screen.getByText(/Target/i)).toBeVisible();
    expect(screen.getByText("CLINICAL CONTRAST")).toBeVisible();
    expect(screen.getByText(/CNR Proxy/i)).toBeVisible();
  });

  it("supports Cross-Lens Cursor linking when clicking echo chips", () => {
    render(
      <WorkspaceProvider>
        <WorkbenchCockpit />
      </WorkspaceProvider>
    );

    const echo6Btn = screen.getByTestId("echo-chip-6");
    fireEvent.click(echo6Btn);

    expect(screen.getByTestId("echo-readout").textContent).toBe("Echo #6");
    expect(screen.getByTestId("time-readout").textContent).toBe("t = 75.0 ms");
  });

  it("supports Physics Mode drilldown into Pulse Inspector (Waveform, Freq, Slice Profile, EPG Matrix)", () => {
    function PhysicsWorkbench() {
      const { setProfile } = useWorkspace();
      return (
        <div>
          <button onClick={() => setProfile("physics")}>Set Physics</button>
          <WorkbenchCockpit />
        </div>
      );
    }

    render(
      <WorkspaceProvider>
        <PhysicsWorkbench />
      </WorkspaceProvider>
    );

    // Switch to physics
    fireEvent.click(screen.getByRole("button", { name: /Set Physics/i }));

    // Click inspect pulse button
    const inspectBtn = screen.getByTestId("open-pulse-inspector-btn");
    expect(inspectBtn).toBeVisible();
    fireEvent.click(inspectBtn);

    // Pulse inspector should be displayed
    expect(screen.getByTestId("pulse-inspector")).toBeVisible();
    expect(screen.getByText(/PULSE INSPECTOR/i)).toBeVisible();
    expect(screen.getByText(/Frequency Response/i)).toBeVisible();
    expect(screen.getByText(/Slice Profile/i)).toBeVisible();
    expect(screen.getByText(/EPG Coherence Transfer/i)).toBeVisible();

    // Close pulse inspector
    fireEvent.click(screen.getByRole("button", { name: /Close Inspector/i }));
    expect(screen.queryByTestId("pulse-inspector")).toBeNull();
  });

  it("supports Compare Lens for A/B parameter sweeps (Echo train, ΔContrast, SAR load, CNR proxy)", () => {
    render(
      <WorkspaceProvider>
        <WorkbenchCockpit />
      </WorkspaceProvider>
    );

    // Switch to Compare lens
    const compareTab = screen.getByTestId("lens-tab-compare");
    fireEvent.click(compareTab);

    // Verify compare screen renders both protocols and metrics
    expect(screen.getByTestId("compare-lens")).toBeVisible();
    expect(screen.getByText(/PROTOCOL A: Standard TSE/i)).toBeVisible();
    expect(screen.getByText(/PROTOCOL B: Low SAR Candidate/i)).toBeVisible();
    expect(screen.getByText(/ECHO TRAIN DECAY DYNAMICS/i)).toBeVisible();
    expect(screen.getByText(/Relative SAR Load/i)).toBeVisible();
  });

  it("supports Optimize Lens: Pareto frontier, sensitivity gradients & apply optimal to protocol", () => {
    render(
      <WorkspaceProvider>
        <WorkbenchCockpit />
      </WorkspaceProvider>
    );

    // Switch to Optimize lens
    const optTab = screen.getByTestId("lens-tab-optimize");
    fireEvent.click(optTab);

    // Verify Optimize view elements
    expect(screen.getByTestId("optimize-lens-view")).toBeVisible();
    expect(screen.getByText(/Pareto Frontier/i)).toBeVisible();
    expect(screen.getByText(/Sensitivity Gradients/i)).toBeVisible();
    expect(screen.getByText(/Recommended Protocol Parameters/i)).toBeVisible();

    // Toggle goal mode
    const minSarBtn = screen.getByTestId("goal-min-sar");
    fireEvent.click(minSarBtn);
    expect(screen.getByText(/Minimum SAR \/ Thermal Safety First/i)).toBeVisible();

    // Apply optimal parameters
    const applyBtn = screen.getByTestId("apply-optimal-button");
    fireEvent.click(applyBtn);

    // Flip Angle input should be updated
    const faSlider = screen.getByLabelText(/Refocusing Flip Angle/i) as HTMLInputElement;
    expect(Number(faSlider.value)).toBeGreaterThanOrEqual(100);
  });
});
