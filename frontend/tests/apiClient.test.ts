import { canonicalJson } from "../src/api/canonical";
import { createPlanningWorkspaceClient, WorkspaceClientError } from "../src/api/client";
import { parseScheduleVersion, parseWorkspaceResponse } from "../src/api/contracts";
import { buildWorkspaceQuery } from "../src/api/query";
import type { RuntimeConfig } from "../src/api/runtime";
import { testScheduleVersion, workspaceResponse } from "./fixtures";

const runtime: RuntimeConfig = {
  apiBaseUrl: "https://aps.test/api/v1",
  dataPlane: "PRODUCTION",
  environment: "PRODUCTION",
  synthetic: false,
};

describe("read-only Planning Workspace API client", () => {
  it("sends URL-encoded canonical JSON by GET and uses only the injected token", async () => {
    const responseBody = await workspaceResponse();
    let capturedInput: RequestInfo | URL | undefined;
    let capturedInit: RequestInit | undefined;
    const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      capturedInput = input;
      capturedInit = init;
      return new Response(JSON.stringify(responseBody), {
        status: 200,
        headers: { "Content-Type": "application/json", "X-Correlation-Id": responseBody.correlation_id },
      });
    }) as typeof fetch;
    const client = createPlanningWorkspaceClient(
      runtime,
      { async getAccessToken() { return "ephemeral-test-token"; } },
      fetcher,
    );
    const query = await buildWorkspaceQuery({
      authority: runtime,
      view: "DATA_HEALTH",
      correlationId: "correlation-frontend-test-001",
    });
    await expect(client.queryWorkspace(query, "DATA_HEALTH")).resolves.toEqual(responseBody);
    expect(capturedInit?.method).toBe("GET");
    expect(capturedInit?.cache).toBe("no-store");
    expect(capturedInit?.credentials).toBe("omit");
    expect(new Headers(capturedInit?.headers).get("Authorization")).toBe(
      "Bearer ephemeral-test-token",
    );
    const url = new URL(String(capturedInput));
    expect(url.searchParams.get("query")).toBe(canonicalJson(query));
  });

  it.each([
    [401, "authorization_denied"],
    [403, "authorization_denied"],
    [409, "stale"],
    [422, "contract_error"],
    [503, "server_error"],
  ] as const)("maps HTTP %s without fabricating a ready state", async (status, kind) => {
    const client = createPlanningWorkspaceClient(
      runtime,
      { async getAccessToken() { return null; } },
      vi.fn(async () =>
        new Response(
          JSON.stringify({ message: "safe failure", correlation_id: "correlation-failure-001" }),
          { status, headers: { "Content-Type": "application/json" } },
        ),
      ) as typeof fetch,
    );
    const query = await buildWorkspaceQuery({ authority: runtime, view: "DATA_HEALTH" });
    const error = await client.queryWorkspace(query, "DATA_HEALTH").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(WorkspaceClientError);
    expect((error as WorkspaceClientError).kind).toBe(kind);
    expect((error as WorkspaceClientError).correlationId).toBe("correlation-failure-001");
  });

  it("fails visibly for an unknown ScheduleVersion state", () => {
    expect(() => parseScheduleVersion({ ...testScheduleVersion, state: "ARCHIVED" })).toThrow(
      /unknown ScheduleVersion state/u,
    );
  });

  it("rejects payload fingerprint drift", async () => {
    const response = await workspaceResponse();
    response.items[0]!.payload_fingerprint = `sha256:${"f".repeat(64)}`;
    await expect(parseWorkspaceResponse(response, "DATA_HEALTH")).rejects.toThrow(
      /payload_fingerprint/u,
    );
  });
});
