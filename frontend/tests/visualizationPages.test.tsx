import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { PlanningWorkspaceClient } from "../src/api/client";
import type { RuntimeConfig } from "../src/api/runtime";
import { AppServicesProvider } from "../src/app/context";
import { GanttPage } from "../src/features/gantt/GanttPage";
import { ResourceLoadPage } from "../src/features/resource-load/ResourceLoadPage";
import { VersionComparisonPage } from "../src/features/version-comparison/VersionComparisonPage";
import {
  comparedScheduleVersion,
  comparisonPayload,
  ganttPayload,
  resourceLoadPayload,
  testScheduleVersion,
  workspaceResponse,
} from "./fixtures";

const runtime: RuntimeConfig = {
  apiBaseUrl: "/api/v1",
  dataPlane: "PRODUCTION",
  environment: "PRODUCTION",
  synthetic: false,
};

const client: PlanningWorkspaceClient = {
  async getPlanningRun() {
    return { planning_run_id: "planning-run-test-001" };
  },
  async getScheduleVersion(id) {
    return id === comparedScheduleVersion.schedule_version_id
      ? comparedScheduleVersion
      : testScheduleVersion;
  },
  async getExportJob() {
    throw new Error("not used by this test");
  },
  async executeCommand() {
    throw new Error("not used by this test");
  },
  async downloadExportPackage() {
    throw new Error("not used by this test");
  },
  async queryWorkspace(_query, view) {
    if (view === "GANTT") {
      return workspaceResponse(view, {
        payloads: [ganttPayload(0), ganttPayload(1)],
        scheduleVersion: testScheduleVersion,
      });
    }
    if (view === "RESOURCE_LOAD") {
      return workspaceResponse(view, {
        payloads: [resourceLoadPayload],
        scheduleVersion: testScheduleVersion,
      });
    }
    if (view === "KPI") {
      return workspaceResponse(view, {
        payloads: [{ kpi_id: "kpi-test-001", delivery: { late_order_count: 0 } }],
        scheduleVersion: testScheduleVersion,
      });
    }
    if (view === "DIAGNOSTICS") {
      return workspaceResponse(view, {
        payloads: [{ diagnostic_source: "VALIDATION_REPORT", status: "PASS" }],
        scheduleVersion: testScheduleVersion,
      });
    }
    throw new Error(`unexpected view ${view}`);
  },
  async compareScheduleVersions() {
    return workspaceResponse("VERSION_COMPARISON", {
      payloads: [comparisonPayload],
      scheduleVersion: testScheduleVersion,
    });
  },
};

function renderRoute(initialEntry: string, path: string, element: React.ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AppServicesProvider services={{ client, runtime }}>
        <MemoryRouter initialEntries={[initialEntry]}>
          <Routes><Route path={path} element={element} /></Routes>
        </MemoryRouter>
      </AppServicesProvider>
    </QueryClientProvider>,
  );
}

describe("P3-12 visualization pages", () => {
  it("renders server Gantt facts and explicit KPI/diagnostics overlays", async () => {
    renderRoute(
      `/planning/versions/${testScheduleVersion.schedule_version_id}/gantt/factory`,
      "/planning/versions/:schedule_version_id/gantt/factory",
      <GanttPage grouping="factory" />,
    );
    await waitFor(() =>
      expect(screen.getAllByText(/operation-test-1/u).length).toBeGreaterThan(0),
    );
    expect(screen.getByText(/late_order_count/u)).toBeInTheDocument();
    expect(screen.getByText(/VALIDATION_REPORT/u)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve|publish|export|lock/u })).toBeNull();
  });

  it("renders Resource Load facts and a resource-filtered Gantt link", async () => {
    renderRoute(
      `/resource-load?schedule_version_id=${testScheduleVersion.schedule_version_id}&resource_id=resource-test-1`,
      "/resource-load",
      <ResourceLoadPage />,
    );
    await waitFor(() => expect(screen.getByText("14400")).toBeInTheDocument());
    expect(screen.getAllByText("0.5")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Machine Gantt" })).toHaveAttribute(
      "href",
      expect.stringContaining("resource_id=resource-test-1"),
    );
  });

  it("renders only server-classified changed deltas by default", async () => {
    renderRoute(
      `/compare?schedule_version_id=${testScheduleVersion.schedule_version_id}&compared_schedule_version_id=${comparedScheduleVersion.schedule_version_id}`,
      "/compare",
      <VersionComparisonPage />,
    );
    await waitFor(() => expect(screen.getByText("Server summary")).toBeInTheDocument());
    expect(screen.getByText("START_SHIFT")).toBeInTheDocument();
    expect(screen.queryByText("UNCHANGED")).toBeNull();
    expect(screen.getByText("WEIGHTED_TARDINESS")).toBeInTheDocument();
  });
});
