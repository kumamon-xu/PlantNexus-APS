import { workspaceQueryFingerprint } from "./canonical";
import {
  scheduleStates,
  type ArtifactReference,
  type JsonObject,
  type JsonValue,
  type ScheduleLineage,
  type ScheduleState,
  type ScheduleVersion,
  type VersionReference,
  type WorkspaceHttpResponse,
  type WorkspacePayloadItem,
  type WorkspaceQueryDocument,
  type WorkspaceQueryResultBody,
  type WorkspaceView,
} from "./types";

const fingerprintPattern = /^sha256:[0-9a-f]{64}$/;
const scheduleStateSet = new Set<string>(scheduleStates);

export class ContractViolation extends Error {
  constructor(
    readonly field: string,
    message: string,
  ) {
    super(`${field}: ${message}`);
    this.name = "ContractViolation";
  }
}

export function isJsonObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function object(value: unknown, field: string): JsonObject {
  if (!isJsonObject(value)) {
    throw new ContractViolation(field, "must be an object");
  }
  return value;
}

function string(value: unknown, field: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new ContractViolation(field, "must be a non-empty string");
  }
  return value;
}

function literal<T extends string>(
  value: unknown,
  expected: T,
  field: string,
): T {
  if (value !== expected) {
    throw new ContractViolation(field, `must equal ${expected}`);
  }
  return expected;
}

function fingerprint(value: unknown, field: string): string {
  const result = string(value, field);
  if (!fingerprintPattern.test(result)) {
    throw new ContractViolation(field, "must be a sha256 fingerprint");
  }
  return result;
}

function nullableFingerprint(value: unknown, field: string): string | null {
  return value === null ? null : fingerprint(value, field);
}

function utc(value: unknown, field: string): string {
  const result = string(value, field);
  if (!result.endsWith("Z") || Number.isNaN(Date.parse(result))) {
    throw new ContractViolation(field, "must be an explicit UTC instant");
  }
  return result;
}

function state(value: unknown, field: string): ScheduleState {
  const result = string(value, field);
  if (!scheduleStateSet.has(result)) {
    throw new ContractViolation(field, `unknown ScheduleVersion state: ${result}`);
  }
  return result as ScheduleState;
}

function artifact(value: unknown, field: string): ArtifactReference {
  const result = object(value, field);
  return {
    ...result,
    document_version: string(result.document_version, `${field}.document_version`),
    artifact_id: string(result.artifact_id, `${field}.artifact_id`),
    fingerprint: fingerprint(result.fingerprint, `${field}.fingerprint`),
  } as ArtifactReference;
}

function versionReference(value: unknown, field: string): VersionReference {
  const result = object(value, field);
  return {
    ...result,
    schedule_version_id: string(
      result.schedule_version_id,
      `${field}.schedule_version_id`,
    ),
    state: state(result.state, `${field}.state`),
    content_fingerprint: fingerprint(
      result.content_fingerprint,
      `${field}.content_fingerprint`,
    ),
  } as VersionReference;
}

function lineage(value: unknown, field: string): ScheduleLineage {
  const result = object(value, field);
  return {
    ...result,
    planning_run_id: string(result.planning_run_id, `${field}.planning_run_id`),
    snapshot: artifact(result.snapshot, `${field}.snapshot`),
    problem: artifact(result.problem, `${field}.problem`),
    planning_solution: artifact(
      result.planning_solution,
      `${field}.planning_solution`,
    ),
    validation_report: artifact(
      result.validation_report,
      `${field}.validation_report`,
    ),
    kpi: artifact(result.kpi, `${field}.kpi`),
    solver_report: artifact(result.solver_report, `${field}.solver_report`),
    code_commit: string(result.code_commit, `${field}.code_commit`),
  } as ScheduleLineage;
}

export function parseScheduleVersion(value: unknown): ScheduleVersion {
  const envelope = object(value, "response");
  const raw =
    envelope.schedule_version_version === "schedule-version.v1"
      ? envelope
      : object(envelope.schedule_version, "response.schedule_version");
  const revision = raw.revision;
  if (!Number.isInteger(revision) || (revision as number) < 1) {
    throw new ContractViolation("schedule_version.revision", "must be a positive integer");
  }
  if (!Array.isArray(raw.allowed_actions)) {
    throw new ContractViolation(
      "schedule_version.allowed_actions",
      "must be an array",
    );
  }
  const parent =
    raw.parent_schedule_version === null
      ? null
      : versionReference(
          raw.parent_schedule_version,
          "schedule_version.parent_schedule_version",
        );
  const plane = literalPlane(raw.data_plane, "schedule_version.data_plane");
  const environment = literalEnvironment(
    raw.environment,
    "schedule_version.environment",
  );
  if (typeof raw.synthetic !== "boolean") {
    throw new ContractViolation("schedule_version.synthetic", "must be a boolean");
  }
  return {
    ...raw,
    schedule_version_version: literal(
      raw.schedule_version_version,
      "schedule-version.v1",
      "schedule_version.schedule_version_version",
    ),
    schema_set_version: literal(
      raw.schema_set_version,
      "2.6.0",
      "schedule_version.schema_set_version",
    ),
    canonicalization_version: literal(
      raw.canonicalization_version,
      "canonical-json.v1",
      "schedule_version.canonicalization_version",
    ),
    schedule_version_id: string(
      raw.schedule_version_id,
      "schedule_version.schedule_version_id",
    ),
    revision: revision as number,
    state: state(raw.state, "schedule_version.state"),
    data_plane: plane,
    environment,
    synthetic: raw.synthetic,
    parent_schedule_version: parent,
    lineage: lineage(raw.lineage, "schedule_version.lineage"),
    content_fingerprint: fingerprint(
      raw.content_fingerprint,
      "schedule_version.content_fingerprint",
    ),
    validation: object(raw.validation, "schedule_version.validation"),
    allowed_actions: raw.allowed_actions as JsonValue[],
    created_at_utc: utc(raw.created_at_utc, "schedule_version.created_at_utc"),
    created_by_actor_ref: string(
      raw.created_by_actor_ref,
      "schedule_version.created_by_actor_ref",
    ),
  } as ScheduleVersion;
}

function literalPlane(value: unknown, field: string): "SIMULATION" | "PRODUCTION" {
  if (value !== "SIMULATION" && value !== "PRODUCTION") {
    throw new ContractViolation(field, "must be SIMULATION or PRODUCTION");
  }
  return value;
}

function literalEnvironment(
  value: unknown,
  field: string,
): "DEVELOPMENT" | "TEST" | "BENCHMARK" | "PRODUCTION" {
  if (
    value !== "DEVELOPMENT" &&
    value !== "TEST" &&
    value !== "BENCHMARK" &&
    value !== "PRODUCTION"
  ) {
    throw new ContractViolation(field, "is not a supported environment");
  }
  return value;
}

function resultBody(value: unknown): WorkspaceQueryResultBody {
  const result = object(value, "document.result");
  if (typeof result.found !== "boolean") {
    throw new ContractViolation("document.result.found", "must be a boolean");
  }
  if (!Array.isArray(result.items)) {
    throw new ContractViolation("document.result.items", "must be an array");
  }
  if (!Number.isInteger(result.observed_count) || (result.observed_count as number) < 0) {
    throw new ContractViolation(
      "document.result.observed_count",
      "must be a non-negative integer",
    );
  }
  if (!Array.isArray(result.allowed_actions)) {
    throw new ContractViolation("document.result.allowed_actions", "must be an array");
  }
  const nextCursor = result.next_cursor;
  if (nextCursor !== null && typeof nextCursor !== "string") {
    throw new ContractViolation("document.result.next_cursor", "must be null or a string");
  }
  const authority =
    result.authoritative_schedule_version === null
      ? null
      : versionReference(
          result.authoritative_schedule_version,
          "document.result.authoritative_schedule_version",
        );
  const parsedLineage =
    result.lineage === null ? null : lineage(result.lineage, "document.result.lineage");
  return {
    ...result,
    result_version: literal(
      result.result_version,
      "workspace-query-result.v1",
      "document.result.result_version",
    ),
    found: result.found,
    authoritative_schedule_version: authority,
    lineage: parsedLineage,
    items: result.items.map((item, index) =>
      object(item, `document.result.items[${index}]`),
    ),
    next_cursor: nextCursor,
    observed_count: result.observed_count as number,
    allowed_actions: result.allowed_actions as JsonValue[],
    freshness: string(result.freshness, "document.result.freshness"),
    generated_at_utc: utc(
      result.generated_at_utc,
      "document.result.generated_at_utc",
    ),
  } as WorkspaceQueryResultBody;
}

function workspaceDocument(
  value: unknown,
  expectedView: WorkspaceView,
): WorkspaceQueryDocument {
  const document = object(value, "document");
  if (document.view !== expectedView) {
    throw new ContractViolation(
      "document.view",
      `expected ${expectedView}, received ${String(document.view)}`,
    );
  }
  return {
    ...document,
    workspace_query_version: literal(
      document.workspace_query_version,
      "workspace-query.v1",
      "document.workspace_query_version",
    ),
    schema_set_version: literal(
      document.schema_set_version,
      "2.6.0",
      "document.schema_set_version",
    ),
    canonicalization_version: literal(
      document.canonicalization_version,
      "canonical-json.v1",
      "document.canonicalization_version",
    ),
    direction: literal(document.direction, "RESULT", "document.direction"),
    query_kind: literal(
      document.query_kind,
      "WORKSPACE_VIEW",
      "document.query_kind",
    ),
    data_plane: literalPlane(document.data_plane, "document.data_plane"),
    environment: literalEnvironment(document.environment, "document.environment"),
    synthetic: requireBoolean(document.synthetic, "document.synthetic"),
    resource: object(document.resource, "document.resource"),
    view: expectedView,
    schedule_version_precondition:
      document.schedule_version_precondition === null
        ? null
        : versionReference(
            document.schedule_version_precondition,
            "document.schedule_version_precondition",
          ),
    sort: requireObjectArray(document.sort, "document.sort"),
    filters: object(document.filters, "document.filters"),
    page: object(document.page, "document.page"),
    query_fingerprint: fingerprint(
      document.query_fingerprint,
      "document.query_fingerprint",
    ),
    correlation_id: string(document.correlation_id, "document.correlation_id"),
    result: resultBody(document.result),
  } as WorkspaceQueryDocument;
}

function requireBoolean(value: unknown, field: string): boolean {
  if (typeof value !== "boolean") {
    throw new ContractViolation(field, "must be a boolean");
  }
  return value;
}

function requireObjectArray(value: unknown, field: string): JsonObject[] {
  if (!Array.isArray(value)) {
    throw new ContractViolation(field, "must be an array");
  }
  return value.map((item, index) => object(item, `${field}[${index}]`));
}

function payloadItem(value: unknown, index: number): WorkspacePayloadItem {
  const item = object(value, `items[${index}]`);
  return {
    ...item,
    item_id: string(item.item_id, `items[${index}].item_id`),
    item_type: string(item.item_type, `items[${index}].item_type`),
    payload: object(item.payload, `items[${index}].payload`),
    payload_fingerprint: fingerprint(
      item.payload_fingerprint,
      `items[${index}].payload_fingerprint`,
    ),
  } as WorkspacePayloadItem;
}

export async function parseWorkspaceResponse(
  value: unknown,
  expectedView: WorkspaceView,
): Promise<WorkspaceHttpResponse> {
  const response = object(value, "response");
  if (!Array.isArray(response.items)) {
    throw new ContractViolation("response.items", "must be an array");
  }
  const document = workspaceDocument(response.document, expectedView);
  const items = response.items.map(payloadItem);
  const result = document.result;
  if (result === null) {
    throw new ContractViolation("document.result", "must be present for a RESULT carrier");
  }
  if (result.items.length !== items.length) {
    throw new ContractViolation(
      "response.items",
      "payload page length differs from carrier references",
    );
  }
  for (let index = 0; index < items.length; index += 1) {
    const item = items[index];
    const reference = result.items[index];
    if (item === undefined || reference === undefined) {
      throw new ContractViolation("response.items", "carrier alignment is incomplete");
    }
    for (const field of ["item_id", "item_type", "payload_fingerprint"] as const) {
      if (reference[field] !== item[field]) {
        throw new ContractViolation(
          `document.result.items[${index}].${field}`,
          "does not match the complete payload item",
        );
      }
    }
  }
  const calculatedQuery = await workspaceQueryFingerprint(document);
  if (calculatedQuery !== document.query_fingerprint) {
    throw new ContractViolation(
      "document.query_fingerprint",
      "does not match the canonical query projection",
    );
  }
  if (!result.found && (items.length > 0 || response.collection_fingerprint !== null)) {
    throw new ContractViolation(
      "document.result.found",
      "missing resources cannot contain a payload collection",
    );
  }
  return {
    ...response,
    document,
    items,
    collection_fingerprint: nullableFingerprint(
      response.collection_fingerprint,
      "response.collection_fingerprint",
    ),
    source_fingerprint: nullableFingerprint(
      response.source_fingerprint,
      "response.source_fingerprint",
    ),
    correlation_id: string(response.correlation_id, "response.correlation_id"),
  } as WorkspaceHttpResponse;
}

export function parsePlanningRun(value: unknown): JsonObject {
  const response = object(value, "response");
  const run = isJsonObject(response.planning_run) ? response.planning_run : response;
  string(run.planning_run_id, "planning_run.planning_run_id");
  return run;
}
