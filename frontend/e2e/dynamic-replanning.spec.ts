import { expect, test, type Page, type Route } from "@playwright/test";

import type { JsonObject } from "../src/api/types";
import type {
  PlanningRunState,
  ReplanAttemptAction,
  ReplanningQueryDocument,
  ReplanningWorkspaceIdentity,
} from "../src/features/replanning/types";
import {
  p4Event,
  p4Identity,
  responseForQuery,
} from "../tests/replanningFixtures";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    globalThis.localStorage.setItem("plantnexus.locale.v1", "en-US");
  });
});

const fiveDisruptionEvents = [
  p4Event(1, "URGENT_DEMAND_RECEIVED"),
  p4Event(2, "MACHINE_UNAVAILABLE"),
  p4Event(3, "MACHINE_RECOVERED"),
  p4Event(4, "MATERIAL_DELAYED"),
  p4Event(5, "PROCESSING_REMAINING_CHANGED"),
  p4Event(6, "OPERATION_COMPLETED"),
];

const browserIdentity: ReplanningWorkspaceIdentity = {
  ...p4Identity,
  throughPosition: fiveDisruptionEvents.length,
};

function workspaceUrl(identity = browserIdentity): string {
  const query = new URLSearchParams({
    planning_scope_id: identity.planningScopeId,
    authority_id: identity.authorityId,
    stream_id: identity.streamId,
    stream_version: identity.streamVersion,
    from_position: String(identity.fromPosition),
    through_position: String(identity.throughPosition),
    request_id: identity.requestId,
    request_fingerprint: identity.requestFingerprint,
    attempt_id: identity.attemptId,
  });
  return `/planning/replanning?${query}`;
}

interface MockOptions {
  state?: PlanningRunState;
  allowedActions?: ReplanAttemptAction[];
  errorStatus?: number | null;
  tamperReport?: boolean;
  abortFirstAction?: boolean;
}

interface ActionObservation {
  body: string;
  key: string | null;
  planningScope: string | null;
}

async function fulfillJson(route: Route, status: number, body: unknown) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function installMock(page: Page, options: MockOptions = {}) {
  const actions: ActionObservation[] = [];
  let postCount = 0;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    if (request.method() === "POST") {
      postCount += 1;
      const bodyText = request.postData() ?? "{}";
      const body = JSON.parse(bodyText) as JsonObject;
      actions.push({
        body: bodyText,
        key: request.headers()["idempotency-key"] ?? null,
        planningScope: request.headers()["x-planning-scope-id"] ?? null,
      });
      if (options.abortFirstAction === true && postCount === 1) {
        await route.abort("failed");
        return;
      }
      await fulfillJson(route, 202, {
        response_version: "dynamic-replanning-response.v1",
        operation:
          body.action === "CANCEL"
            ? "CANCEL_REPLAN_REQUEST"
            : "RETRY_REPLAN_REQUEST",
        resource_type: "REPLAN_REQUEST",
        resource_id: body.request_id,
        result: {
          result_version: "replan-attempt-action-result.v1",
          action: body.action,
          request_id: body.request_id,
          attempt_id: body.expected_attempt_id,
          attempt_number: body.expected_attempt_number,
          expected_planning_run_state: body.expected_planning_run_state,
          action_fingerprint: body.action_fingerprint,
          accepted: true,
        },
        replayed: postCount > 1,
        correlation_id: body.correlation_id,
      });
      return;
    }
    const errorStatus = options.errorStatus ?? null;
    if (errorStatus !== null) {
      await fulfillJson(route, errorStatus, {
        error_version: "planning-workspace-error.v1",
        reason:
          errorStatus === 409
            ? "STALE_SOURCE"
            : errorStatus === 422
              ? "INVALID_QUERY"
              : errorStatus >= 500
                ? "SERVICE_UNAVAILABLE"
                : "AUTHORIZATION_DENIED",
        message: `bounded HTTP ${errorStatus}`,
        retryable: false,
        correlation_id: "correlation-p4-browser-error",
      });
      return;
    }
    const url = new URL(request.url());
    const query = JSON.parse(
      url.searchParams.get("query") ?? "{}",
    ) as ReplanningQueryDocument;
    const response = await responseForQuery(
      query,
      options.state ?? "COMPLETED",
      options.allowedActions ?? [],
      fiveDisruptionEvents,
    );
    if (options.tamperReport === true && query.query_kind === "CHANGE_REPORT") {
      const tardiness = response.result.tardiness as JsonObject;
      tardiness.after_seconds = 0;
    }
    await fulfillJson(route, 200, response);
  });
  return actions;
}

test("renders the five-disruption timeline, freeze, before/after tardiness, Stability and ChangeReport", async ({ page }) => {
  await installMock(page);
  await page.goto(workspaceUrl());

  await expect(page.getByRole("heading", { name: "Dynamic replanning workspace" })).toBeVisible();
  await expect(page.locator(".event-timeline > li")).toHaveCount(6);
  for (const label of [
    "Urgent demand received",
    "Machine unavailable",
    "Machine recovered",
    "Material delayed",
    "Remaining processing changed",
    "Operation completed",
  ]) {
    await expect(page.getByText(label, { exact: false }).first()).toBeVisible();
  }
  await expect(page.getByText("lock-p4-ui-freeze-001", { exact: true })).toBeVisible();
  await expect(page.getByText("600", { exact: true })).toBeVisible();
  await expect(page.getByText("300", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("CHANGED", { exact: true })).toBeVisible();
  await expect(page.getByText("publishable=false", { exact: false })).toBeVisible();
  await expect(page.getByText("P4 evidence stops at a reviewable Simulation DRAFT.", { exact: false })).toBeVisible();

  await page.getByRole("combobox", { name: "Language" }).click();
  await page.getByText("简体中文", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "动态重排工作区" })).toBeVisible();
  await expect(page.getByText("已收到紧急需求", { exact: false }).first()).toBeVisible();
});

test("maps 401/403/409/422/500 without cached or zero-value fallback", async ({ page }) => {
  let status = 401;
  await page.route("**/api/v1/**", async (route) => {
    await fulfillJson(route, status, {
      error_version: "planning-workspace-error.v1",
      reason: status === 409 ? "STALE_SOURCE" : "AUTHORIZATION_DENIED",
      message: `bounded HTTP ${status}`,
      retryable: false,
      correlation_id: `correlation-p4-browser-${status}`,
    });
  });
  const expected = new Map<number, string>([
    [401, "Authorization denied"],
    [403, "Authorization denied"],
    [409, "ScheduleVersion changed"],
    [422, "Contract error"],
    [500, "Workspace unavailable"],
  ]);
  for (const code of [401, 403, 409, 422, 500]) {
    status = code;
    await page.goto(`${workspaceUrl()}&error_case=${code}`);
    await expect(page.getByText(expected.get(code)!, { exact: true })).toBeVisible();
    await expect(page.getByText(`bounded HTTP ${code}`, { exact: false })).toBeVisible();
    await expect(page.getByText("Before weighted tardiness", { exact: true })).not.toBeVisible();
  }
});

test("rejects a fingerprint-tampered ChangeReport instead of displaying partial success", async ({ page }) => {
  await installMock(page, { tamperReport: true });
  await page.goto(workspaceUrl());

  await expect(page.getByText("Contract error", { exact: true })).toBeVisible();
  await expect(
    page.getByText("projection_fingerprint", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("After weighted tardiness", { exact: true })).not.toBeVisible();
});

test("queries authority after a network-unknown CANCEL and retries the exact retained request", async ({ page }) => {
  const actions = await installMock(page, {
    state: "SOLVING",
    allowedActions: ["CANCEL"],
    abortFirstAction: true,
  });
  await page.goto(workspaceUrl());
  const cancel = page.getByRole("button", { name: "Cancel current attempt" });
  await expect(cancel).toBeDisabled();
  await page.getByRole("textbox", { name: "Action reason" }).fill(
    "cancel synthetic attempt after browser review",
  );
  await page
    .getByRole("checkbox", {
      name: "I understand this acts only on the current Simulation PlanningRun attempt.",
    })
    .check();
  await cancel.click();
  await expect(
    page.getByText("Outcome unknown — query authority before retry", { exact: true }),
  ).toBeVisible();
  expect(actions).toHaveLength(1);

  await page.getByRole("button", { name: "Refresh authority" }).click();
  await expect(
    page.getByText("Authority unchanged — exact same request may be retried", {
      exact: true,
    }),
  ).toBeVisible();
  expect(actions).toHaveLength(1);

  await page.getByRole("button", { name: "Retry same request" }).click();
  await expect(page.getByText("Server confirmed the action", { exact: true })).toBeVisible();
  expect(actions).toHaveLength(2);
  expect(actions[1]).toEqual(actions[0]);
  expect(actions[0]?.planningScope).toBe(browserIdentity.planningScopeId);
});

test("mounts RETRY only for server-authorized terminal authority", async ({ page }) => {
  const actions = await installMock(page, {
    state: "FAILED",
    allowedActions: ["RETRY"],
  });
  await page.goto(workspaceUrl());
  await expect(page.getByRole("button", { name: "Cancel current attempt" })).not.toBeVisible();
  const retry = page.getByRole("button", { name: "Retry terminal attempt" });
  await page.getByRole("textbox", { name: "Action reason" }).fill(
    "retry synthetic terminal attempt after review",
  );
  await page
    .getByRole("checkbox", {
      name: "I understand this acts only on the current Simulation PlanningRun attempt.",
    })
    .check();
  await retry.click();
  await expect(page.getByText("Server confirmed the action", { exact: true })).toBeVisible();
  expect(actions).toHaveLength(1);
  expect(JSON.parse(actions[0]!.body)).toMatchObject({
    action: "RETRY",
    expected_planning_run_state: "FAILED",
  });
});
