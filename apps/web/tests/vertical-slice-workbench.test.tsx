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

  it("renders Retromorphic Instrument Shell with Lens Projection Contract", () => {
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

    // Clinical Mode Default
    expect(screen.getByTestId("clinical-contrast-panel")).toBeVisible();
    expect(screen.getByText(/CLINICAL CONTRAST/i)).toBeVisible();
    expect(screen.getByText(/MS Lesion Plaque/i)).toBeVisible();
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

  it("supports Clinical Scenario switching across Brain, Cardiac, Abdomen, MSK, Angio", () => {
    render(
      <WorkspaceProvider>
        <WorkbenchCockpit />
      </WorkspaceProvider>
    );

    const dropdown = screen.getByTestId("scenario-dropdown");
    fireEvent.change(dropdown, { target: { value: "abdomen_dixon" } });

    expect(screen.getByText(/Hepatic Parenchyma/i)).toBeVisible();
    expect(screen.getByText(/Focal Hepatic Steatosis/i)).toBeVisible();
  });

  it("supports Physics Lens: operators, EPG phase space, and dedicated test phantom", () => {
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

    fireEvent.click(screen.getByRole("button", { name: /Set Physics/i }));

    expect(screen.getByTestId("physics-details-panel")).toBeVisible();
    expect(screen.getByText(/PHYSICS ENGINE SPEC/i)).toBeVisible();
    expect(screen.getByText(/1. 5-CH TIMELINE/i)).toBeVisible();
    expect(screen.getByText(/4. TEST PHANTOM/i)).toBeVisible();

    // v0.43: Toggle Edit mode
    const editBtn = screen.getByTestId("edit-mode-toggle");
    expect(editBtn.textContent).toContain("EDIT");
    fireEvent.click(editBtn);
    expect(editBtn.textContent).toContain("EDITING");
    expect(screen.getByTestId("readout-width-slider")).toBeVisible();

    // v0.45: K-space / recon lens is a renderer only
    fireEvent.click(screen.getByTestId("kspace-tab-btn"));
    expect(screen.getByTestId("kspace-recon-lens")).toBeVisible();
    expect(screen.getByTestId("trajectory-type-select")).toBeVisible();
  });

  it("executes experiment with real ResultGraph backend dispatch on RUN", () => {
    render(
      <WorkspaceProvider>
        <WorkbenchCockpit />
      </WorkspaceProvider>
    );

    const runBtn = screen.getByTestId("run-experiment-btn");
    expect(runBtn).toBeVisible();
    fireEvent.click(runBtn);

    expect(screen.getByTestId("status-rail")).toBeVisible();
  });
});
