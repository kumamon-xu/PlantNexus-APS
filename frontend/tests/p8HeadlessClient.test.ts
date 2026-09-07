import type { SessionProvider } from "../src/api/session";
import {
  createHeadlessPlanningClient,
  HeadlessClientError,
} from "../src/headless/client";
import { parsePlanningRun } from "../src/headless/contracts";
import {
  cloneFixture,
  jsonResponse,
  p8AcceptedResult,
  p8CanonicalRequestText,
  p8CompletedRun,
  p8CreatedRun,
  p8Runtime,
  p8Scope,
} from "./p8HeadlessFixtures";

const session: SessionProvider = {
  async getAccessToken() {
    return "p8-memory-only-token";
  },
};

describe("TEST-P8-FRONTEND-DISTRIBUTION-001 generated-snapshot Headless client", () => {
  it("sends exact create bytes, explicit identity headers and no ambient credentials", async () => {
    const requests: Array<{ input: string; init: RequestInit | undefined }> = [];
    const fetcher: typeof fetch = async (input, init) => {
      requests.push({ input: String(input), init });
      return jsonResponse(
        p8AcceptedResult,
        202,
        "CORRELATION-P8-SYNTHETIC-001",
      );
    };
    const result = await createHeadlessPlanningClient(
      p8Runtime,
      session,
      fetcher,
    ).create(p8CanonicalRequestText);

    expect(result.disposition).toBe("ACCEPTED");
    const observed = requests[0];
    if (observed === undefined) throw new Error("create request was not observed");
    expect(observed.input).toBe("/api/v1/planning-runs");
    expect(observed.init?.body).toBe(p8CanonicalRequestText);
    expect(observed.init?.credentials).toBe("omit");
    expect(observed.init?.cache).toBe("no-store");
    const headers = new Headers(observed.init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer p8-memory-only-token");
    expect(headers.get("Idempotency-Key")).toBe("p8-synthetic-request-0001");
    expect(headers.get("X-Correlation-Id")).toBe(
      "CORRELATION-P8-SYNTHETIC-001",
    );
  });

  it("uses only the five public P8 routes and server-provided CAS/attempt facts", async () => {
    const calls: Array<{ path: string; init: RequestInit | undefined }> = [];
    const fetcher: typeof fetch = async (input, init) => {
      const path = String(input);
      calls.push({ path, init });
      const correlation = new Headers(init?.headers).get("X-Correlation-Id") ?? "missing";
      if (path.endsWith("/planning-runs")) {
        return jsonResponse(p8AcceptedResult, 202, correlation);
      }
      return jsonResponse(
        path.endsWith("/retry") ? p8CompletedRun : p8CreatedRun,
        path.endsWith("/retry") ? 202 : 200,
        correlation,
      );
    };
    const client = createHeadlessPlanningClient(p8Runtime, session, fetcher);
    await client.create(p8CanonicalRequestText);
    const created = parsePlanningRun(p8CreatedRun);
    await client.status(created.planning_run_id, created.effective_scope, "P8-STATUS");
    await client.result(created.planning_run_id, created.effective_scope, "P8-RESULT");
    await client.cancel(created, "operator cancellation", "P8-CANCEL-KEY", "P8-CANCEL");
    const completed = parsePlanningRun(p8CompletedRun);
    await client.retry(completed, "retry timed out attempt", "P8-RETRY-KEY", "P8-RETRY");

    expect(calls.map(({ path }) => path)).toEqual([
      "/api/v1/planning-runs",
      "/api/v1/planning-runs/PLANNING-RUN-P8-SYNTHETIC-001/status",
      "/api/v1/planning-runs/PLANNING-RUN-P8-SYNTHETIC-001/result",
      "/api/v1/planning-runs/PLANNING-RUN-P8-SYNTHETIC-001/cancel",
      "/api/v1/planning-runs/PLANNING-RUN-P8-SYNTHETIC-001/retry",
    ]);
    for (const call of calls.slice(1)) {
      const headers = new Headers(call.init?.headers);
      expect(headers.get("X-APS-Tenant-Id")).toBe(p8Scope.tenant_id);
      expect(headers.get("X-APS-Factory-Id")).toBe(p8Scope.factory_id);
      expect(headers.get("X-APS-Planning-Scope-Id")).toBe(
        p8Scope.planning_scope_id,
      );
    }
    const cancelBody = JSON.parse(String(calls[3]?.init?.body)) as Record<string, unknown>;
    expect(cancelBody).toMatchObject({
      action_version: "planning-run-cancel-action.v1",
      expected_revision: created.revision,
      expected_state: created.state,
      expected_run_fingerprint: created.run_fingerprint,
    });
    const retryBody = JSON.parse(String(calls[4]?.init?.body)) as Record<string, unknown>;
    expect(retryBody).toMatchObject({
      action_version: "planning-run-retry-action.v1",
      failed_attempt_id: completed.attempt?.attempt_id,
      failed_attempt_number: completed.attempt?.attempt_number,
    });
  });

  it.each([
    [401, "authentication_required"],
    [403, "authorization_denied"],
    [409, "state_conflict"],
    [503, "unavailable"],
  ] as const)("keeps HTTP %i distinguishable as %s", async (status, kind) => {
    const fetcher: typeof fetch = async () =>
      jsonResponse({ message: `HTTP ${status}` }, status, "P8-ERROR");
    const promise = createHeadlessPlanningClient(
      p8Runtime,
      session,
      fetcher,
    ).create(p8CanonicalRequestText);
    await expect(promise).rejects.toMatchObject({ kind, status });
  });

  it("marks a disconnected POST as outcome-unknown and a disconnected GET unavailable", async () => {
    const fetcher: typeof fetch = async () => {
      throw new TypeError("network details must not escape");
    };
    const client = createHeadlessPlanningClient(p8Runtime, session, fetcher);
    await expect(client.create(p8CanonicalRequestText)).rejects.toMatchObject({
      kind: "outcome_unknown",
    });
    await expect(
      client.status("PLANNING-RUN-P8-SYNTHETIC-001", p8Scope, "P8-GET"),
    ).rejects.toMatchObject({ kind: "unavailable" });
  });

  it("rejects unknown success versions, missing no-store and changed scope", async () => {
    const unknown = cloneFixture(p8AcceptedResult) as Record<string, unknown>;
    unknown.canonical_ingress_result_version = "canonical-ingress-result.v2";
    const unknownClient = createHeadlessPlanningClient(
      p8Runtime,
      session,
      async () => jsonResponse(unknown, 202, "CORRELATION-P8-SYNTHETIC-001"),
    );
    await expect(unknownClient.create(p8CanonicalRequestText)).rejects.toMatchObject({
      kind: "version_error",
    });

    const missingNoStore = createHeadlessPlanningClient(
      p8Runtime,
      session,
      async () =>
        new Response(JSON.stringify(p8AcceptedResult), {
          status: 202,
          headers: {
            "Content-Type": "application/json",
            "X-Correlation-Id": "CORRELATION-P8-SYNTHETIC-001",
          },
        }),
    );
    await expect(missingNoStore.create(p8CanonicalRequestText)).rejects.toMatchObject({
      kind: "contract_error",
    });

    const changed = cloneFixture(p8CreatedRun) as Record<string, unknown>;
    const scope = changed.effective_scope as Record<string, unknown>;
    scope.factory_id = "OTHER-FACTORY";
    const changedClient = createHeadlessPlanningClient(
      p8Runtime,
      session,
      async (_input, init) =>
        jsonResponse(changed, 200, new Headers(init?.headers).get("X-Correlation-Id") ?? ""),
    );
    await expect(
      changedClient.status(
        "PLANNING-RUN-P8-SYNTHETIC-001",
        p8Scope,
        "P8-SCOPE",
      ),
    ).rejects.toBeInstanceOf(HeadlessClientError);
  });
});
