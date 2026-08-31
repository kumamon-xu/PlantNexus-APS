import type { JsonObject } from "../src/api/types";
import { createDynamicReplanningClient, ReplanningClientError } from "../src/features/replanning/client";
import {
  buildReplanAttemptAction,
  buildRequestQuery,
  buildTimelineQuery,
} from "../src/features/replanning/query";
import type { ReplanningQueryDocument } from "../src/features/replanning/types";
import {
  p4AttemptId,
  p4Fingerprint,
  p4Identity,
  p4RequestId,
  p4Runtime,
  responseForQuery,
} from "./replanningFixtures";

const session = {
  async getAccessToken() {
    return "p4-ui-test-token";
  },
};

function jsonResponse(value: unknown, status = 200, correlationId?: string): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...(correlationId === undefined ? {} : { "X-Correlation-Id": correlationId }),
    },
  });
}

describe("TEST-REPLAN-FRONTEND-001 dynamic-replanning client", () => {
  it("sends canonical locale-neutral queries and accepts only bound server projections", async () => {
    const observations: Array<{ authorization: string | null; query: ReplanningQueryDocument }> = [];
    const fetcher = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "https://plantnexus.test");
      const query = JSON.parse(url.searchParams.get("query") ?? "{}") as ReplanningQueryDocument;
      observations.push({
        authorization: new Headers(init?.headers).get("Authorization"),
        query,
      });
      return jsonResponse(await responseForQuery(query), 200, query.correlation_id);
    };
    const client = createDynamicReplanningClient(p4Runtime, session, fetcher);
    const [timelineQuery, requestQuery] = await Promise.all([
      buildTimelineQuery(p4Runtime, p4Identity),
      buildRequestQuery(p4Runtime, p4Identity),
    ]);

    const [timeline, request] = await Promise.all([
      client.listExecutionEvents(timelineQuery),
      client.getReplanRequest(requestQuery),
    ]);

    expect(timeline.events).toHaveLength(2);
    expect(request.request.request_id).toBe(p4RequestId);
    expect(observations).toHaveLength(2);
    expect(observations.every((item) => item.authorization === "Bearer p4-ui-test-token")).toBe(true);
    expect(
      observations.some((item) =>
        Object.keys(item.query).some((key) => /locale|language/iu.test(key)),
      ),
    ).toBe(false);
  });

  it("binds CANCEL to expected attempt state and hashes the key before transport", async () => {
    const requests: Array<{ body: JsonObject; headers: Headers }> = [];
    const fetcher = async (_input: RequestInfo | URL, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body)) as JsonObject;
      const headers = new Headers(init?.headers);
      requests.push({ body, headers });
      return jsonResponse(
        {
          response_version: "dynamic-replanning-response.v1",
          operation: "CANCEL_REPLAN_REQUEST",
          resource_type: "REPLAN_REQUEST",
          resource_id: p4RequestId,
          result: {
            result_version: "replan-attempt-action-result.v1",
            action: "CANCEL",
            request_id: p4RequestId,
            attempt_id: p4AttemptId,
            attempt_number: 1,
            expected_planning_run_state: "SOLVING",
            action_fingerprint: body.action_fingerprint,
            accepted: true,
          },
          replayed: false,
          correlation_id: body.correlation_id,
        },
        202,
        String(body.correlation_id),
      );
    };
    const client = createDynamicReplanningClient(p4Runtime, session, fetcher);
    const action = await buildReplanAttemptAction(p4Runtime, {
      action: "CANCEL",
      requestId: p4RequestId,
      requestFingerprint: p4Fingerprint("8"),
      attempt: {
        attempt_id: p4AttemptId,
        attempt_number: 1,
        planning_run_id: "planning-run-p4-ui-001",
        state: "SOLVING",
        allowed_actions: ["CANCEL"],
        updated_at_utc: "2026-08-31T06:01:00Z",
      },
      planningScopeId: p4Identity.planningScopeId,
      reason: "operator cancels synthetic replan attempt",
      idempotencyKey: "p4-ui-idempotency-key-0001",
      correlationId: "correlation-p4-ui-cancel-001",
    });
    const response = await client.executeAttemptAction(action);

    expect(response.result.accepted).toBe(true);
    expect(requests).toHaveLength(1);
    expect(requests[0]?.headers.get("Idempotency-Key")).toBe(
      "p4-ui-idempotency-key-0001",
    );
    expect(requests[0]?.headers.get("X-Planning-Scope-Id")).toBe(
      p4Identity.planningScopeId,
    );
    expect(requests[0]?.body.idempotency_key_reference).toMatch(
      /^sha256:[0-9a-f]{64}$/u,
    );
    expect(JSON.stringify(requests[0]?.body)).not.toContain(
      "p4-ui-idempotency-key-0001",
    );
  });

  it("marks a 503 POST as unknown and never advertises blind retry", async () => {
    let calls = 0;
    const fetcher = async (_input: RequestInfo | URL, init?: RequestInit) => {
      calls += 1;
      const body = JSON.parse(String(init?.body)) as JsonObject;
      return jsonResponse(
        {
          error_version: "planning-workspace-error.v1",
          reason: "UNKNOWN_OUTCOME",
          message: "Outcome must be queried before retry",
          retryable: false,
          correlation_id: body.correlation_id,
        },
        503,
        String(body.correlation_id),
      );
    };
    const client = createDynamicReplanningClient(p4Runtime, session, fetcher);
    const action = await buildReplanAttemptAction(p4Runtime, {
      action: "RETRY",
      requestId: p4RequestId,
      requestFingerprint: p4Fingerprint("8"),
      attempt: {
        attempt_id: p4AttemptId,
        attempt_number: 1,
        planning_run_id: "planning-run-p4-ui-001",
        state: "FAILED",
        allowed_actions: ["RETRY"],
        updated_at_utc: "2026-08-31T06:01:00Z",
      },
      planningScopeId: p4Identity.planningScopeId,
      reason: "retry synthetic failed attempt after review",
    });

    await expect(client.executeAttemptAction(action)).rejects.toMatchObject({
      name: "ReplanningClientError",
      outcomeUnknown: true,
      reason: "UNKNOWN_OUTCOME",
    } satisfies Partial<ReplanningClientError>);
    expect(calls).toBe(1);
  });

  it("rejects Production query construction before any transport call", async () => {
    await expect(
      buildTimelineQuery(
        {
          apiBaseUrl: "/api/v1",
          dataPlane: "PRODUCTION",
          environment: "PRODUCTION",
          synthetic: false,
        },
        p4Identity,
      ),
    ).rejects.toThrow("isolated Simulation runtime");
  });
});
