import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type { PlanningWorkspaceClient } from "../src/api/client";
import { AppServicesProvider } from "../src/app/context";
import { createDynamicReplanningClient } from "../src/features/replanning/client";
import { ReplanningWorkspacePage } from "../src/features/replanning/ReplanningWorkspacePage";
import type {
  PlanningRunState,
  ReplanAttemptAction,
  ReplanningQueryDocument,
} from "../src/features/replanning/types";
import { LocaleProvider } from "../src/i18n/locale";
import {
  p4Identity,
  p4Runtime,
  responseForQuery,
} from "./replanningFixtures";

const unusedPlanningClient = {} as PlanningWorkspaceClient;
const session = { async getAccessToken() { return "p4-ui-test-token"; } };

function queryString(): string {
  return new URLSearchParams({
    planning_scope_id: p4Identity.planningScopeId,
    authority_id: p4Identity.authorityId,
    stream_id: p4Identity.streamId,
    stream_version: p4Identity.streamVersion,
    from_position: String(p4Identity.fromPosition),
    through_position: String(p4Identity.throughPosition),
    request_id: p4Identity.requestId,
    request_fingerprint: p4Identity.requestFingerprint,
    attempt_id: p4Identity.attemptId,
  }).toString();
}

function renderWorkspace(options: {
  state?: PlanningRunState;
  allowedActions?: ReplanAttemptAction[];
  unknownFirstPost?: boolean;
  postObservations?: Array<{ body: string; key: string | null }>;
  locale?: "zh-CN" | "en-US";
}) {
  let postCount = 0;
  const fetcher = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "https://plantnexus.test");
    if (init?.method === "POST") {
      postCount += 1;
      const body = String(init.body);
      const parsed = JSON.parse(body) as Record<string, unknown>;
      options.postObservations?.push({
        body,
        key: new Headers(init.headers).get("Idempotency-Key"),
      });
      if (options.unknownFirstPost === true && postCount === 1) {
        return new Response(
          JSON.stringify({
            error_version: "planning-workspace-error.v1",
            reason: "UNKNOWN_OUTCOME",
            message: "query exact authority before retry",
            retryable: false,
            correlation_id: parsed.correlation_id,
          }),
          { status: 503, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(
        JSON.stringify({
          response_version: "dynamic-replanning-response.v1",
          operation:
            parsed.action === "CANCEL"
              ? "CANCEL_REPLAN_REQUEST"
              : "RETRY_REPLAN_REQUEST",
          resource_type: "REPLAN_REQUEST",
          resource_id: parsed.request_id,
          result: {
            result_version: "replan-attempt-action-result.v1",
            action: parsed.action,
            request_id: parsed.request_id,
            attempt_id: parsed.expected_attempt_id,
            attempt_number: parsed.expected_attempt_number,
            expected_planning_run_state: parsed.expected_planning_run_state,
            action_fingerprint: parsed.action_fingerprint,
            accepted: true,
          },
          replayed: postCount > 1,
          correlation_id: parsed.correlation_id,
        }),
        { status: 202, headers: { "Content-Type": "application/json" } },
      );
    }
    const query = JSON.parse(
      url.searchParams.get("query") ?? "{}",
    ) as ReplanningQueryDocument;
    return new Response(
      JSON.stringify(
        await responseForQuery(
          query,
          options.state ?? "COMPLETED",
          options.allowedActions ?? [],
        ),
      ),
      {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "X-Correlation-Id": query.correlation_id,
        },
      },
    );
  };
  const dynamicReplanningClient = createDynamicReplanningClient(
    p4Runtime,
    session,
    fetcher,
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <LocaleProvider initialLocale={options.locale ?? "en-US"}>
      <QueryClientProvider client={queryClient}>
        <AppServicesProvider
          services={{
            client: unusedPlanningClient,
            dynamicReplanningClient,
            runtime: p4Runtime,
          }}
        >
          <MemoryRouter initialEntries={[`/planning/replanning?${queryString()}`]}>
            <ReplanningWorkspacePage />
          </MemoryRouter>
        </AppServicesProvider>
      </QueryClientProvider>
    </LocaleProvider>,
  );
}

describe("TEST-REPLAN-FRONTEND-001 replanning workspace", () => {
  it("renders bilingual raw event/freeze/tardiness/Stability and ChangeReport evidence", async () => {
    renderWorkspace({ locale: "zh-CN" });

    expect(await screen.findByRole("heading", { name: "动态重排工作区" })).toBeVisible();
    expect(await screen.findByText("设备不可用")).toBeVisible();
    expect(screen.getByText("MACHINE_UNAVAILABLE")).toBeVisible();
    expect(screen.getByText("lock-p4-ui-freeze-001")).toBeVisible();
    expect(screen.getByText("600", { exact: true })).toBeVisible();
    expect(screen.getAllByText("300", { exact: true }).length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("因执行事实移除")).not.toBeInTheDocument();
    expect(screen.getByText("CHANGED")).toBeVisible();
    expect(screen.getByText("publishable=false", { exact: false })).toBeVisible();
    expect(screen.queryByRole("button", { name: "取消当前尝试" })).not.toBeInTheDocument();
  });

  it("requires confirmation and queries before retrying the exact unknown-outcome action", async () => {
    const observations: Array<{ body: string; key: string | null }> = [];
    renderWorkspace({
      state: "SOLVING",
      allowedActions: ["CANCEL"],
      unknownFirstPost: true,
      postObservations: observations,
    });
    const user = userEvent.setup();
    const cancel = await screen.findByRole("button", { name: "Cancel current attempt" });
    expect(cancel).toBeDisabled();
    await user.type(
      screen.getByRole("textbox", { name: "Action reason" }),
      "cancel synthetic attempt after operator review",
    );
    await user.click(
      screen.getByRole("checkbox", {
        name: "I understand this acts only on the current Simulation PlanningRun attempt.",
      }),
    );
    await user.click(cancel);
    expect(
      await screen.findByText("Outcome unknown — query authority before retry"),
    ).toBeVisible();
    expect(observations).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "Refresh authority" }));
    expect(
      await screen.findByText("Authority unchanged — exact same request may be retried"),
    ).toBeVisible();
    expect(observations).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "Retry same request" }));
    await waitFor(() => expect(observations).toHaveLength(2));
    expect(observations[1]?.key).toBe(observations[0]?.key);
    expect(observations[1]?.body).toBe(observations[0]?.body);
    expect(await screen.findByText("Server confirmed the action")).toBeVisible();
  });

  it("default-denies the P4 control surface in Production without a read", () => {
    const productionRuntime = {
      apiBaseUrl: "/api/v1",
      dataPlane: "PRODUCTION",
      environment: "PRODUCTION",
      synthetic: false,
    } as const;
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <LocaleProvider initialLocale="en-US">
        <QueryClientProvider client={queryClient}>
          <AppServicesProvider
            services={{ client: unusedPlanningClient, runtime: productionRuntime }}
          >
            <MemoryRouter initialEntries={[`/planning/replanning?${queryString()}`]}>
              <ReplanningWorkspacePage />
            </MemoryRouter>
          </AppServicesProvider>
        </QueryClientProvider>
      </LocaleProvider>,
    );
    expect(
      screen.getByText(
        "Dynamic replanning controls are default-deny outside the isolated Simulation runtime.",
      ),
    ).toBeVisible();
  });
});
