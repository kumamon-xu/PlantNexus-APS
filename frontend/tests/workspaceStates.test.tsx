import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { WorkspaceClientError, type PlanningWorkspaceClient } from "../src/api/client";
import type { RuntimeConfig } from "../src/api/runtime";
import { AppServicesProvider } from "../src/app/context";
import { WorkspaceStatePanel } from "../src/components/WorkspaceStatePanel";
import { WorkspaceCollectionPage } from "../src/pages/WorkspaceCollectionPage";
import { testScheduleVersion, workspaceResponse } from "./fixtures";

const runtime: RuntimeConfig = {
  apiBaseUrl: "/api/v1",
  dataPlane: "PRODUCTION",
  environment: "PRODUCTION",
  synthetic: false,
};

function renderPage(client: PlanningWorkspaceClient) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AppServicesProvider services={{ client, runtime }}>
        <MemoryRouter initialEntries={["/planning/data-health"]}>
          <WorkspaceCollectionPage title="Data health" view="DATA_HEALTH" />
        </MemoryRouter>
      </AppServicesProvider>
    </QueryClientProvider>,
  );
}

function clientWith(
  queryWorkspace: PlanningWorkspaceClient["queryWorkspace"],
): PlanningWorkspaceClient {
  return {
    async getPlanningRun() {
      return { planning_run_id: "planning-run-test-001" };
    },
    async getScheduleVersion() {
      return testScheduleVersion;
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
    queryWorkspace,
    async compareScheduleVersions() {
      throw new Error("not used by this test");
    },
  };
}

describe("Planning Workspace visible states", () => {
  it.each([
    ["stale", "ScheduleVersion changed"],
    ["authorization_denied", "Authorization denied"],
    ["contract_error", "Contract error"],
    ["server_error", "Workspace unavailable"],
  ] as const)("renders %s distinctly", (state, title) => {
    render(<WorkspaceStatePanel state={state} />);
    expect(screen.getByRole("alert")).toHaveTextContent(title);
  });

  it("renders loading without a success placeholder", () => {
    render(<WorkspaceStatePanel state="loading" />);
    expect(screen.getByLabelText("Loading authoritative workspace data")).toBeInTheDocument();
    expect(screen.queryByText("No matching items")).not.toBeInTheDocument();
  });

  it("distinguishes found=false from found=true/items=[]", () => {
    const { rerender } = render(<WorkspaceStatePanel state="empty" emptyKind="missing" />);
    expect(screen.getByText("Resource not found")).toBeInTheDocument();
    rerender(<WorkspaceStatePanel state="empty" emptyKind="collection" />);
    expect(screen.getByText("No matching items")).toBeInTheDocument();
  });

  it("renders a ready carrier with server authority and raw UTC", async () => {
    const response = await workspaceResponse();
    renderPage(clientWith(async () => response));
    await waitFor(() => expect(screen.getByText("item-test-1")).toBeInTheDocument());
    expect(screen.getByText("server application")).toBeInTheDocument();
    expect(screen.getByText("2026-08-25T01:04:05Z")).toBeInTheDocument();
    expect(screen.getByText(/HEALTHY/u)).toBeInTheDocument();
  });

  it("does not turn an authorization denial into an empty or ready state", async () => {
    renderPage(
      clientWith(async () => {
        throw new WorkspaceClientError(
          "authorization_denied",
          "server denied view",
          403,
          "correlation-auth-test",
        );
      }),
    );
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("server denied view"));
    expect(screen.queryByText("No matching items")).not.toBeInTheDocument();
    expect(screen.queryByText("Authoritative payload")).not.toBeInTheDocument();
  });
});
