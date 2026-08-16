import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Home from "../app/page";
import { LinkedLens } from "../components/editor/LinkedLens";
import { WorkspaceProvider } from "../components/workspace/WorkspaceProvider";

describe("clinical Explore and Linked Lens", () => {
  it("leads with clinical questions and keeps sequence names secondary", () => {
    render(<WorkspaceProvider><Home /></WorkspaceProvider>);
    expect(screen.getByText("Dark Blood")).toBeVisible();
    expect(screen.getByText(/Uses: TSE/)).toBeVisible();
  });
  it("names all conceptual layers and exposes linked cursor controls", () => {
    render(<WorkspaceProvider><LinkedLens /></WorkspaceProvider>);
    for (const label of ["SYSTEM", "PHYSICS", "STATE", "OBSERVATION"]) expect(screen.getByText(label)).toBeVisible();
    expect(screen.getByRole("slider", { name: "Experiment time" })).toBeVisible();
  });
});
