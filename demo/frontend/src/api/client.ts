import {
  DemoContractError,
  parseActivationResult,
  parseBootstrap,
  parseComparisonView,
  parseFactoryView,
  parseJob,
  parseJobAccepted,
  parseScheduleView,
  parseScheduleSummary,
  parseSession,
} from "./contracts";
import type {
  BaselineActivationRequest,
  BaselineActivationResult,
  ComparisonQueryInput,
  DemoBootstrap,
  DemoComparisonView,
  DemoFactoryView,
  DemoJob,
  DemoScheduleView,
  DemoScheduleSummary,
  JobAccepted,
  ScheduleQueryInput,
  UrgentOrderCommand,
} from "./types";

const API_PREFIX = "/api/demo/v1";

export class DemoClientError extends Error {
  constructor(
    readonly code: string,
    readonly field: string,
    readonly correlationId: string | null,
    readonly status: number | null,
  ) {
    super("Demo API request failed");
    this.name = "DemoClientError";
  }
}

export interface DemoApi {
  establishSession(): Promise<void>;
  bootstrap(): Promise<DemoBootstrap>;
  getFactory(): Promise<DemoFactoryView>;
  getJob(jobId: string): Promise<DemoJob>;
  getScheduleSummary(versionId: string): Promise<DemoScheduleSummary>;
  getSchedulePage(
    versionId: string,
    query?: ScheduleQueryInput,
  ): Promise<DemoScheduleView>;
  reset(profile: "smoke" | "showcase", idempotencyKey: string): Promise<JobAccepted>;
  createInitialPlan(runId: string, idempotencyKey: string): Promise<JobAccepted>;
  activateBaseline(
    request: BaselineActivationRequest,
    idempotencyKey: string,
  ): Promise<BaselineActivationResult>;
  submitUrgentOrder(
    request: UrgentOrderCommand,
    idempotencyKey: string,
  ): Promise<JobAccepted>;
  getComparison(
    requestId: string,
    query?: ComparisonQueryInput,
  ): Promise<DemoComparisonView>;
}

type Parser<T> = (value: unknown) => T;

const SCHEDULE_PAGE_LIMIT = 160;
const COMPARISON_PAGE_LIMIT = 120;

function sortedUnique(values: readonly string[] | undefined): readonly string[] {
  return [...new Set((values ?? []).filter((value) => value.length > 0))].sort();
}

export function buildScheduleQuery(query: ScheduleQueryInput = {}): string {
  const offset = query.offset ?? 0;
  const limit = query.limit ?? SCHEDULE_PAGE_LIMIT;
  if (
    !Number.isInteger(offset) ||
    offset < 0 ||
    !Number.isInteger(limit) ||
    limit < 1 ||
    limit > 200
  ) {
    throw new DemoContractError("schedule.query.pagination");
  }
  if (
    query.start_at_utc !== undefined &&
    query.start_at_utc !== null &&
    (!query.start_at_utc.endsWith("Z") || Number.isNaN(Date.parse(query.start_at_utc)))
  ) {
    throw new DemoContractError("schedule.query.start_at_utc");
  }
  if (
    query.end_at_utc !== undefined &&
    query.end_at_utc !== null &&
    (!query.end_at_utc.endsWith("Z") || Number.isNaN(Date.parse(query.end_at_utc)))
  ) {
    throw new DemoContractError("schedule.query.end_at_utc");
  }
  if (
    query.start_at_utc &&
    query.end_at_utc &&
    Date.parse(query.end_at_utc) <= Date.parse(query.start_at_utc)
  ) {
    throw new DemoContractError("schedule.query.range");
  }
  const params = new URLSearchParams();
  for (const value of sortedUnique(query.resource_ids)) {
    params.append("resource_id", value);
  }
  for (const value of sortedUnique(query.workshop_ids)) {
    params.append("workshop_id", value);
  }
  for (const value of sortedUnique(query.demand_order_ids)) {
    params.append("demand_order_id", value);
  }
  for (const value of sortedUnique(query.states)) params.append("state", value);
  if (query.start_at_utc) params.set("start_at_utc", query.start_at_utc);
  if (query.end_at_utc) params.set("end_at_utc", query.end_at_utc);
  params.set("sort", query.sort ?? "START_ASC");
  params.set("offset", String(offset));
  params.set("limit", String(limit));
  return params.toString();
}

export function buildComparisonQuery(query: ComparisonQueryInput = {}): string {
  const offset = query.offset ?? 0;
  const limit = query.limit ?? COMPARISON_PAGE_LIMIT;
  if (
    !Number.isInteger(offset) ||
    offset < 0 ||
    !Number.isInteger(limit) ||
    limit < 1 ||
    limit > 200
  ) {
    throw new DemoContractError("comparison.query.pagination");
  }
  for (const [value, field] of [
    [query.start_at_utc, "start_at_utc"],
    [query.end_at_utc, "end_at_utc"],
  ] as const) {
    if (
      value !== undefined &&
      value !== null &&
      (!value.endsWith("Z") || Number.isNaN(Date.parse(value)))
    ) {
      throw new DemoContractError(`comparison.query.${field}`);
    }
  }
  if (
    query.start_at_utc &&
    query.end_at_utc &&
    Date.parse(query.end_at_utc) <= Date.parse(query.start_at_utc)
  ) {
    throw new DemoContractError("comparison.query.range");
  }
  const allowed = new Set([
    "UNCHANGED",
    "CHANGED",
    "ADDED",
    "REMOVED_BY_FACT",
  ]);
  const classifications = sortedUnique(
    query.classifications ?? ["ADDED", "CHANGED"],
  );
  if (
    classifications.length === 0 ||
    classifications.some((value) => !allowed.has(value))
  ) {
    throw new DemoContractError("comparison.query.classifications");
  }
  const params = new URLSearchParams();
  for (const value of classifications) params.append("classification", value);
  for (const value of sortedUnique(query.resource_ids)) {
    params.append("resource_id", value);
  }
  for (const value of sortedUnique(query.workshop_ids)) {
    params.append("workshop_id", value);
  }
  for (const value of sortedUnique(query.demand_order_ids)) {
    params.append("demand_order_id", value);
  }
  if (query.start_at_utc) params.set("start_at_utc", query.start_at_utc);
  if (query.end_at_utc) params.set("end_at_utc", query.end_at_utc);
  params.set("sort", query.sort ?? "SHIFT_DESC");
  params.set("offset", String(offset));
  params.set("limit", String(limit));
  return params.toString();
}

function correlationId(): string {
  const suffix = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
  return `correlation-demo-ui-${suffix}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function sanitizedError(
  value: unknown,
  response: Response,
): DemoClientError {
  const document = isRecord(value) ? value : {};
  const code =
    typeof document.code === "string" && /^[A-Z][A-Z0-9_]{1,63}$/.test(document.code)
      ? document.code
      : "REQUEST_FAILED";
  const field =
    typeof document.field === "string" && document.field.length <= 128
      ? document.field
      : "request";
  const bodyCorrelation =
    typeof document.correlation_id === "string" &&
    document.correlation_id.length <= 256
      ? document.correlation_id
      : null;
  return new DemoClientError(
    code,
    field,
    response.headers.get("X-Correlation-Id") ?? bodyCorrelation,
    response.status,
  );
}

async function requestJson<T>(
  path: string,
  parser: Parser<T>,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("X-Correlation-Id", correlationId());
  if (init.body !== undefined) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}${path}`, {
      ...init,
      headers,
      credentials: "same-origin",
    });
  } catch {
    throw new DemoClientError("NETWORK_ERROR", "network", null, null);
  }

  let payload: unknown;
  try {
    const body = await response.text();
    payload = body.length === 0 ? null : (JSON.parse(body) as unknown);
  } catch {
    throw new DemoContractError("response.json");
  }
  if (!response.ok) throw sanitizedError(payload, response);
  return parser(payload);
}

export function createDemoApi(): DemoApi {
  return {
    async establishSession() {
      await requestJson("/session", (value) => {
        parseSession(value);
        return undefined;
      }, { method: "POST" });
    },

    bootstrap() {
      return requestJson("/bootstrap", parseBootstrap);
    },

    getFactory() {
      return requestJson("/factory", parseFactoryView);
    },

    getJob(jobId) {
      return requestJson(`/jobs/${encodeURIComponent(jobId)}`, parseJob);
    },

    getScheduleSummary(versionId) {
      return requestJson(
        `/versions/${encodeURIComponent(versionId)}?limit=1`,
        parseScheduleSummary,
      );
    },

    getSchedulePage(versionId, query = {}) {
      return requestJson(
        `/versions/${encodeURIComponent(versionId)}?${buildScheduleQuery(query)}`,
        parseScheduleView,
      );
    },

    reset(profile, idempotencyKey) {
      return requestJson("/resets", parseJobAccepted, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({
          request_version: "cnc-demo-reset-request.v1",
          profile_name: profile,
        }),
      });
    },

    createInitialPlan(runId, idempotencyKey) {
      return requestJson("/initial-plans", parseJobAccepted, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({
          request_version: "cnc-demo-initial-plan-request.v1",
          expected_run_id: runId,
        }),
      });
    },

    activateBaseline(request, idempotencyKey) {
      return requestJson("/baseline-activations", parseActivationResult, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify(request),
      });
    },

    submitUrgentOrder(request, idempotencyKey) {
      return requestJson("/urgent-orders", parseJobAccepted, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify(request),
      });
    },

    getComparison(requestId, query = {}) {
      return requestJson(
        `/comparisons/${encodeURIComponent(requestId)}?${buildComparisonQuery(query)}`,
        parseComparisonView,
      );
    },
  };
}
