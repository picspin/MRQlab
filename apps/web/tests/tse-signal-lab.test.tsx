import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TseSignalLab } from "../components/signal-lab/TseSignalLab";
import { WorkspaceProvider } from "../components/workspace/WorkspaceProvider";

describe("TSE Signal Lab", () => {
  it("shows the complete parameter-to-contrast chain", async () => {
    const run = vi.fn().mockResolvedValue({
      schema_version: "1.0", experiment_id: "tse",
      observations: [
        { id: "configurations", kind: "configurations", data: [[1]], derived_from: ["signal"] },
        { id: "echo_train", kind: "echo_train", data: [1, .8], derived_from: ["signal"] },
        { id: "image", kind: "image", data: [1, .8], derived_from: ["signal"] },
        { id: "sar", kind: "sar", data: 1.2, derived_from: [] },
      ],
    });
    render(<WorkspaceProvider><TseSignalLab run={run}/></WorkspaceProvider>);
    fireEvent.change(screen.getByRole("slider", { name: "Refocusing flip angle" }), { target: { value: "120" } });
    fireEvent.click(screen.getByText("Run teaching chain"));
    for (const label of ["EPG states", "Echo train", "k-space weighting", "Tissue contrast", "SAR 1.20"])
      expect(await screen.findByText(label)).toBeVisible();
  });
});
