import { canonicalJson, sha256Fingerprint } from "../../api/canonical";
import { ContractViolation, isJsonObject } from "../../api/contracts";
import type { RuntimeConfig } from "../../api/runtime";
import type { SessionProvider } from "../../api/session";
import type { ClientFailureKind, JsonObject } from "../../api/types";
import {
  parseActionResponse,
  parseChangeReportResponse,
  parseRequestResponse,
  parseResultResponse,
  parseTimelineResponse,
} from "./contracts";
import type {
  ChangeReportWorkspaceProjection,
  DynamicReplanningEnvelope,
  ExecutionEventTimelineProjection,
  ReplanActionAcknowledgement,
  ReplanActionRequest,
  ReplanRequestProjection,
  ReplanResultProjection,
  ReplanningQueryDocument,
} from "./types";

export class ReplanningClientError extends Error {
  constructor(
    readonly kind: ClientFailureKind,
    message: string,
    readonly status: number | null,
    readonly correlationId: string | null,
    readonly reason: string | null,
    readonly outcomeUnknown: boolean,
  ) {
    super(message);
    this.name = "ReplanningClientError";
  }
}

export interface DynamicReplanningClient {
  listExecutionEvents(
    query: ReplanningQueryDocument,
  ): Promise<ExecutionEventTimelineProjection>;
  getReplanRequest(query: ReplanningQueryDocument): Promise<ReplanRequestProjection>;
  getReplanResult(query: ReplanningQueryDocument): Promise<ReplanResultProjection>;
  getChangeReport(
    query: ReplanningQueryDocument,
  ): Promise<ChangeReportWorkspaceProjection>;
  executeAttemptAction(
    request: ReplanActionRequest,
  ): Promise<DynamicReplanningEnvelope<ReplanActionAcknowledgement>>;
}

function failureKind(status: number): ClientFailureKind {
  if (status === 401 || status === 403) return "authorization_denied";
  if (status === 409) return "stale";
  if (status === 404 || status === 422) return "contract_error";
  return "server_error";
}

function safeError(value: unknown, fallback: string): {
  message: string;
  reason: string | null;
  correlationId: string | null;
  retryable: boolean | null;
} {
  if (!isJsonObject(value)) {
    return { message: fallback, reason: null, correlationId: null, retryable: null };
  }
  return {
    message: typeof value.message === "string" ? value.message : fallback,
    reason: typeof value.reason === "string" ? value.reason : null,
    correlationId:
      typeof value.correlation_id === "string" ? value.correlation_id : null,
    retryable: typeof value.retryable === "boolean" ? value.retryable : null,
  };
}

function canonicalHeader(value: string, field: string): string {
  if (
    value.length === 0 ||
    value.trim() !== value ||
    /[\u0000-\u001f\u007f]/u.test(value)
  ) {
    throw new ReplanningClientError(
      "contract_error",
      `${field} is not canonical`,
      null,
      null,
      "INVALID_REQUEST",
      false,
    );
  }
  return value;
}

async function sha256Text(value: string): Promise<string> {
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return `sha256:${Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("")}`;
}

async function validateQuery(
  query: ReplanningQueryDocument,
  kind: ReplanningQueryDocument["query_kind"],
  config: RuntimeConfig,
): Promise<void> {
  if (
    query.query_kind !== kind ||
    query.data_plane !== "SIMULATION" ||
    query.environment !== config.environment ||
    query.production_binding !== false
  ) {
    throw new ContractViolation("query", "kind or runtime boundary differs");
  }
  const projection = Object.fromEntries(
    Object.entries(query).filter(([key]) => key !== "query_fingerprint"),
  ) as JsonObject;
  if ((await sha256Fingerprint(projection)) !== query.query_fingerprint) {
    throw new ContractViolation("query.query_fingerprint", "outbound query was altered");
  }
}

export function createDynamicReplanningClient(
  config: RuntimeConfig,
  session: SessionProvider,
  fetcher: typeof fetch = globalThis.fetch,
): DynamicReplanningClient {
  async function headers(accept = "application/json"): Promise<Headers> {
    const result = new Headers({ Accept: accept });
    const token = await session.getAccessToken();
    if (token !== null) {
      canonicalHeader(token, "session credential");
      result.set("Authorization", `Bearer ${token}`);
    }
    return result;
  }

  async function request(
    path: string,
    method: "GET" | "POST",
    correlationId: string,
    body?: JsonObject,
    additionalHeaders: Readonly<Record<string, string>> = {},
  ): Promise<unknown> {
    const requestHeaders = await headers();
    requestHeaders.set("X-Correlation-Id", canonicalHeader(correlationId, "correlation_id"));
    if (body !== undefined) requestHeaders.set("Content-Type", "application/json");
    for (const [name, value] of Object.entries(additionalHeaders)) {
      requestHeaders.set(name, canonicalHeader(value, name));
    }
    let response: Response;
    try {
      response = await fetcher(`${config.apiBaseUrl}${path}`, {
        method,
        headers: requestHeaders,
        body: body === undefined ? undefined : canonicalJson(body),
        cache: "no-store",
        credentials: "omit",
      });
    } catch {
      throw new ReplanningClientError(
        "server_error",
        method === "POST"
          ? "Replan action outcome is unknown"
          : "Dynamic replanning authority is unavailable",
        null,
        correlationId,
        method === "POST" ? "UNKNOWN_OUTCOME" : "SERVICE_UNAVAILABLE",
        method === "POST",
      );
    }
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new ReplanningClientError(
        response.ok ? "contract_error" : failureKind(response.status),
        "Server returned a non-JSON dynamic-replanning response",
        response.status,
        response.headers.get("X-Correlation-Id") ?? correlationId,
        response.ok ? "CONTRACT_REJECTED" : null,
        method === "POST" && response.status >= 500,
      );
    }
    if (!response.ok) {
      const detail = safeError(payload, `Request failed with HTTP ${response.status}`);
      const unknown =
        method === "POST" &&
        (response.status === 503 || detail.reason === "UNKNOWN_OUTCOME") &&
        detail.retryable !== true;
      throw new ReplanningClientError(
        failureKind(response.status),
        detail.message,
        response.status,
        detail.correlationId ?? response.headers.get("X-Correlation-Id") ?? correlationId,
        detail.reason,
        unknown,
      );
    }
    return payload;
  }

  function queryPath(path: string, query: ReplanningQueryDocument): string {
    return `${path}?${new URLSearchParams({ query: canonicalJson(query) })}`;
  }

  async function checked<T>(operation: () => Promise<T>): Promise<T> {
    try {
      return await operation();
    } catch (error) {
      if (error instanceof ReplanningClientError) throw error;
      if (error instanceof ContractViolation || error instanceof TypeError) {
        throw new ReplanningClientError(
          "contract_error",
          error.message,
          200,
          null,
          "CONTRACT_REJECTED",
          false,
        );
      }
      throw new ReplanningClientError(
        "contract_error",
        "Dynamic replanning response failed its consumer contract",
        200,
        null,
        "CONTRACT_REJECTED",
        false,
      );
    }
  }

  return {
    async listExecutionEvents(query) {
      return checked(async () => {
        await validateQuery(query, "EXECUTION_EVENT_STREAM", config);
        return parseTimelineResponse(
          await request(
            queryPath("/execution-events", query),
            "GET",
            query.correlation_id,
          ),
          query,
        );
      });
    },
    async getReplanRequest(query) {
      return checked(async () => {
        await validateQuery(query, "REPLAN_REQUEST", config);
        return parseRequestResponse(
          await request(
            queryPath(`/replan-requests/${encodeURIComponent(String(query.resource_id))}`, query),
            "GET",
            query.correlation_id,
          ),
          query,
        );
      });
    },
    async getReplanResult(query) {
      return checked(async () => {
        await validateQuery(query, "REPLAN_RESULT", config);
        return parseResultResponse(
          await request(
            queryPath(
              `/replan-requests/${encodeURIComponent(String(query.resource_id))}/result`,
              query,
            ),
            "GET",
            query.correlation_id,
          ),
          query,
        );
      });
    },
    async getChangeReport(query) {
      return checked(async () => {
        await validateQuery(query, "CHANGE_REPORT", config);
        return parseChangeReportResponse(
          await request(
            queryPath(`/change-reports/${encodeURIComponent(String(query.resource_id))}`, query),
            "GET",
            query.correlation_id,
          ),
          query,
        );
      });
    },
    async executeAttemptAction(actionRequest) {
      return checked(async () => {
        const { document, idempotencyKey, planningScopeId } = actionRequest;
        if (
          config.dataPlane !== "SIMULATION" ||
          document.data_plane !== "SIMULATION" ||
          document.environment !== config.environment ||
          document.production_binding !== false
        ) {
          throw new ContractViolation("replan_action", "runtime boundary differs");
        }
        const fingerprintProjection = Object.fromEntries(
          Object.entries(document).filter(
            ([key]) => key !== "action_id" && key !== "action_fingerprint",
          ),
        ) as JsonObject;
        if (
          (await sha256Fingerprint(fingerprintProjection)) !== document.action_fingerprint ||
          document.action_id !==
            `replan-action-${document.action_fingerprint.slice("sha256:".length)}` ||
          (await sha256Text(idempotencyKey)) !== document.idempotency_key_reference
        ) {
          throw new ContractViolation("replan_action", "identity or key binding differs");
        }
        const suffix = document.action === "CANCEL" ? "cancel" : "retry";
        const response = await request(
          `/replan-requests/${encodeURIComponent(document.request_id)}/${suffix}`,
          "POST",
          document.correlation_id,
          document,
          {
            "Idempotency-Key": idempotencyKey,
            "X-Planning-Scope-Id": planningScopeId,
          },
        );
        return parseActionResponse(response, document);
      });
    },
  };
}
