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
import { CLINICAL_SCENARIOS, isSpectrumScenario } from "../lib/scenarios";

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
    expect(byId["cest-apt"].executable).toBe(true);
    expect(byId["cest-apt"].recipeId).toBe("cest_amide_z_spectrum");
    expect(byId["cest-apt"].category).toBe("Spectroscopy & Exchange");
    expect(byId["cest-apt"].title).toMatch(/CW/i);
    expect(byId["cest-apt"].title).not.toMatch(/pulsed/i);
    expect(byId["cest-apt"].sequence).toMatch(/CW/i);
    expect(byId["cest-apt"].sequence).not.toMatch(/pulsed/i);
    expect(byId["cest-apt"].keyPhysics).toMatch(/CW/i);
    expect(byId["cest-apt-pulsed"].executable).toBe(true);
    expect(byId["cest-apt-pulsed"].recipeId).toBe("cest_amide_pulsed_z_spectrum");
    expect(byId["cest-apt-pulsed"].category).toBe("Spectroscopy & Exchange");
    expect(byId["cest-apt-pulsed"].title).toMatch(/pulsed/i);
    expect(byId["cest-apt-pulsed"].title).not.toMatch(/CW/i);
    expect(byId["cest-apt-pulsed"].sequence).toMatch(/pulsed/i);
    expect(byId["cest-apt-pulsed"].sequence).not.toMatch(/CW/i);
    expect(byId["cest-apt-pulsed"].keyPhysics).toMatch(/pulsed/i);
    expect(byId["cest-apt-pulsed"].keyPhysics).not.toMatch(/CW/i);
    expect(byId["cest-apt"].parameters).toBeUndefined();
    expect(byId["cest-apt-pulsed"].parameters).toBeUndefined();
    expect(byId["mrs-1h"].parameters).toBeUndefined();
    expect(byId["x-nuclei"].parameters).toBeUndefined();
    expect(byId["mrs-1h"].executable).toBe(false);
    expect(byId["mrs-1h"].recipeId).toBeNull();
    expect(byId["x-nuclei"].executable).toBe(false);

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
    expect(scenarioKeyForRecipe("cest_amide_z_spectrum")).toBe("cest_amide");
    expect(scenarioKeyForRecipe("cest_amide_pulsed_z_spectrum")).toBe("cest_amide");
    expect(scenarioKeyForRecipe("cest_amide_foo_z_spectrum")).toBe("cest_amide");
    expect(scenarioKeyForRecipe("cest_amide_foo_z_spectrum")).not.toBe("ms_brain");
    expect(scenarioKeyForRecipe("cest_amine_z_spectrum")).toBe("cest_amide");
    expect(scenarioKeyForRecipe("cest_amine_z_spectrum")).not.toBe("ms_brain");
    expect(scenarioKeyForRecipe("nope")).toBe("ms_brain");
    expect(RECIPE_TO_SCENARIO.cardiac_cine_gre).toBeUndefined();
  });

  it("cest_amide scenario is Spectroscopy/CEST/VOXEL, not Neuro/SE/AXIAL", () => {
    const cest = CLINICAL_SCENARIOS.cest_amide;
    expect(cest.category).toBe("Spectroscopy");
    expect(cest.seqType).toBe("CEST");
    expect(cest.scanPlane).toBe("VOXEL");
    expect(cest.category).not.toBe("Neuro");
    expect(cest.seqType).not.toBe("SE");
    expect(cest.scanPlane).not.toBe("AXIAL");
    expect(cest.defaultParams).toBeUndefined();
  });

  it("Spectrum identity follows seqType CEST, not the cest_amide key name", () => {
    expect(isSpectrumScenario(CLINICAL_SCENARIOS.cest_amide)).toBe(true);
    expect(isSpectrumScenario(CLINICAL_SCENARIOS.ms_brain)).toBe(false);
    expect(isSpectrumScenario({ seqType: "CEST" })).toBe(true);
    expect(isSpectrumScenario({ seqType: "TSE" })).toBe(false);
  });

  it("Launch Cockpit deep-links executable cases and badges the rest", () => {
    render(<Home />);

    const ms = screen.getByTestId("launch-ms-lesion-t2");
    expect(ms).toHaveAttribute("href", "/workbench?recipe=brain_t2_tse");

    const dixon = screen.getByTestId("launch-dixon-fat-water");
    expect(dixon).toHaveAttribute("href", "/workbench?recipe=abdomen_dixon_gre");

    const dark = screen.getByTestId("launch-dark-blood-tse");
    expect(dark).toHaveAttribute("href", "/workbench?recipe=dark_blood_vessel_wall_tse");

    const cest = screen.getByTestId("launch-cest-apt");
    expect(cest).toHaveAttribute("href", "/workbench?recipe=cest_amide_z_spectrum");
    const pulsed = screen.getByTestId("launch-cest-apt-pulsed");
    expect(pulsed).toHaveAttribute("href", "/workbench?recipe=cest_amide_pulsed_z_spectrum");
    expect(screen.queryByTestId("launch-mrs-1h")).toBeNull();
    expect(screen.getByTestId("badge-mrs-1h")).toHaveTextContent(/not in v0\.1/i);
    expect(screen.getByTestId("badge-x-nuclei")).toHaveTextContent(/not in v0\.1/i);

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

  it("workbench deep-links the CEST recipe without putting it in the clinical dropdown", () => {
    render(
      <WorkspaceProvider>
        <WorkbenchCockpit initialRecipeId="cest_amide_z_spectrum" />
      </WorkspaceProvider>
    );
    expect(screen.getByText(/Amide solute/i)).toBeVisible();
    expect(screen.getByTestId("spectrum-experiment-identity")).toHaveTextContent(/Amide CEST Z-spectrum/);
    expect(screen.getByTestId("spectrum-experiment-identity")).toHaveTextContent(/not MS plaque imaging/i);
    const dropdown = screen.getByTestId("scenario-dropdown") as HTMLSelectElement;
    expect(dropdown.value).toBe("");
    expect(Array.from(dropdown.options).map((option) => option.value)).not.toContain("cest_amide");
    expect(dropdown.selectedOptions[0]?.textContent).toMatch(/Not a clinical imaging case/);
  });

  it("workbench deep-links the pulsed CEST recipe as Spectrum, not MS plaque", () => {
    render(
      <WorkspaceProvider>
        <WorkbenchCockpit initialRecipeId="cest_amide_pulsed_z_spectrum" />
      </WorkspaceProvider>
    );
    expect(screen.getByTestId("spectrum-experiment-identity")).toHaveTextContent(/Amide CEST Z-spectrum/);
    expect(screen.getByTestId("spectrum-experiment-identity")).toHaveTextContent(/not MS plaque imaging/i);
    const dropdown = screen.getByTestId("scenario-dropdown") as HTMLSelectElement;
    expect(dropdown.value).toBe("");
    expect(dropdown.selectedOptions[0]?.textContent).toMatch(/Not a clinical imaging case/);
    expect(screen.queryByTestId("echo-train-rail")).toBeNull();
    expect(screen.queryByTestId("spectrum-control-honesty")).toBeNull();
    expect(screen.getByTestId("cest-b1-slider")).toBeVisible();
    expect(screen.getByTestId("cest-offset-span-slider")).toBeVisible();
    expect(screen.queryByTestId("cest-duty-slider")).toBeNull();
    expect(screen.getByTestId("clinical-rejects-z-spectrum")).toBeVisible();
    expect(screen.queryByTestId("acquisition-plane-picker")).toBeNull();
    expect(screen.queryByRole("button", { name: "AXIAL" })).toBeNull();
    expect(screen.getByTestId("spectrum-clinical-honesty")).toBeVisible();
    expect(screen.getByTestId("spectrum-clinical-honesty")).toHaveTextContent(/no acquisition plane/i);
    expect(screen.queryByText("CLINICAL CONTRAST")).toBeNull();
    expect(screen.getByTestId("display-header-title")).toHaveTextContent("SPECTRUM VIEWPORT · SINGLE VOXEL · Z(Δ)");
    expect(screen.getByTestId("display-header-title")).not.toHaveTextContent("CLINICAL QUAD VIEWPORT");
    expect(screen.getByTestId("display-header-title")).not.toHaveTextContent("AXIAL");
    expect(screen.getByTestId("control-bank-mode")).toHaveTextContent("Saturation & Offset");
    expect(screen.getByTestId("control-bank-mode")).not.toHaveTextContent("Geometry & Contrast");
  });

  it("cest_amide_* deep-link stays Spectrum, not MS plaque", () => {
    render(
      <WorkspaceProvider>
        <WorkbenchCockpit initialRecipeId="cest_amide_foo_z_spectrum" />
      </WorkspaceProvider>
    );
    expect(screen.getByTestId("spectrum-experiment-identity")).toBeVisible();
    expect(screen.getByTestId("spectrum-experiment-identity")).toHaveTextContent(/not MS plaque imaging/i);
    expect(screen.getByTestId("clinical-rejects-z-spectrum")).toBeVisible();
    expect(screen.queryByTestId("clinical-quad-grid")).toBeNull();
  });

  it("nav chrome says v0.67.18", () => {
    render(
      <WorkspaceProvider>
        <WorkspaceShell>
          <div>Content</div>
        </WorkspaceShell>
      </WorkspaceProvider>
    );
    expect(screen.getByTestId("version-tag")).toHaveTextContent("v0.67.18");
  });
});
