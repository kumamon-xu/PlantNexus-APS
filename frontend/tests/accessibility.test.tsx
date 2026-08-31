import { render } from "@testing-library/react";
import { screen } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { parseGanttSegments } from "../src/api/contracts";
import { ScheduleVersionPanel } from "../src/components/ScheduleVersionPanel";
import { WorkspaceStatePanel } from "../src/components/WorkspaceStatePanel";
import type { PlanningWorkspaceClient } from "../src/api/client";
import { AppServicesProvider } from "../src/app/context";
import { createDynamicReplanningClient } from "../src/features/replanning/client";
import { ReplanningWorkspacePage } from "../src/features/replanning/ReplanningWorkspacePage";
import type { ReplanningQueryDocument } from "../src/features/replanning/types";
import { GanttTimeline } from "../src/features/gantt/GanttTimeline";
import { ganttPayload, testScheduleVersion, workspaceResponse } from "./fixtures";
import { LocaleProvider } from "../src/i18n/locale";
import { p4Identity, p4Runtime, responseForQuery } from "./replanningFixtures";

describe("P3-11 accessibility foundation", () => {
  it("has no axe violations in the authority and error primitives", async () => {
    const { container } = render(
      <main>
        <ScheduleVersionPanel version={testScheduleVersion} />
        <WorkspaceStatePanel state="authorization_denied" />
      </main>,
    );
    const result = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(result.violations).toEqual([]);
  });
});

describe("P3-12 visualization accessibility", () => {
  it("has no axe violations in the Gantt/table alternative", async () => {
    const response = await workspaceResponse("GANTT", {
      payloads: [ganttPayload(0), ganttPayload(1)],
      scheduleVersion: testScheduleVersion,
    });
    const { container } = render(
      <MemoryRouter>
        <main>
          <GanttTimeline
            segments={parseGanttSegments(response)}
            grouping="factory"
            scheduleVersionId={testScheduleVersion.schedule_version_id}
            zoom={1}
            selection={{ operationId: null, orderId: null, resourceId: null }}
            onSelect={() => undefined}
          />
        </main>
      </MemoryRouter>,
    );
    const result = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(result.violations).toEqual([]);
  });
});

describe("TEST-REPLAN-FRONTEND-001 accessibility", () => {
  it("has no axe violations in the P4 event/replan/freeze/report workspace", async () => {
    const fetcher = async (input: RequestInfo | URL) => {
      const url = new URL(String(input), "https://plantnexus.test");
      const query = JSON.parse(
        url.searchParams.get("query") ?? "{}",
      ) as ReplanningQueryDocument;
      return new Response(JSON.stringify(await responseForQuery(query)), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };
    const dynamicReplanningClient = createDynamicReplanningClient(
      p4Runtime,
      { async getAccessToken() { return "p4-a11y-token"; } },
      fetcher,
    );
    const query = new URLSearchParams({
      planning_scope_id: p4Identity.planningScopeId,
      authority_id: p4Identity.authorityId,
      stream_id: p4Identity.streamId,
      stream_version: p4Identity.streamVersion,
      from_position: String(p4Identity.fromPosition),
      through_position: String(p4Identity.throughPosition),
      request_id: p4Identity.requestId,
      request_fingerprint: p4Identity.requestFingerprint,
      attempt_id: p4Identity.attemptId,
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const { container } = render(
      <LocaleProvider initialLocale="en-US">
        <QueryClientProvider client={queryClient}>
          <AppServicesProvider
            services={{
              client: {} as PlanningWorkspaceClient,
              dynamicReplanningClient,
              runtime: p4Runtime,
            }}
          >
            <MemoryRouter initialEntries={[`/planning/replanning?${query}`]}>
              <ReplanningWorkspacePage />
            </MemoryRouter>
          </AppServicesProvider>
        </QueryClientProvider>
      </LocaleProvider>,
    );
    await screen.findByRole("heading", {
      name: "ChangeReport and before/after evidence",
    });
    const result = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(result.violations).toEqual([]);
  });
});
