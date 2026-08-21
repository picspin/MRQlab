import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WorkspaceProvider } from "../components/workspace/WorkspaceProvider";
import { WorkbenchCockpit } from "../components/workbench/WorkbenchCockpit";

const COCKPIT_OK = {
  seq_type: "TSE",
  fa_deg: 150,
  te_ms: 100,
  tr_ms: 3000,
  is_gre: false,
  refocus_eff: 1,
  relative_sar: 35.6,
  delta_signal: 0.16,
  cnr_proxy: 3.2,
  tissues: [],
  signals: {},
};

const RESULT_OK = {
  schema_version: "1.0",
  experiment_id: "recipe:brain_t2_tse",
  observations: [
    {
      id: "signal",
      kind: "signal",
      data: { echo_count: 16 },
      provenance: { engine: "epg", representation: "epg" },
    },
  ],
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("Wave A: fail-closed RUN from clinical recipe", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo) => {
        const url = String(input);
        if (url.includes("/cockpit/signals")) return jsonResponse(COCKPIT_OK);
        return jsonResponse({ detail: "not found" }, 404);
      })
    );
  });

  it("does not auto-POST /experiments/run on mount", async () => {
    render(
      <WorkspaceProvider>
        <WorkbenchCockpit />
      </WorkspaceProvider>
    );
    await waitFor(() => expect(screen.getByTestId("run-experiment-btn")).toBeVisible());
    const urls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.includes("/experiments/run"))).toBe(false);
  });

  it("POSTs /experiments/run-from-recipe with brain_t2_tse and shows RESULT", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/cockpit/signals")) return jsonResponse(COCKPIT_OK);
      if (url.includes("/experiments/run-from-recipe")) {
        expect(init?.method).toBe("POST");
        const body = JSON.parse(String(init?.body));
        expect(body.recipe_id).toBe("brain_t2_tse");
        expect(body.params.te).toBeCloseTo(0.1);
        expect(body.params.tr).toBeCloseTo(3.0);
        return jsonResponse(RESULT_OK);
      }
      return jsonResponse({ detail: "not found" }, 404);
    });

    render(
      <WorkspaceProvider>
        <WorkbenchCockpit />
      </WorkspaceProvider>
    );
    fireEvent.click(screen.getByTestId("run-experiment-btn"));
    await waitFor(() => expect(screen.getByTestId("status-rail")).toHaveTextContent("STATUS: RESULT"));
    expect(screen.getByTestId("status-rail")).toHaveTextContent("KERNEL ENGINE: EPG");
    const urls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.includes("/experiments/run-from-recipe"))).toBe(true);
    expect(urls.some((u) => /\/experiments\/run$/.test(u) || u.endsWith("/experiments/run"))).toBe(false);
  });

  it("sets STATUS ERROR and does not mint a fake ResultGraph on 422", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/cockpit/signals")) return jsonResponse(COCKPIT_OK);
      if (url.includes("/experiments/run-from-recipe")) {
        return jsonResponse({ detail: [{ loc: ["body", "intent"], msg: "Field required" }] }, 422);
      }
      return jsonResponse({ detail: "not found" }, 404);
    });

    render(
      <WorkspaceProvider>
        <WorkbenchCockpit />
      </WorkspaceProvider>
    );
    fireEvent.click(screen.getByTestId("run-experiment-btn"));
    await waitFor(() => expect(screen.getByTestId("status-rail")).toHaveTextContent("STATUS: ERROR"));
    expect(screen.getByTestId("run-error")).toBeVisible();
    expect(screen.getByTestId("status-rail")).not.toHaveTextContent("STATUS: RESULT");
  });
});
