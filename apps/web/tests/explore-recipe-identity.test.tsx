import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import Home from "../app/page";
import { WorkspaceProvider } from "../components/workspace/WorkspaceProvider";
import { WorkbenchCockpit } from "../components/workbench/WorkbenchCockpit";
import { WorkspaceShell } from "../components/workspace/WorkspaceShell";
import {
  EXPLORE_CASES,
  RECIPE_TO_SCENARIO,
  scenarioKeyForRecipe,
} from "../lib/explore-catalog";

afterEach(() => {
  cleanup();
});

describe("Wave A remainder: Explore ↔ recipe identity", () => {
  it("maps executable Explore cards onto backend recipe ids", () => {
    const byId = Object.fromEntries(EXPLORE_CASES.map((c) => [c.id, c]));

    expect(byId["ms-lesion-t2"].executable).toBe(true);
    expect(byId["ms-lesion-t2"].recipeId).toBe("brain_t2_tse");
    expect(byId["dark-blood-tse"].recipeId).toBe("dark_blood_vessel_wall_tse");
    expect(byId["dixon-fat-water"].recipeId).toBe("abdomen_dixon_gre");

    expect(byId["brain-flair"].executable).toBe(false);
    expect(byId["brain-flair"].recipeId).toBeNull();
    expect(byId["myocardial-t1-map"].executable).toBe(false);
    expect(byId["knee-cartilage-t2"].executable).toBe(false);
  });

  it("resolves recipe_id to the workbench scenario key", () => {
    expect(scenarioKeyForRecipe("brain_t2_tse")).toBe("ms_brain");
    expect(scenarioKeyForRecipe("abdomen_dixon_gre")).toBe("abdomen_dixon");
    expect(scenarioKeyForRecipe("dark_blood_vessel_wall_tse")).toBe("cardiac_darkblood");
    expect(scenarioKeyForRecipe("msk_knee_tse")).toBe("msk_knee");
    expect(scenarioKeyForRecipe("angio_tof_gre")).toBe("angio_tof");
    expect(scenarioKeyForRecipe("nope")).toBe("ms_brain");
    expect(RECIPE_TO_SCENARIO.cardiac_cine_gre).toBeUndefined();
  });

  it("Launch Cockpit deep-links executable cases and badges the rest", () => {
    render(<Home />);

    const ms = screen.getByTestId("launch-ms-lesion-t2");
    expect(ms).toHaveAttribute("href", "/workbench?recipe=brain_t2_tse");

    const dixon = screen.getByTestId("launch-dixon-fat-water");
    expect(dixon).toHaveAttribute("href", "/workbench?recipe=abdomen_dixon_gre");

    const dark = screen.getByTestId("launch-dark-blood-tse");
    expect(dark).toHaveAttribute("href", "/workbench?recipe=dark_blood_vessel_wall_tse");

    expect(screen.queryByTestId("launch-brain-flair")).toBeNull();
    expect(screen.queryByTestId("launch-myocardial-t1-map")).toBeNull();
    expect(screen.queryByTestId("launch-knee-cartilage-t2")).toBeNull();

    expect(screen.getByTestId("badge-brain-flair")).toHaveTextContent(/not in v0\.1/i);
    expect(screen.getByTestId("badge-myocardial-t1-map")).toHaveTextContent(/not in v0\.1/i);
    expect(screen.getByTestId("badge-knee-cartilage-t2")).toHaveTextContent(/not in v0\.1/i);
  });

  it("workbench selects the scenario from ?recipe=", () => {
    render(
      <WorkspaceProvider>
        <WorkbenchCockpit initialRecipeId="abdomen_dixon_gre" />
      </WorkspaceProvider>
    );
    const dropdown = screen.getByTestId("scenario-dropdown") as HTMLSelectElement;
    expect(dropdown.value).toBe("abdomen_dixon");
    expect(screen.getByText(/Hepatic Parenchyma/i)).toBeVisible();
  });

  it("nav chrome says v0.63", () => {
    render(
      <WorkspaceProvider>
        <WorkspaceShell>
          <div>Content</div>
        </WorkspaceShell>
      </WorkspaceProvider>
    );
    expect(screen.getByTestId("version-tag")).toHaveTextContent("v0.63");
  });
});
