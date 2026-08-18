import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WorkspaceShell } from "../components/workspace/WorkspaceShell";
import { WorkspaceProvider, useWorkspace } from "../components/workspace/WorkspaceProvider";
import { WorkbenchCockpit } from "../components/workbench/WorkbenchCockpit";

describe("Web Vertical Slice: Taxonomy, Dual Persona, Single Large Display & Retromorphism", () => {
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
});
