import { sha256Fingerprint, workspaceQueryFingerprint } from "./canonical";
import {
  comparisonChangeKinds,
  exportJobStates,
  scheduleStates,
  workspaceCommandTypes,
  type ArtifactReference,
  type ComparisonChangeKind,
  type ComparisonSummary,
  type GanttSegment,
  type ExportArtifactManifest,
  type ExportJob,
  type ExportJobState,
  type JsonObject,
  type JsonValue,
  type KpiDelta,
  type OperationDelta,
  type ResourceLoad,
  type ScheduleLineage,
  type ScheduleState,
  type ScheduleVersion,
  type ScheduleVersionComparison,
  type VersionReference,
  type WorkspaceHttpResponse,
  type WorkspaceActionResult,
  type WorkspaceCommandDocument,
  type WorkspaceCommandType,
  type WorkspacePayloadItem,
  type WorkspaceQueryDocument,
  type WorkspaceQueryResultBody,
  type WorkspaceView,
} from "./types";

const fingerprintPattern = /^sha256:[0-9a-f]{64}$/;
const scheduleStateSet = new Set<string>(scheduleStates);
const comparisonChangeKindSet = new Set<string>(comparisonChangeKinds);
const exportJobStateSet = new Set<string>(exportJobStates);
const workspaceCommandTypeSet = new Set<string>(workspaceCommandTypes);

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

function nullableString(value: unknown, field: string): string | null {
  return value === null ? null : string(value, field);
}

function nullableUtc(value: unknown, field: string): string | null {
  return value === null ? null : utc(value, field);
}

function finiteNumber(value: unknown, field: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new ContractViolation(field, "must be a finite number");
  }
  return value;
}

function nonNegativeNumber(value: unknown, field: string): number {
  const result = finiteNumber(value, field);
  if (result < 0) throw new ContractViolation(field, "must be non-negative");
  return result;
}

function integer(value: unknown, field: string, minimum = 0): number {
  if (!Number.isInteger(value) || (value as number) < minimum) {
    throw new ContractViolation(field, `must be an integer >= ${minimum}`);
  }
  return value as number;
}

function stringArray(value: unknown, field: string): string[] {
  if (!Array.isArray(value)) {
    throw new ContractViolation(field, "must be an array");
  }
  return value.map((item, index) => string(item, `${field}[${index}]`));
}

function state(value: unknown, field: string): ScheduleState {
  const result = string(value, field);
  if (!scheduleStateSet.has(result)) {
    throw new ContractViolation(field, `unknown ScheduleVersion state: ${result}`);
  }
  return result as ScheduleState;
}

function exportState(value: unknown, field: string): ExportJobState {
  const result = string(value, field);
  if (!exportJobStateSet.has(result)) {
    throw new ContractViolation(field, `unknown ExportJob state: ${result}`);
  }
  return result as ExportJobState;
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
  if (raw.synthetic && !isJsonObject(raw.synthetic_provenance)) {
    throw new ContractViolation(
      "schedule_version.synthetic_provenance",
      "synthetic versions require provenance",
    );
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
    synthetic_provenance: raw.synthetic
      ? (raw.synthetic_provenance as JsonObject)
      : null,
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

export function parseExportJob(value: unknown): ExportJob {
  const envelope = object(value, "response");
  const raw =
    envelope.export_job_version === "export-job.v2"
      ? envelope
      : object(envelope.document ?? envelope.export_job, "response.export_job");
  const rawArtifact = raw.artifact_manifest;
  let artifactManifest: ExportArtifactManifest | null = null;
  if (rawArtifact !== null) {
    const artifact = object(rawArtifact, "export_job.artifact_manifest");
    artifactManifest = {
      ...artifact,
      export_manifest_version: literal(
        artifact.export_manifest_version,
        "export-manifest.v2",
        "export_job.artifact_manifest.export_manifest_version",
      ),
      package_id: string(
        artifact.package_id,
        "export_job.artifact_manifest.package_id",
      ),
      manifest_fingerprint: fingerprint(
        artifact.manifest_fingerprint,
        "export_job.artifact_manifest.manifest_fingerprint",
      ),
      storage_reference: fingerprint(
        artifact.storage_reference,
        "export_job.artifact_manifest.storage_reference",
      ),
    } as ExportArtifactManifest;
  }
  if (typeof raw.synthetic !== "boolean") {
    throw new ContractViolation("export_job.synthetic", "must be a boolean");
  }
  const provenance = raw.synthetic_provenance;
  if (raw.synthetic && !isJsonObject(provenance)) {
    throw new ContractViolation(
      "export_job.synthetic_provenance",
      "synthetic jobs require provenance",
    );
  }
  return {
    ...raw,
    export_job_version: literal(
      raw.export_job_version,
      "export-job.v2",
      "export_job.export_job_version",
    ),
    schema_set_version: literal(
      raw.schema_set_version,
      "2.7.0",
      "export_job.schema_set_version",
    ),
    canonicalization_version: literal(
      raw.canonicalization_version,
      "canonical-json.v1",
      "export_job.canonicalization_version",
    ),
    export_job_id: string(raw.export_job_id, "export_job.export_job_id"),
    state: exportState(raw.state, "export_job.state"),
    schedule_version: versionReference(
      raw.schedule_version,
      "export_job.schedule_version",
    ),
    data_plane: literalPlane(raw.data_plane, "export_job.data_plane"),
    environment: literalEnvironment(raw.environment, "export_job.environment"),
    synthetic: raw.synthetic,
    synthetic_provenance: raw.synthetic ? (provenance as JsonObject) : null,
    target: literal(
      raw.target,
      "SIMULATION_INTERNAL",
      "export_job.target",
    ),
    package_profile: literal(
      raw.package_profile,
      "p3-standard-export.v1",
      "export_job.package_profile",
    ),
    attempt: integer(raw.attempt, "export_job.attempt"),
    artifact_manifest: artifactManifest,
    latest_audit_event_id: string(
      raw.latest_audit_event_id,
      "export_job.latest_audit_event_id",
    ),
    job_fingerprint: fingerprint(
      raw.job_fingerprint,
      "export_job.job_fingerprint",
    ),
  } as ExportJob;
}

export function parseWorkspaceActionResult(
  value: unknown,
  command: WorkspaceCommandDocument,
): WorkspaceActionResult {
  const raw = object(value, "action_response");
  const correlationId = string(raw.correlation_id, "action_response.correlation_id");
  if (correlationId !== command.correlation_id) {
    throw new ContractViolation(
      "action_response.correlation_id",
      "does not match the outbound command",
    );
  }
  const rawCommandType = raw.command_type;
  if (
    rawCommandType !== undefined &&
    (!workspaceCommandTypeSet.has(String(rawCommandType)) ||
      rawCommandType !== command.command_type)
  ) {
    throw new ContractViolation(
      "action_response.command_type",
      "does not match the outbound command",
    );
  }
  const sourceVersion =
    raw.source_version === undefined || raw.source_version === null
      ? null
      : versionReference(raw.source_version, "action_response.source_version");
  const rawAuthority = raw.new_version ?? raw.published_version;
  const authoritativeVersion =
    rawAuthority === undefined || rawAuthority === null
      ? null
      : versionReference(rawAuthority, "action_response.authoritative_version");
  let exportJob: ExportJob | null = null;
  if (raw.document !== undefined || raw.export_job !== undefined) {
    exportJob = parseExportJob(raw);
  }
  const rawReplay = raw.exact_replay ?? raw.replayed ?? false;
  if (typeof rawReplay !== "boolean") {
    throw new ContractViolation("action_response.exact_replay", "must be boolean");
  }
  if (
    command.command_type === "REQUEST_EXPORT" ||
    command.command_type === "RETRY_EXPORT" ||
    command.command_type === "CANCEL_EXPORT"
  ) {
    if (exportJob === null) {
      throw new ContractViolation(
        "action_response.document",
        "export commands require export-job.v2",
      );
    }
  } else if (authoritativeVersion === null) {
    throw new ContractViolation(
      "action_response.authoritative_version",
      "schedule commands require an authoritative Version reference",
    );
  }
  return {
    commandType: command.command_type as WorkspaceCommandType,
    correlationId,
    auditEventId: string(
      raw.audit_event_id ?? exportJob?.latest_audit_event_id,
      "action_response.audit_event_id",
    ),
    exactReplay: rawReplay,
    sourceVersion,
    authoritativeVersion,
    exportJob,
  };
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
      expectedView === "VERSION_COMPARISON"
        ? "SCHEDULE_VERSION_COMPARISON"
        : expectedView === "AUDIT"
          ? "AUDIT_LOG"
          : "WORKSPACE_VIEW",
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

function requireItemType(
  item: WorkspacePayloadItem,
  expected: string,
  index: number,
): void {
  if (item.item_type !== expected) {
    throw new ContractViolation(
      `items[${index}].item_type`,
      `expected ${expected}, received ${item.item_type}`,
    );
  }
}

function ganttSegment(item: WorkspacePayloadItem, index: number): GanttSegment {
  requireItemType(item, "GANTT_SEGMENT", index);
  const payload = item.payload;
  const startAt = utc(payload.start_at_utc, `items[${index}].payload.start_at_utc`);
  const endAt = utc(payload.end_at_utc, `items[${index}].payload.end_at_utc`);
  if (Date.parse(endAt) <= Date.parse(startAt)) {
    throw new ContractViolation(
      `items[${index}].payload.end_at_utc`,
      "must be later than start_at_utc",
    );
  }
  const startTick = integer(payload.start_tick, `items[${index}].payload.start_tick`);
  const endTick = integer(payload.end_tick, `items[${index}].payload.end_tick`, 1);
  if (endTick <= startTick) {
    throw new ContractViolation(
      `items[${index}].payload.end_tick`,
      "must be greater than start_tick",
    );
  }
  return {
    ...payload,
    item_id: item.item_id,
    operation_id: string(payload.operation_id, `items[${index}].payload.operation_id`),
    order_id: string(payload.order_id, `items[${index}].payload.order_id`),
    resource_id: string(payload.resource_id, `items[${index}].payload.resource_id`),
    resource_code: string(payload.resource_code, `items[${index}].payload.resource_code`),
    factory_id: nullableString(payload.factory_id, `items[${index}].payload.factory_id`),
    workshop_id: nullableString(payload.workshop_id, `items[${index}].payload.workshop_id`),
    production_line_id: nullableString(
      payload.production_line_id,
      `items[${index}].payload.production_line_id`,
    ),
    resource_group_id: nullableString(
      payload.resource_group_id,
      `items[${index}].payload.resource_group_id`,
    ),
    start_at_utc: startAt,
    end_at_utc: endAt,
    duration_seconds: integer(
      payload.duration_seconds,
      `items[${index}].payload.duration_seconds`,
      1,
    ),
    start_tick: startTick,
    end_tick: endTick,
    lock_ids: stringArray(payload.lock_ids, `items[${index}].payload.lock_ids`),
    execution_fact_ids: stringArray(
      payload.execution_fact_ids,
      `items[${index}].payload.execution_fact_ids`,
    ),
  } as GanttSegment;
}

function resourceLoad(item: WorkspacePayloadItem, index: number): ResourceLoad {
  requireItemType(item, "RESOURCE_LOAD", index);
  const payload = item.payload;
  const startAt = utc(payload.start_at_utc, `items[${index}].payload.start_at_utc`);
  const endAt = utc(payload.end_at_utc, `items[${index}].payload.end_at_utc`);
  if (Date.parse(endAt) <= Date.parse(startAt)) {
    throw new ContractViolation(
      `items[${index}].payload.end_at_utc`,
      "must be later than start_at_utc",
    );
  }
  return {
    ...payload,
    item_id: item.item_id,
    resource_id: string(payload.resource_id, `items[${index}].payload.resource_id`),
    resource_code: string(payload.resource_code, `items[${index}].payload.resource_code`),
    calendar_id: string(payload.calendar_id, `items[${index}].payload.calendar_id`),
    start_at_utc: startAt,
    end_at_utc: endAt,
    bucket_kind: literal(
      payload.bucket_kind,
      "PLANNING_HORIZON",
      `items[${index}].payload.bucket_kind`,
    ),
    assignment_count: integer(
      payload.assignment_count,
      `items[${index}].payload.assignment_count`,
    ),
    planned_busy_seconds: nonNegativeNumber(
      payload.planned_busy_seconds,
      `items[${index}].payload.planned_busy_seconds`,
    ),
    available_seconds: nonNegativeNumber(
      payload.available_seconds,
      `items[${index}].payload.available_seconds`,
    ),
    utilization: nonNegativeNumber(
      payload.utilization,
      `items[${index}].payload.utilization`,
    ),
  } as ResourceLoad;
}

function operationDelta(value: unknown, index: number): OperationDelta {
  const raw = object(value, `comparison.operation_deltas[${index}]`);
  const changeKind = string(
    raw.change_kind,
    `comparison.operation_deltas[${index}].change_kind`,
  );
  if (!comparisonChangeKindSet.has(changeKind)) {
    throw new ContractViolation(
      `comparison.operation_deltas[${index}].change_kind`,
      `unsupported server change kind: ${changeKind}`,
    );
  }
  return {
    ...raw,
    operation_id: string(
      raw.operation_id,
      `comparison.operation_deltas[${index}].operation_id`,
    ),
    change_kind: changeKind as ComparisonChangeKind,
    base_resource_id: nullableString(
      raw.base_resource_id,
      `comparison.operation_deltas[${index}].base_resource_id`,
    ),
    compared_resource_id: nullableString(
      raw.compared_resource_id,
      `comparison.operation_deltas[${index}].compared_resource_id`,
    ),
    base_start_at_utc: nullableUtc(
      raw.base_start_at_utc,
      `comparison.operation_deltas[${index}].base_start_at_utc`,
    ),
    compared_start_at_utc: nullableUtc(
      raw.compared_start_at_utc,
      `comparison.operation_deltas[${index}].compared_start_at_utc`,
    ),
    base_end_at_utc: nullableUtc(
      raw.base_end_at_utc,
      `comparison.operation_deltas[${index}].base_end_at_utc`,
    ),
    compared_end_at_utc: nullableUtc(
      raw.compared_end_at_utc,
      `comparison.operation_deltas[${index}].compared_end_at_utc`,
    ),
  } as OperationDelta;
}

function kpiDelta(value: unknown, index: number): KpiDelta {
  const raw = object(value, `comparison.kpi_deltas[${index}]`);
  return {
    ...raw,
    metric: string(raw.metric, `comparison.kpi_deltas[${index}].metric`),
    base_value: finiteNumber(
      raw.base_value,
      `comparison.kpi_deltas[${index}].base_value`,
    ),
    compared_value: finiteNumber(
      raw.compared_value,
      `comparison.kpi_deltas[${index}].compared_value`,
    ),
    delta: finiteNumber(raw.delta, `comparison.kpi_deltas[${index}].delta`),
  } as KpiDelta;
}

function comparisonSummary(value: unknown): ComparisonSummary {
  const raw = object(value, "comparison.summary");
  return {
    ...raw,
    operation_count: integer(raw.operation_count, "comparison.summary.operation_count"),
    changed_operation_count: integer(
      raw.changed_operation_count,
      "comparison.summary.changed_operation_count",
    ),
    added_operation_count: integer(
      raw.added_operation_count,
      "comparison.summary.added_operation_count",
    ),
    removed_operation_count: integer(
      raw.removed_operation_count,
      "comparison.summary.removed_operation_count",
    ),
    resource_changed_count: integer(
      raw.resource_changed_count,
      "comparison.summary.resource_changed_count",
    ),
  } as ComparisonSummary;
}

function comparisonPayload(
  item: WorkspacePayloadItem,
  index: number,
): ScheduleVersionComparison {
  requireItemType(item, "VERSION_COMPARISON", index);
  const raw = item.payload;
  if (!Array.isArray(raw.operation_deltas) || !Array.isArray(raw.kpi_deltas)) {
    throw new ContractViolation(
      `items[${index}].payload`,
      "operation_deltas and kpi_deltas must be arrays",
    );
  }
  const base = versionReference(raw.base_version, "comparison.base_version");
  const compared = versionReference(
    raw.compared_version,
    "comparison.compared_version",
  );
  if (base.schedule_version_id === compared.schedule_version_id) {
    throw new ContractViolation(
      "comparison.compared_version.schedule_version_id",
      "must differ from the base Version",
    );
  }
  return {
    ...raw,
    schedule_version_comparison_version: literal(
      raw.schedule_version_comparison_version,
      "schedule-version-comparison.v1",
      "comparison.schedule_version_comparison_version",
    ),
    schema_set_version: literal(
      raw.schema_set_version,
      "2.6.0",
      "comparison.schema_set_version",
    ),
    canonicalization_version: literal(
      raw.canonicalization_version,
      "canonical-json.v1",
      "comparison.canonicalization_version",
    ),
    comparison_id: string(raw.comparison_id, "comparison.comparison_id"),
    data_plane: literalPlane(raw.data_plane, "comparison.data_plane"),
    environment: literalEnvironment(raw.environment, "comparison.environment"),
    synthetic: requireBoolean(raw.synthetic, "comparison.synthetic"),
    base_version: base,
    compared_version: compared,
    query_fingerprint: fingerprint(
      raw.query_fingerprint,
      "comparison.query_fingerprint",
    ),
    operation_deltas: raw.operation_deltas.map(operationDelta),
    kpi_deltas: raw.kpi_deltas.map(kpiDelta),
    summary: comparisonSummary(raw.summary),
    comparison_fingerprint: fingerprint(
      raw.comparison_fingerprint,
      "comparison.comparison_fingerprint",
    ),
    generated_at_utc: utc(raw.generated_at_utc, "comparison.generated_at_utc"),
  } as ScheduleVersionComparison;
}

export function parseGanttSegments(response: WorkspaceHttpResponse): GanttSegment[] {
  if (response.document.view !== "GANTT") {
    throw new ContractViolation("document.view", "expected GANTT response");
  }
  return response.items.map(ganttSegment);
}

export function parseResourceLoads(response: WorkspaceHttpResponse): ResourceLoad[] {
  if (response.document.view !== "RESOURCE_LOAD") {
    throw new ContractViolation("document.view", "expected RESOURCE_LOAD response");
  }
  return response.items.map(resourceLoad);
}

export function parseVersionComparison(
  response: WorkspaceHttpResponse,
): ScheduleVersionComparison {
  if (response.document.view !== "VERSION_COMPARISON") {
    throw new ContractViolation(
      "document.view",
      "expected VERSION_COMPARISON response",
    );
  }
  if (response.items.length !== 1 || response.items[0] === undefined) {
    throw new ContractViolation(
      "response.items",
      "Version comparison requires exactly one complete payload",
    );
  }
  return comparisonPayload(response.items[0], 0);
}

function validateViewPayloads(
  view: WorkspaceView,
  response: WorkspaceHttpResponse,
): void {
  if (view === "GANTT") parseGanttSegments(response);
  if (view === "RESOURCE_LOAD") parseResourceLoads(response);
  if (view === "VERSION_COMPARISON") parseVersionComparison(response);
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
    const calculatedPayload = await sha256Fingerprint(item.payload);
    if (calculatedPayload !== item.payload_fingerprint) {
      throw new ContractViolation(
        `items[${index}].payload_fingerprint`,
        "does not match the canonical complete payload",
      );
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
  const parsed = {
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
  validateViewPayloads(expectedView, parsed);
  return parsed;
}

export function parsePlanningRun(value: unknown): JsonObject {
  const response = object(value, "response");
  const run = isJsonObject(response.planning_run) ? response.planning_run : response;
  string(run.planning_run_id, "planning_run.planning_run_id");
  return run;
}
