import { canonicalJson } from "../api/canonical";
import type { RuntimeConfig } from "../api/runtime";
import type { SessionProvider } from "../api/session";
import type { JsonObject } from "../api/types";
import {
  HeadlessContractError,
  parseCanonicalIngressRequestText,
  parseCanonicalIngressResult,
  parseHeadlessError,
  parsePlanningRun,
  sameScope,
} from "./contracts";
import type {
  CanonicalIngressResult,
  EffectiveScope,
  HeadlessClientFailureKind,
  PlanningRun,
  PlanningRunCancelAction,
  PlanningRunRetryAction,
} from "./types";

export class HeadlessClientError extends Error {
  constructor(
    readonly kind: HeadlessClientFailureKind,
    message: string,
    readonly status: number | null,
    readonly correlationId: string | null,
    readonly code: string | null,
  ) {
    super(message);
    this.name = "HeadlessClientError";
  }
}

export interface HeadlessPlanningClient {
  create(canonicalRequest: string): Promise<CanonicalIngressResult>;
  status(
    planningRunId: string,
    scope: EffectiveScope,
    correlationId: string,
  ): Promise<PlanningRun>;
  result(
    planningRunId: string,
    scope: EffectiveScope,
    correlationId: string,
  ): Promise<PlanningRun>;
  cancel(
    run: PlanningRun,
    reason: string,
    idempotencyKey: string,
    correlationId: string,
  ): Promise<PlanningRun>;
  retry(
    run: PlanningRun,
    reason: string,
    idempotencyKey: string,
    correlationId: string,
  ): Promise<PlanningRun>;
}

function safeIdentity(value: string, label: string): string {
  if (
    value.length === 0 ||
    value.trim() !== value ||
    /[\s\u0000-\u001f\u007f]/u.test(value)
  ) {
    throw new HeadlessClientError(
      "contract_error",
      `${label} is invalid`,
      null,
      null,
      "CONTRACT_VIOLATION",
    );
  }
  return value;
}

function segment(value: string): string {
  return encodeURIComponent(safeIdentity(value, "PlanningRun identity"));
}

function kindForStatus(status: number): HeadlessClientFailureKind {
  if (status === 401) return "authentication_required";
  if (status === 403) return "authorization_denied";
  if (status === 409) return "state_conflict";
  if ([400, 404, 413, 415, 422].includes(status)) return "contract_error";
  if (status === 503) return "unavailable";
  return "server_error";
}

function failureDetails(
  value: unknown,
  status: number,
  headerCorrelation: string | null,
): { message: string; correlation: string | null; code: string | null } {
  try {
    const error = parseHeadlessError(value);
    return {
      message: error.message,
      correlation: error.correlation_id,
      code: error.code,
    };
  } catch (error) {
    if (!(error instanceof HeadlessContractError)) throw error;
  }
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    const source = value as Record<string, unknown>;
    if (source.canonical_ingress_result_version === "canonical-ingress-result.v1") {
      try {
        const result = parseCanonicalIngressResult(value);
        if (result.rejection !== null) {
          return {
            message: result.rejection.message,
            correlation: result.rejection.correlation_id,
            code: result.rejection.code,
          };
        }
      } catch (error) {
        if (!(error instanceof HeadlessContractError)) throw error;
      }
    }
    const message =
      typeof source.message === "string"
        ? source.message
        : `Headless request failed with HTTP ${status}`;
    const correlation =
      typeof source.correlation_id === "string"
        ? source.correlation_id
        : headerCorrelation;
    const product =
      source.product_error !== null && typeof source.product_error === "object"
        ? (source.product_error as Record<string, unknown>)
        : null;
    const control =
      source.workspace_control_error !== null &&
      typeof source.workspace_control_error === "object"
        ? (source.workspace_control_error as Record<string, unknown>)
        : null;
    const code =
      typeof product?.code === "string"
        ? product.code
        : typeof control?.reason === "string"
          ? control.reason
          : null;
    return { message, correlation, code };
  }
  return {
    message: `Headless request failed with HTTP ${status}`,
    correlation: headerCorrelation,
    code: null,
  };
}

function contractFailure(error: HeadlessContractError): HeadlessClientError {
  return new HeadlessClientError(
    error.code === "VERSION_MISMATCH" ? "version_error" : "contract_error",
    error.message,
    null,
    null,
    error.code,
  );
}

export function createHeadlessPlanningClient(
  config: RuntimeConfig,
  session: SessionProvider,
  fetcher: typeof fetch = globalThis.fetch,
): HeadlessPlanningClient {
  async function headers(scope?: EffectiveScope): Promise<Headers> {
    const result = new Headers({ Accept: "application/json" });
    const token = await session.getAccessToken();
    if (token !== null) {
      safeIdentity(token, "Session credential");
      result.set("Authorization", `Bearer ${token}`);
    }
    if (scope !== undefined) {
      result.set("X-APS-Tenant-Id", safeIdentity(scope.tenant_id, "Tenant identity"));
      result.set("X-APS-Factory-Id", safeIdentity(scope.factory_id, "Factory identity"));
      result.set(
        "X-APS-Planning-Scope-Id",
        safeIdentity(scope.planning_scope_id, "Planning scope identity"),
      );
    }
    return result;
  }

  async function request(
    path: string,
    method: "GET" | "POST",
    options: {
      body?: string;
      scope?: EffectiveScope;
      idempotencyKey?: string;
      correlationId: string;
    },
  ): Promise<{ payload: unknown; response: Response }> {
    const requestHeaders = await headers(options.scope);
    requestHeaders.set(
      "X-Correlation-Id",
      safeIdentity(options.correlationId, "Correlation identity"),
    );
    if (options.body !== undefined) {
      requestHeaders.set("Content-Type", "application/json; charset=utf-8");
    }
    if (options.idempotencyKey !== undefined) {
      requestHeaders.set(
        "Idempotency-Key",
        safeIdentity(options.idempotencyKey, "Idempotency key"),
      );
    }
    let response: Response;
    try {
      response = await fetcher(`${config.apiBaseUrl}${path}`, {
        method,
        headers: requestHeaders,
        body: options.body,
        cache: "no-store",
        credentials: "omit",
      });
    } catch {
      throw new HeadlessClientError(
        method === "POST" ? "outcome_unknown" : "unavailable",
        method === "POST"
          ? "The command outcome is unknown; read server authority before retrying"
          : "The Headless Runtime is unavailable",
        null,
        options.correlationId,
        null,
      );
    }
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new HeadlessClientError(
        response.ok ? "contract_error" : kindForStatus(response.status),
        "The Runtime returned a non-JSON response",
        response.status,
        response.headers.get("X-Correlation-Id"),
        "CONTRACT_VIOLATION",
      );
    }
    if (!response.ok) {
      const detail = failureDetails(
        payload,
        response.status,
        response.headers.get("X-Correlation-Id"),
      );
      throw new HeadlessClientError(
        kindForStatus(response.status),
        detail.message,
        response.status,
        detail.correlation,
        detail.code,
      );
    }
    if (!response.headers.get("Cache-Control")?.toLowerCase().includes("no-store")) {
      throw new HeadlessClientError(
        "contract_error",
        "The Runtime response omitted Cache-Control: no-store",
        response.status,
        response.headers.get("X-Correlation-Id"),
        "CONTRACT_VIOLATION",
      );
    }
    return { payload, response };
  }

  async function readRun(
    operation: "status" | "result",
    planningRunId: string,
    scope: EffectiveScope,
    correlationId: string,
  ): Promise<PlanningRun> {
    const { payload, response } = await request(
      `/planning-runs/${segment(planningRunId)}/${operation}`,
      "GET",
      { correlationId, scope },
    );
    let run: PlanningRun;
    try {
      run = parsePlanningRun(payload);
    } catch (error) {
      if (error instanceof HeadlessContractError) throw contractFailure(error);
      throw error;
    }
    const responseCorrelation = response.headers.get("X-Correlation-Id");
    if (
      run.planning_run_id !== planningRunId ||
      !sameScope(run.effective_scope, scope) ||
      responseCorrelation !== correlationId
    ) {
      throw new HeadlessClientError(
        "contract_error",
        "PlanningRun response is not bound to the requested identity and scope",
        response.status,
        responseCorrelation,
        "CONTRACT_VIOLATION",
      );
    }
    return run;
  }

  async function action(
    operation: "cancel" | "retry",
    run: PlanningRun,
    body: PlanningRunCancelAction | PlanningRunRetryAction,
    idempotencyKey: string,
    correlationId: string,
  ): Promise<PlanningRun> {
    const { payload, response } = await request(
      `/planning-runs/${segment(run.planning_run_id)}/${operation}`,
      "POST",
      {
        body: canonicalJson(body as unknown as JsonObject),
        correlationId,
        idempotencyKey,
        scope: run.effective_scope,
      },
    );
    let result: PlanningRun;
    try {
      result = parsePlanningRun(payload);
    } catch (error) {
      if (error instanceof HeadlessContractError) throw contractFailure(error);
      throw error;
    }
    if (
      result.planning_run_id !== run.planning_run_id ||
      !sameScope(result.effective_scope, run.effective_scope) ||
      response.headers.get("X-Correlation-Id") !== correlationId
    ) {
      throw new HeadlessClientError(
        "contract_error",
        "PlanningRun action response changed identity or scope",
        response.status,
        response.headers.get("X-Correlation-Id"),
        "CONTRACT_VIOLATION",
      );
    }
    return result;
  }

  return {
    async create(canonicalRequest: string): Promise<CanonicalIngressResult> {
      let parsed;
      try {
        parsed = parseCanonicalIngressRequestText(canonicalRequest);
      } catch (error) {
        if (error instanceof HeadlessContractError) throw contractFailure(error);
        throw error;
      }
      if (
        parsed.requestedScope.data_plane !== config.dataPlane ||
        parsed.requestedScope.environment !== config.environment
      ) {
        throw new HeadlessClientError(
          "contract_error",
          "Canonical request scope does not match the configured Runtime",
          null,
          parsed.correlationId,
          "DATA_PLANE_MISMATCH",
        );
      }
      const { payload, response } = await request("/planning-runs", "POST", {
        body: parsed.raw,
        correlationId: parsed.correlationId,
        idempotencyKey: parsed.idempotencyKey,
      });
      try {
        const result = parseCanonicalIngressResult(payload, parsed);
        if (response.headers.get("X-Correlation-Id") !== result.correlation_id) {
          throw new HeadlessContractError(
            "CONTRACT_VIOLATION",
            "/headers/X-Correlation-Id",
            "response correlation header and body disagree",
          );
        }
        return result;
      } catch (error) {
        if (error instanceof HeadlessContractError) throw contractFailure(error);
        throw error;
      }
    },
    status: (planningRunId, scope, correlationId) =>
      readRun("status", planningRunId, scope, correlationId),
    result: (planningRunId, scope, correlationId) =>
      readRun("result", planningRunId, scope, correlationId),
    cancel(run, reason, idempotencyKey, correlationId) {
      if (!run.allowed_actions.includes("CANCEL")) {
        throw new HeadlessClientError(
          "state_conflict",
          "The server did not expose CANCEL for this PlanningRun",
          null,
          correlationId,
          "INVALID_STATE_TRANSITION",
        );
      }
      return action(
        "cancel",
        run,
        {
          action_version: "planning-run-cancel-action.v1",
          expected_revision: run.revision,
          expected_state: run.state,
          expected_run_fingerprint: run.run_fingerprint,
          reason,
        },
        idempotencyKey,
        correlationId,
      );
    },
    retry(run, reason, idempotencyKey, correlationId) {
      if (run.attempt === null) {
        throw new HeadlessClientError(
          "state_conflict",
          "Retry requires an exact failed attempt reference from server authority",
          null,
          correlationId,
          "ATTEMPT_NOT_RETRYABLE",
        );
      }
      return action(
        "retry",
        run,
        {
          action_version: "planning-run-retry-action.v1",
          expected_revision: run.revision,
          expected_state: run.state,
          expected_run_fingerprint: run.run_fingerprint,
          failed_attempt_id: run.attempt.attempt_id,
          failed_attempt_number: run.attempt.attempt_number,
          reason,
        },
        idempotencyKey,
        correlationId,
      );
    },
  };
}
