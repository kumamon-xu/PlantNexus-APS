import { canonicalJson } from "./canonical";
import {
  ContractViolation,
  isJsonObject,
  parsePlanningRun,
  parseScheduleVersion,
  parseWorkspaceResponse,
} from "./contracts";
import type { RuntimeConfig } from "./runtime";
import type { SessionProvider } from "./session";
import type {
  ClientFailureKind,
  JsonObject,
  ScheduleVersion,
  WorkspaceHttpResponse,
  WorkspaceQueryDocument,
  WorkspaceView,
} from "./types";

export class WorkspaceClientError extends Error {
  constructor(
    readonly kind: ClientFailureKind,
    message: string,
    readonly status: number | null,
    readonly correlationId: string | null,
  ) {
    super(message);
    this.name = "WorkspaceClientError";
  }
}

export interface PlanningWorkspaceClient {
  getPlanningRun(planningRunId: string): Promise<JsonObject>;
  getScheduleVersion(scheduleVersionId: string): Promise<ScheduleVersion>;
  queryWorkspace(
    query: WorkspaceQueryDocument,
    expectedView: WorkspaceView,
  ): Promise<WorkspaceHttpResponse>;
}

function kindForStatus(status: number): ClientFailureKind {
  if (status === 401 || status === 403) return "authorization_denied";
  if (status === 409) return "stale";
  if (status === 404 || status === 422) return "contract_error";
  return "server_error";
}

function safeError(value: unknown, fallback: string): {
  message: string;
  correlationId: string | null;
} {
  if (!isJsonObject(value)) return { message: fallback, correlationId: null };
  return {
    message: typeof value.message === "string" ? value.message : fallback,
    correlationId:
      typeof value.correlation_id === "string" ? value.correlation_id : null,
  };
}

function pathSegment(value: string): string {
  const trimmed = value.trim();
  if (trimmed.length === 0 || /[\s\u0000-\u001f\u007f]/u.test(trimmed)) {
    throw new WorkspaceClientError(
      "contract_error",
      "Resource identity is empty or contains a control character",
      null,
      null,
    );
  }
  return encodeURIComponent(trimmed);
}

export function createPlanningWorkspaceClient(
  config: RuntimeConfig,
  session: SessionProvider,
  fetcher: typeof fetch = globalThis.fetch,
): PlanningWorkspaceClient {
  async function get(path: string): Promise<unknown> {
    const token = await session.getAccessToken();
    const headers = new Headers({ Accept: "application/json" });
    if (token !== null) {
      if (
        token.length === 0 ||
        token.trim() !== token ||
        /[\u0000-\u001f\u007f]/u.test(token)
      ) {
        throw new WorkspaceClientError(
          "authorization_denied",
          "Session provider returned an invalid credential",
          null,
          null,
        );
      }
      headers.set("Authorization", `Bearer ${token}`);
    }
    let response: Response;
    try {
      response = await fetcher(`${config.apiBaseUrl}${path}`, {
        method: "GET",
        headers,
        cache: "no-store",
        credentials: "omit",
      });
    } catch {
      throw new WorkspaceClientError(
        "server_error",
        "Planning Workspace is unavailable",
        null,
        null,
      );
    }
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new WorkspaceClientError(
        response.ok ? "contract_error" : kindForStatus(response.status),
        "Server returned a non-JSON response",
        response.status,
        response.headers.get("X-Correlation-Id"),
      );
    }
    if (!response.ok) {
      const detail = safeError(payload, `Request failed with HTTP ${response.status}`);
      throw new WorkspaceClientError(
        kindForStatus(response.status),
        detail.message,
        response.status,
        detail.correlationId ?? response.headers.get("X-Correlation-Id"),
      );
    }
    return payload;
  }

  async function checked<T>(operation: () => Promise<T>): Promise<T> {
    try {
      return await operation();
    } catch (error) {
      if (error instanceof WorkspaceClientError) throw error;
      if (error instanceof ContractViolation || error instanceof TypeError) {
        throw new WorkspaceClientError("contract_error", error.message, 200, null);
      }
      throw new WorkspaceClientError(
        "contract_error",
        "Server response failed the read-only contract",
        200,
        null,
      );
    }
  }

  return {
    async getPlanningRun(planningRunId) {
      return checked(async () =>
        parsePlanningRun(await get(`/planning-runs/${pathSegment(planningRunId)}`)),
      );
    },
    async getScheduleVersion(scheduleVersionId) {
      return checked(async () =>
        parseScheduleVersion(
          await get(`/schedule-versions/${pathSegment(scheduleVersionId)}`),
        ),
      );
    },
    async queryWorkspace(query, expectedView) {
      return checked(async () => {
        const encoded = new URLSearchParams({ query: canonicalJson(query) });
        const path =
          query.resource.resource_type === "WORKSPACE"
            ? workspacePath(expectedView)
            : scheduleWorkspacePath(
                String(query.resource.resource_id),
                expectedView,
              );
        return parseWorkspaceResponse(await get(`${path}?${encoded}`), expectedView);
      });
    },
  };
}

function workspacePath(view: WorkspaceView): string {
  const paths: Partial<Record<WorkspaceView, string>> = {
    DATA_HEALTH: "/workspace/data-health",
    IMPORT_RUNS: "/workspace/import-runs",
    PLANNING_RUNS: "/workspace/planning-runs",
  };
  const path = paths[view];
  if (path === undefined) {
    throw new WorkspaceClientError(
      "contract_error",
      `${view} requires a ScheduleVersion precondition`,
      null,
      null,
    );
  }
  return path;
}

function scheduleWorkspacePath(id: string, view: WorkspaceView): string {
  return `/schedule-versions/${pathSegment(id)}/workspace/${encodeURIComponent(view)}`;
}
