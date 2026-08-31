import { sha256Fingerprint } from "../../api/canonical";
import type { RuntimeConfig } from "../../api/runtime";
import type { JsonObject } from "../../api/types";
import type {
  ReplanAttemptAction,
  ReplanAttemptActionDocument,
  ReplanAttemptProjection,
  ReplanActionRequest,
  ReplanningQueryDocument,
  ReplanningQueryKind,
  ReplanningWorkspaceIdentity,
} from "./types";

const fingerprintPattern = /^sha256:[0-9a-f]{64}$/u;
const requestPattern = /^replan-request-[0-9a-f]{64}$/u;
const attemptPattern = /^replan-attempt-[0-9a-f]{64}$/u;
const canonicalIdentityPattern = /^[^\s\u0000-\u001f\u007f]{1,256}$/u;
const semverPattern = /^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$/u;
const sensitiveReasonMarkers = [
  "bearer ",
  "password",
  "postgresql://",
  "redis://",
  "secret",
  "token",
] as const;

function requireSimulationRuntime(config: RuntimeConfig): asserts config is RuntimeConfig & {
  dataPlane: "SIMULATION";
  environment: "DEVELOPMENT" | "TEST" | "BENCHMARK";
} {
  if (
    config.dataPlane !== "SIMULATION" ||
    !["DEVELOPMENT", "TEST", "BENCHMARK"].includes(config.environment)
  ) {
    throw new TypeError(
      "Dynamic replanning is available only in an isolated Simulation runtime",
    );
  }
}

function identity(value: string, field: string, pattern = canonicalIdentityPattern): string {
  const trimmed = value.trim();
  if (trimmed !== value || !pattern.test(trimmed)) {
    throw new TypeError(`${field} is not a canonical P4 identity`);
  }
  return value;
}

function positiveInteger(value: number, field: string): number {
  if (!Number.isInteger(value) || value < 1) {
    throw new TypeError(`${field} must be a positive integer`);
  }
  return value;
}

async function sha256Text(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  const hex = Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  return `sha256:${hex}`;
}

interface QueryFields {
  queryKind: ReplanningQueryKind;
  resourceId: string | null;
  planningScopeId: string;
  authorityId?: string;
  streamId?: string;
  streamVersion?: string;
  fromPosition?: number;
  throughPosition?: number;
  attemptId?: string;
  requestFingerprint?: string;
  reportFingerprint?: string;
  cursor?: string | null;
  correlationId?: string;
}

async function buildQuery(
  config: RuntimeConfig,
  fields: QueryFields,
): Promise<ReplanningQueryDocument> {
  requireSimulationRuntime(config);
  const document: JsonObject = {
    replanning_query_version: "dynamic-replanning-query.v1",
    api_contract_version: "dynamic-replanning-http.v1",
    canonicalization_version: "canonical-json.v1",
    query_kind: fields.queryKind,
    resource_id: fields.resourceId,
    planning_scope_id: identity(fields.planningScopeId, "planning_scope_id"),
    authority_id: fields.authorityId ?? null,
    stream_id: fields.streamId ?? null,
    stream_version: fields.streamVersion ?? null,
    from_position: fields.fromPosition ?? null,
    through_position: fields.throughPosition ?? null,
    attempt_id: fields.attemptId ?? null,
    request_fingerprint: fields.requestFingerprint ?? null,
    report_fingerprint: fields.reportFingerprint ?? null,
    page: { size: 100, cursor: fields.cursor ?? null },
    data_plane: "SIMULATION",
    environment: config.environment,
    production_binding: false,
    correlation_id:
      fields.correlationId ?? `correlation-p4-ui-${globalThis.crypto.randomUUID()}`,
    query_fingerprint: `sha256:${"0".repeat(64)}`,
  };
  document.query_fingerprint = await sha256Fingerprint(
    Object.fromEntries(
      Object.entries(document).filter(([key]) => key !== "query_fingerprint"),
    ) as JsonObject,
  );
  return document as ReplanningQueryDocument;
}

export async function buildTimelineQuery(
  config: RuntimeConfig,
  authority: ReplanningWorkspaceIdentity,
  cursor: string | null = null,
): Promise<ReplanningQueryDocument> {
  const from = positiveInteger(authority.fromPosition, "from_position");
  const through = positiveInteger(authority.throughPosition, "through_position");
  if (from > through) throw new TypeError("event stream position range is reversed");
  identity(authority.authorityId, "authority_id");
  identity(authority.streamId, "stream_id");
  identity(authority.streamVersion, "stream_version", semverPattern);
  return buildQuery(config, {
    queryKind: "EXECUTION_EVENT_STREAM",
    resourceId: null,
    planningScopeId: authority.planningScopeId,
    authorityId: authority.authorityId,
    streamId: authority.streamId,
    streamVersion: authority.streamVersion,
    fromPosition: from,
    throughPosition: through,
    cursor,
  });
}

export async function buildRequestQuery(
  config: RuntimeConfig,
  authority: ReplanningWorkspaceIdentity,
): Promise<ReplanningQueryDocument> {
  identity(authority.requestId, "request_id", requestPattern);
  identity(authority.requestFingerprint, "request_fingerprint", fingerprintPattern);
  return buildQuery(config, {
    queryKind: "REPLAN_REQUEST",
    resourceId: authority.requestId,
    planningScopeId: authority.planningScopeId,
    requestFingerprint: authority.requestFingerprint,
  });
}

export async function buildResultQuery(
  config: RuntimeConfig,
  authority: ReplanningWorkspaceIdentity,
): Promise<ReplanningQueryDocument> {
  identity(authority.requestId, "request_id", requestPattern);
  identity(authority.requestFingerprint, "request_fingerprint", fingerprintPattern);
  identity(authority.attemptId, "attempt_id", attemptPattern);
  return buildQuery(config, {
    queryKind: "REPLAN_RESULT",
    resourceId: authority.requestId,
    planningScopeId: authority.planningScopeId,
    requestFingerprint: authority.requestFingerprint,
    attemptId: authority.attemptId,
  });
}

export async function buildChangeReportQuery(
  config: RuntimeConfig,
  authority: ReplanningWorkspaceIdentity,
  reportId: string,
  reportFingerprint: string,
  cursor: string | null = null,
): Promise<ReplanningQueryDocument> {
  identity(reportId, "report_id", /^change-report-[0-9a-f]{64}$/u);
  identity(reportFingerprint, "report_fingerprint", fingerprintPattern);
  identity(authority.attemptId, "attempt_id", attemptPattern);
  return buildQuery(config, {
    queryKind: "CHANGE_REPORT",
    resourceId: reportId,
    planningScopeId: authority.planningScopeId,
    requestFingerprint: authority.requestFingerprint,
    attemptId: authority.attemptId,
    reportFingerprint,
    cursor,
  });
}

function sanitizedReason(value: string): string {
  const reason = value.trim();
  if (
    reason !== value ||
    reason.length < 1 ||
    reason.length > 512 ||
    /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(reason) ||
    sensitiveReasonMarkers.some((marker) => reason.toLowerCase().includes(marker))
  ) {
    throw new TypeError("replan action reason must be bounded sanitized text");
  }
  return reason;
}

export async function buildReplanAttemptAction(
  config: RuntimeConfig,
  input: {
    action: ReplanAttemptAction;
    requestId: string;
    requestFingerprint: string;
    attempt: ReplanAttemptProjection;
    planningScopeId: string;
    reason: string;
    idempotencyKey?: string;
    correlationId?: string;
  },
): Promise<ReplanActionRequest> {
  requireSimulationRuntime(config);
  if (!input.attempt.allowed_actions.includes(input.action)) {
    throw new TypeError("server authority did not allow this replan action");
  }
  const idempotencyKey =
    input.idempotencyKey ??
    `p4-replan-${input.action.toLowerCase()}-${globalThis.crypto.randomUUID()}`;
  identity(idempotencyKey, "Idempotency-Key");
  if (idempotencyKey.length < 16 || idempotencyKey.length > 128) {
    throw new TypeError("Idempotency-Key is outside the HTTP contract bounds");
  }
  const body: JsonObject = {
    replan_action_version: "replan-attempt-action-http.v1",
    api_contract_version: "dynamic-replanning-http.v1",
    canonicalization_version: "canonical-json.v1",
    action: input.action,
    request_id: identity(input.requestId, "request_id", requestPattern),
    request_fingerprint: identity(
      input.requestFingerprint,
      "request_fingerprint",
      fingerprintPattern,
    ),
    expected_attempt_id: identity(
      input.attempt.attempt_id,
      "expected_attempt_id",
      attemptPattern,
    ),
    expected_attempt_number: positiveInteger(
      input.attempt.attempt_number,
      "expected_attempt_number",
    ),
    expected_planning_run_state: input.attempt.state,
    reason: sanitizedReason(input.reason),
    data_plane: "SIMULATION",
    environment: config.environment,
    production_binding: false,
    correlation_id:
      input.correlationId ??
      `correlation-p4-action-${globalThis.crypto.randomUUID()}`,
    idempotency_key_reference: await sha256Text(idempotencyKey),
  };
  const actionFingerprint = await sha256Fingerprint(body);
  const document = {
    ...body,
    action_id: `replan-action-${actionFingerprint.slice("sha256:".length)}`,
    action_fingerprint: actionFingerprint,
  } as ReplanAttemptActionDocument;
  return {
    document,
    idempotencyKey,
    planningScopeId: identity(input.planningScopeId, "planning_scope_id"),
  };
}
