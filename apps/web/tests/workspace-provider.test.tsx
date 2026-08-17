import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WorkspaceProvider, useWorkspace } from "../components/workspace/WorkspaceProvider";

function Probe() {
  const state = useWorkspace();
  return (
    <>
      <output>
        {state.workspace}:{state.cursors.selectedEcho ?? "none"}
      </output>
      <button onClick={() => state.openWorkspace("signal-lab")}>open</button>
      <button onClick={() => state.setCursors({ selectedEcho: 3 })}>echo</button>
    </>
  );
}

describe("WorkspaceProvider", () => {
  it("shares workspace and linked-lens cursors", () => {
    render(
      <WorkspaceProvider>
        <Probe />
      </WorkspaceProvider>,
    );
    fireEvent.click(screen.getByText("open"));
    fireEvent.click(screen.getByText("echo"));
    expect(screen.getByRole("status")).toHaveTextContent("signal-lab:3");
  });
});
