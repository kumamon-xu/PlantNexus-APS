import { sha256Fingerprint } from "../../api/canonical";
import { ContractViolation, isJsonObject } from "../../api/contracts";
import type { JsonObject } from "../../api/types";
import {
  changeClassifications,
  executionEventTypes,
  planningRunStates,
  replanAttemptActions,
  type ArtifactReference,
  type ChangeReportDocument,
  type ChangeReportOperation,
  type ChangeReportWorkspaceProjection,
  type DynamicReplanningEnvelope,
  type ExecutionEventDocument,
  type ExecutionEventTimelineProjection,
  type FreezeResolution,
  type PlanningRunState,
  type ReplanActionAcknowledgement,
  type ReplanAttemptActionDocument,
  type ReplanAttemptProjection,
  type ReplanRequestDocument,
  type ReplanRequestProjection,
  type ReplanResultProjection,
  type ReplanningQueryDocument,
  type ScheduleVersionV2Reference,
  type StabilityProjection,
  type TardinessComparison,
} from "./types";

const fingerprintPattern = /^sha256:[0-9a-f]{64}$/u;
const utcPattern = /Z$/u;
const eventTypeSet = new Set<string>(executionEventTypes);
const planningRunStateSet = new Set<string>(planningRunStates);
const actionSet = new Set<string>(replanAttemptActions);
const classificationSet = new Set<string>(changeClassifications);
const activeStates = new Set<PlanningRunState>([
  "CREATED",
  "INGESTING",
  "VALIDATING",
  "SNAPSHOTTED",
  "BUILDING",
  "SOLVING",
  "SOLVED",
  "VERIFYING",
]);
const retryableStates = new Set<PlanningRunState>([
  "DATA_REJECTED",
  "MODEL_INVALID",
  "INFEASIBLE",
  "NO_SOLUTION_WITHIN_LIMIT",
  "VALIDATION_FAILED",
  "CANCELLED",
  "FAILED",
]);

function object(value: unknown, field: string): JsonObject {
  if (!isJsonObject(value)) throw new ContractViolation(field, "must be an object");
  return value;
}

function exactKeys(value: JsonObject, expected: readonly string[], field: string): void {
  const actual = Object.keys(value).sort();
  const required = [...expected].sort();
  if (actual.join("\u0000") !== required.join("\u0000")) {
    throw new ContractViolation(field, "contains missing or unknown fields");
  }
}

function string(value: unknown, field: string): string {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    /[\u0000-\u001f\u007f]/u.test(value)
  ) {
    throw new ContractViolation(field, "must be a canonical non-empty string");
  }
  return value;
}

function literal<T extends string | boolean>(
  value: unknown,
  expected: T,
  field: string,
): T {
  if (value !== expected) throw new ContractViolation(field, `must equal ${expected}`);
  return expected;
}

function integer(value: unknown, field: string, minimum = 0): number {
  if (!Number.isInteger(value) || (value as number) < minimum) {
    throw new ContractViolation(field, `must be an integer >= ${minimum}`);
  }
  return value as number;
}

function fingerprint(value: unknown, field: string): string {
  const result = string(value, field);
  if (!fingerprintPattern.test(result)) {
    throw new ContractViolation(field, "must be a sha256 fingerprint");
  }
  return result;
}

function utc(value: unknown, field: string): string {
  const result = string(value, field);
  if (!utcPattern.test(result) || Number.isNaN(Date.parse(result))) {
    throw new ContractViolation(field, "must be an explicit UTC instant");
  }
  return result;
}

function nullableString(value: unknown, field: string): string | null {
  return value === null ? null : string(value, field);
}

function stringArray(value: unknown, field: string): string[] {
  if (!Array.isArray(value)) throw new ContractViolation(field, "must be an array");
  return value.map((item, index) => string(item, `${field}[${index}]`));
}

function objectArray(value: unknown, field: string): JsonObject[] {
  if (!Array.isArray(value)) throw new ContractViolation(field, "must be an array");
  return value.map((item, index) => object(item, `${field}[${index}]`));
}

function planningState(value: unknown, field: string): PlanningRunState {
  const state = string(value, field);
  if (!planningRunStateSet.has(state)) {
    throw new ContractViolation(field, `unknown PlanningRun state: ${state}`);
  }
  return state as PlanningRunState;
}

function artifact(value: unknown, field: string): ArtifactReference {
  const raw = object(value, field);
  exactKeys(raw, ["document_version", "artifact_id", "fingerprint"], field);
  return {
    document_version: string(raw.document_version, `${field}.document_version`),
    artifact_id: string(raw.artifact_id, `${field}.artifact_id`),
    fingerprint: fingerprint(raw.fingerprint, `${field}.fingerprint`),
  };
}

function simulationBoundary(raw: JsonObject, query: ReplanningQueryDocument, field: string) {
  literal(raw.data_plane, "SIMULATION", `${field}.data_plane`);
  literal(raw.environment, query.environment, `${field}.environment`);
  literal(raw.synthetic, true, `${field}.synthetic`);
  literal(raw.production_binding, false, `${field}.production_binding`);
  if (fingerprint(raw.query_fingerprint, `${field}.query_fingerprint`) !== query.query_fingerprint) {
    throw new ContractViolation(`${field}.query_fingerprint`, "does not bind the request");
  }
}

async function verifyProjectionFingerprint(raw: JsonObject, field: string): Promise<void> {
  const expected = fingerprint(raw.projection_fingerprint, `${field}.projection_fingerprint`);
  const projection = Object.fromEntries(
    Object.entries(raw).filter(([key]) => key !== "projection_fingerprint"),
  ) as JsonObject;
  if ((await sha256Fingerprint(projection)) !== expected) {
    throw new ContractViolation(
      `${field}.projection_fingerprint`,
      "does not bind the server projection",
    );
  }
}

function parseEnvelope<T extends JsonObject>(
  value: unknown,
  expected: {
    operation: string;
    resourceType: string;
    resourceId: string | null;
    correlationId: string;
  },
): DynamicReplanningEnvelope<T> {
  const raw = object(value, "response");
  exactKeys(
    raw,
    [
      "response_version",
      "operation",
      "resource_type",
      "resource_id",
      "result",
      "replayed",
      "correlation_id",
    ],
    "response",
  );
  literal(raw.response_version, "dynamic-replanning-response.v1", "response.response_version");
  if (
    raw.operation !== expected.operation ||
    raw.resource_type !== expected.resourceType ||
    raw.resource_id !== expected.resourceId ||
    raw.correlation_id !== expected.correlationId
  ) {
    throw new ContractViolation("response", "does not bind operation/resource/correlation");
  }
  if (typeof raw.replayed !== "boolean") {
    throw new ContractViolation("response.replayed", "must be a boolean");
  }
  return raw as unknown as DynamicReplanningEnvelope<T>;
}

function parseExecutionEvent(value: unknown, field: string): ExecutionEventDocument {
  const raw = object(value, field);
  exactKeys(
    raw,
    [
      "execution_event_version",
      "schema_set_version",
      "canonicalization_version",
      "event_id",
      "event_type",
      "data_plane",
      "environment",
      "factory_id",
      "planning_scope_id",
      "authority",
      "source_stream",
      "source_position",
      "occurred_at_utc",
      "received_at_utc",
      "entity_refs",
      "payload",
      "synthetic",
      "synthetic_provenance",
      "production_binding",
      "correlation_id",
      "event_fingerprint",
    ],
    field,
  );
  literal(raw.execution_event_version, "execution-event.v1", `${field}.execution_event_version`);
  literal(raw.schema_set_version, "2.8.0", `${field}.schema_set_version`);
  literal(raw.canonicalization_version, "canonical-json.v1", `${field}.canonicalization_version`);
  const eventType = string(raw.event_type, `${field}.event_type`);
  if (!eventTypeSet.has(eventType)) {
    throw new ContractViolation(`${field}.event_type`, `unknown event type: ${eventType}`);
  }
  literal(raw.data_plane, "SIMULATION", `${field}.data_plane`);
  if (!["DEVELOPMENT", "TEST", "BENCHMARK"].includes(String(raw.environment))) {
    throw new ContractViolation(`${field}.environment`, "is not a P4 Simulation environment");
  }
  literal(raw.synthetic, true, `${field}.synthetic`);
  literal(raw.production_binding, false, `${field}.production_binding`);
  const authority = object(raw.authority, `${field}.authority`);
  const sourceStream = object(raw.source_stream, `${field}.source_stream`);
  object(raw.payload, `${field}.payload`);
  object(raw.synthetic_provenance, `${field}.synthetic_provenance`);
  objectArray(raw.entity_refs, `${field}.entity_refs`);
  string(authority.authority_id, `${field}.authority.authority_id`);
  string(sourceStream.stream_id, `${field}.source_stream.stream_id`);
  string(sourceStream.stream_version, `${field}.source_stream.stream_version`);
  return {
    ...raw,
    execution_event_version: "execution-event.v1",
    schema_set_version: "2.8.0",
    canonicalization_version: "canonical-json.v1",
    event_id: string(raw.event_id, `${field}.event_id`),
    event_type: eventType as ExecutionEventDocument["event_type"],
    data_plane: "SIMULATION",
    environment: raw.environment as ExecutionEventDocument["environment"],
    factory_id: string(raw.factory_id, `${field}.factory_id`),
    planning_scope_id: string(raw.planning_scope_id, `${field}.planning_scope_id`),
    authority,
    source_stream: sourceStream,
    source_position: integer(raw.source_position, `${field}.source_position`, 1),
    occurred_at_utc: utc(raw.occurred_at_utc, `${field}.occurred_at_utc`),
    received_at_utc: utc(raw.received_at_utc, `${field}.received_at_utc`),
    entity_refs: objectArray(raw.entity_refs, `${field}.entity_refs`),
    payload: object(raw.payload, `${field}.payload`),
    synthetic: true,
    synthetic_provenance: object(
      raw.synthetic_provenance,
      `${field}.synthetic_provenance`,
    ),
    production_binding: false,
    correlation_id: string(raw.correlation_id, `${field}.correlation_id`),
    event_fingerprint: fingerprint(raw.event_fingerprint, `${field}.event_fingerprint`),
  } as ExecutionEventDocument;
}

function parseFreeze(value: unknown, field: string): FreezeResolution {
  const raw = object(value, field);
  exactKeys(
    raw,
    [
      "freeze_policy_version",
      "freeze_policy_id",
      "freeze_policy_revision",
      "freeze_policy_fingerprint",
      "source",
      "window_seconds",
      "effective_from_utc",
      "effective_until_utc",
      "interval_semantics",
      "effective_lock_ids",
    ],
    field,
  );
  return {
    freeze_policy_version: literal(
      raw.freeze_policy_version,
      "freeze-policy.v1",
      `${field}.freeze_policy_version`,
    ),
    freeze_policy_id: string(raw.freeze_policy_id, `${field}.freeze_policy_id`),
    freeze_policy_revision: string(
      raw.freeze_policy_revision,
      `${field}.freeze_policy_revision`,
    ),
    freeze_policy_fingerprint: fingerprint(
      raw.freeze_policy_fingerprint,
      `${field}.freeze_policy_fingerprint`,
    ),
    source: object(raw.source, `${field}.source`),
    window_seconds: integer(raw.window_seconds, `${field}.window_seconds`),
    effective_from_utc: utc(raw.effective_from_utc, `${field}.effective_from_utc`),
    effective_until_utc: utc(raw.effective_until_utc, `${field}.effective_until_utc`),
    interval_semantics: literal(
      raw.interval_semantics,
      "HALF_OPEN_START_INCLUSIVE_END_EXCLUSIVE",
      `${field}.interval_semantics`,
    ),
    effective_lock_ids: stringArray(
      raw.effective_lock_ids,
      `${field}.effective_lock_ids`,
    ),
  };
}

function parseReplanRequest(value: unknown, field: string): ReplanRequestDocument {
  const raw = object(value, field);
  exactKeys(
    raw,
    [
      "replan_request_version",
      "schema_set_version",
      "canonicalization_version",
      "request_id",
      "data_plane",
      "environment",
      "factory_id",
      "planning_scope_id",
      "base_schedule_version",
      "base_snapshot",
      "base_problem",
      "new_snapshot",
      "new_snapshot_cutoff_at_utc",
      "new_problem",
      "event_stream",
      "trigger_event_ids",
      "trigger_reason",
      "freeze_resolution",
      "planning_policy",
      "solve_limits",
      "synthetic",
      "synthetic_provenance",
      "production_binding",
      "requested_at_utc",
      "correlation_id",
      "request_fingerprint",
    ],
    field,
  );
  literal(raw.replan_request_version, "replan-request.v1", `${field}.replan_request_version`);
  literal(raw.schema_set_version, "2.8.0", `${field}.schema_set_version`);
  literal(raw.canonicalization_version, "canonical-json.v1", `${field}.canonicalization_version`);
  literal(raw.data_plane, "SIMULATION", `${field}.data_plane`);
  literal(raw.synthetic, true, `${field}.synthetic`);
  literal(raw.production_binding, false, `${field}.production_binding`);
  if (!["DEVELOPMENT", "TEST", "BENCHMARK"].includes(String(raw.environment))) {
    throw new ContractViolation(`${field}.environment`, "is not a P4 Simulation environment");
  }
  return {
    ...raw,
    replan_request_version: "replan-request.v1",
    schema_set_version: "2.8.0",
    canonicalization_version: "canonical-json.v1",
    request_id: string(raw.request_id, `${field}.request_id`),
    data_plane: "SIMULATION",
    environment: raw.environment as ReplanRequestDocument["environment"],
    factory_id: string(raw.factory_id, `${field}.factory_id`),
    planning_scope_id: string(raw.planning_scope_id, `${field}.planning_scope_id`),
    base_schedule_version: object(
      raw.base_schedule_version,
      `${field}.base_schedule_version`,
    ),
    base_snapshot: artifact(raw.base_snapshot, `${field}.base_snapshot`),
    base_problem: artifact(raw.base_problem, `${field}.base_problem`),
    new_snapshot: artifact(raw.new_snapshot, `${field}.new_snapshot`),
    new_snapshot_cutoff_at_utc: utc(
      raw.new_snapshot_cutoff_at_utc,
      `${field}.new_snapshot_cutoff_at_utc`,
    ),
    new_problem: artifact(raw.new_problem, `${field}.new_problem`),
    event_stream: object(raw.event_stream, `${field}.event_stream`),
    trigger_event_ids: stringArray(raw.trigger_event_ids, `${field}.trigger_event_ids`),
    trigger_reason: string(raw.trigger_reason, `${field}.trigger_reason`),
    freeze_resolution: parseFreeze(raw.freeze_resolution, `${field}.freeze_resolution`),
    planning_policy: object(raw.planning_policy, `${field}.planning_policy`),
    solve_limits: object(raw.solve_limits, `${field}.solve_limits`),
    synthetic: true,
    synthetic_provenance: object(
      raw.synthetic_provenance,
      `${field}.synthetic_provenance`,
    ),
    production_binding: false,
    requested_at_utc: utc(raw.requested_at_utc, `${field}.requested_at_utc`),
    correlation_id: string(raw.correlation_id, `${field}.correlation_id`),
    request_fingerprint: fingerprint(
      raw.request_fingerprint,
      `${field}.request_fingerprint`,
    ),
  } as ReplanRequestDocument;
}

function parseAttempt(value: unknown, field: string): ReplanAttemptProjection {
  const raw = object(value, field);
  exactKeys(
    raw,
    [
      "attempt_id",
      "attempt_number",
      "planning_run_id",
      "state",
      "allowed_actions",
      "updated_at_utc",
    ],
    field,
  );
  const state = planningState(raw.state, `${field}.state`);
  const actions = stringArray(raw.allowed_actions, `${field}.allowed_actions`);
  if (actions.some((action) => !actionSet.has(action)) || new Set(actions).size !== actions.length) {
    throw new ContractViolation(`${field}.allowed_actions`, "contains unknown or duplicate actions");
  }
  if (
    actions.some(
      (action) =>
        (action === "CANCEL" && !activeStates.has(state)) ||
        (action === "RETRY" && !retryableStates.has(state)),
    )
  ) {
    throw new ContractViolation(`${field}.allowed_actions`, "does not match PlanningRun state");
  }
  return {
    attempt_id: string(raw.attempt_id, `${field}.attempt_id`),
    attempt_number: integer(raw.attempt_number, `${field}.attempt_number`, 1),
    planning_run_id: string(raw.planning_run_id, `${field}.planning_run_id`),
    state,
    allowed_actions: actions as ReplanAttemptProjection["allowed_actions"],
    updated_at_utc: utc(raw.updated_at_utc, `${field}.updated_at_utc`),
  };
}

function parseScheduleV2(value: unknown, field: string): ScheduleVersionV2Reference {
  const raw = object(value, field);
  exactKeys(
    raw,
    ["schedule_version_version", "schedule_version_id", "state", "content_fingerprint"],
    field,
  );
  return {
    schedule_version_version: literal(
      raw.schedule_version_version,
      "schedule-version.v2",
      `${field}.schedule_version_version`,
    ),
    schedule_version_id: string(raw.schedule_version_id, `${field}.schedule_version_id`),
    state: literal(raw.state, "DRAFT", `${field}.state`),
    content_fingerprint: fingerprint(
      raw.content_fingerprint,
      `${field}.content_fingerprint`,
    ),
  };
}

function parseStability(value: unknown, field: string): StabilityProjection {
  const raw = object(value, field);
  exactKeys(
    raw,
    [
      "soft_lock_violations",
      "changed_existing_operations",
      "resource_changes",
      "absolute_start_shift_seconds",
      "unchanged_existing",
      "comparable_existing",
      "unchanged_ratio",
    ],
    field,
  );
  return {
    soft_lock_violations: integer(
      raw.soft_lock_violations,
      `${field}.soft_lock_violations`,
    ),
    changed_existing_operations: integer(
      raw.changed_existing_operations,
      `${field}.changed_existing_operations`,
    ),
    resource_changes: integer(raw.resource_changes, `${field}.resource_changes`),
    absolute_start_shift_seconds: integer(
      raw.absolute_start_shift_seconds,
      `${field}.absolute_start_shift_seconds`,
    ),
    unchanged_existing: integer(raw.unchanged_existing, `${field}.unchanged_existing`),
    comparable_existing: integer(
      raw.comparable_existing,
      `${field}.comparable_existing`,
    ),
    unchanged_ratio: object(raw.unchanged_ratio, `${field}.unchanged_ratio`),
  };
}

function parseChangeOperation(value: unknown, field: string): ChangeReportOperation {
  const raw = object(value, field);
  exactKeys(
    raw,
    ["operation_id", "classification", "base_assignment", "new_assignment", "deltas", "reasons"],
    field,
  );
  const classification = string(raw.classification, `${field}.classification`);
  if (!classificationSet.has(classification)) {
    throw new ContractViolation(`${field}.classification`, `unknown value: ${classification}`);
  }
  return {
    operation_id: string(raw.operation_id, `${field}.operation_id`),
    classification: classification as ChangeReportOperation["classification"],
    base_assignment:
      raw.base_assignment === null
        ? null
        : object(raw.base_assignment, `${field}.base_assignment`),
    new_assignment:
      raw.new_assignment === null
        ? null
        : object(raw.new_assignment, `${field}.new_assignment`),
    deltas: object(raw.deltas, `${field}.deltas`),
    reasons: objectArray(raw.reasons, `${field}.reasons`),
  };
}

function parseChangeReport(value: unknown, field: string): ChangeReportDocument {
  const raw = object(value, field);
  exactKeys(
    raw,
    [
      "change_report_version",
      "schema_set_version",
      "canonicalization_version",
      "report_id",
      "report_fingerprint",
      "data_plane",
      "environment",
      "synthetic",
      "synthetic_provenance",
      "production_binding",
      "base_schedule_version",
      "new_schedule_version",
      "lineage",
      "freeze_evidence",
      "before_kpi",
      "after_kpi",
      "operation_universe_count",
      "operations",
      "stability",
      "generated_at_utc",
      "correlation_id",
    ],
    field,
  );
  literal(raw.change_report_version, "change-report.v1", `${field}.change_report_version`);
  literal(raw.schema_set_version, "2.8.0", `${field}.schema_set_version`);
  literal(raw.canonicalization_version, "canonical-json.v1", `${field}.canonicalization_version`);
  literal(raw.data_plane, "SIMULATION", `${field}.data_plane`);
  literal(raw.synthetic, true, `${field}.synthetic`);
  literal(raw.production_binding, false, `${field}.production_binding`);
  if (!["DEVELOPMENT", "TEST", "BENCHMARK"].includes(String(raw.environment))) {
    throw new ContractViolation(`${field}.environment`, "is not a P4 Simulation environment");
  }
  if (!Array.isArray(raw.operations)) {
    throw new ContractViolation(`${field}.operations`, "must be an array");
  }
  return {
    ...raw,
    change_report_version: "change-report.v1",
    schema_set_version: "2.8.0",
    canonicalization_version: "canonical-json.v1",
    report_id: string(raw.report_id, `${field}.report_id`),
    report_fingerprint: fingerprint(raw.report_fingerprint, `${field}.report_fingerprint`),
    data_plane: "SIMULATION",
    environment: raw.environment as ChangeReportDocument["environment"],
    synthetic: true,
    synthetic_provenance: object(
      raw.synthetic_provenance,
      `${field}.synthetic_provenance`,
    ),
    production_binding: false,
    base_schedule_version: object(
      raw.base_schedule_version,
      `${field}.base_schedule_version`,
    ),
    new_schedule_version: parseScheduleV2(
      raw.new_schedule_version,
      `${field}.new_schedule_version`,
    ),
    lineage: object(raw.lineage, `${field}.lineage`),
    freeze_evidence: parseFreeze(raw.freeze_evidence, `${field}.freeze_evidence`),
    before_kpi: artifact(raw.before_kpi, `${field}.before_kpi`),
    after_kpi: artifact(raw.after_kpi, `${field}.after_kpi`),
    operation_universe_count: integer(
      raw.operation_universe_count,
      `${field}.operation_universe_count`,
    ),
    operations: raw.operations.map((item, index) =>
      parseChangeOperation(item, `${field}.operations[${index}]`),
    ),
    stability: parseStability(raw.stability, `${field}.stability`),
    generated_at_utc: utc(raw.generated_at_utc, `${field}.generated_at_utc`),
    correlation_id: string(raw.correlation_id, `${field}.correlation_id`),
  } as ChangeReportDocument;
}

function parseTardiness(value: unknown, field: string): TardinessComparison {
  const raw = object(value, field);
  exactKeys(
    raw,
    [
      "metric",
      "before_seconds",
      "after_seconds",
      "delta_seconds",
      "before_kpi",
      "after_kpi",
    ],
    field,
  );
  return {
    metric: literal(
      raw.metric,
      "priority_weighted_tardiness_seconds",
      `${field}.metric`,
    ),
    before_seconds: integer(raw.before_seconds, `${field}.before_seconds`),
    after_seconds: integer(raw.after_seconds, `${field}.after_seconds`),
    delta_seconds: integer(raw.delta_seconds, `${field}.delta_seconds`, Number.MIN_SAFE_INTEGER),
    before_kpi: artifact(raw.before_kpi, `${field}.before_kpi`),
    after_kpi: artifact(raw.after_kpi, `${field}.after_kpi`),
  };
}

export async function parseTimelineResponse(
  value: unknown,
  query: ReplanningQueryDocument,
): Promise<ExecutionEventTimelineProjection> {
  const envelope = parseEnvelope<ExecutionEventTimelineProjection>(value, {
    operation: "LIST_EXECUTION_EVENTS",
    resourceType: "EXECUTION_EVENT_STREAM",
    resourceId: null,
    correlationId: query.correlation_id,
  });
  const raw = object(envelope.result, "response.result");
  exactKeys(
    raw,
    [
      "result_version",
      "query_fingerprint",
      "data_plane",
      "environment",
      "synthetic",
      "production_binding",
      "projection_fingerprint",
      "planning_scope_id",
      "authority_id",
      "stream_id",
      "stream_version",
      "from_position",
      "through_position",
      "events",
      "next_cursor",
      "allowed_actions",
    ],
    "response.result",
  );
  literal(raw.result_version, "execution-event-timeline.v1", "response.result.result_version");
  simulationBoundary(raw, query, "response.result");
  if (!Array.isArray(raw.events)) {
    throw new ContractViolation("response.result.events", "must be an array");
  }
  const events = raw.events.map((item, index) =>
    parseExecutionEvent(item, `response.result.events[${index}]`),
  );
  const positions = events.map((event) => event.source_position);
  if (
    positions.some((position, index) => index > 0 && position !== positions[index - 1]! + 1)
  ) {
    throw new ContractViolation("response.result.events", "server order is not contiguous");
  }
  const allowed = stringArray(raw.allowed_actions, "response.result.allowed_actions");
  if (allowed.length !== 1 || allowed[0] !== "view") {
    throw new ContractViolation("response.result.allowed_actions", "must be exact read authority");
  }
  const projection = {
    ...raw,
    result_version: "execution-event-timeline.v1",
    planning_scope_id: string(raw.planning_scope_id, "response.result.planning_scope_id"),
    authority_id: string(raw.authority_id, "response.result.authority_id"),
    stream_id: string(raw.stream_id, "response.result.stream_id"),
    stream_version: string(raw.stream_version, "response.result.stream_version"),
    from_position: integer(raw.from_position, "response.result.from_position", 1),
    through_position: integer(raw.through_position, "response.result.through_position", 1),
    events,
    next_cursor: nullableString(raw.next_cursor, "response.result.next_cursor"),
    allowed_actions: ["view"],
  } as ExecutionEventTimelineProjection;
  if (
    projection.planning_scope_id !== query.planning_scope_id ||
    projection.authority_id !== query.authority_id ||
    projection.stream_id !== query.stream_id ||
    projection.stream_version !== query.stream_version ||
    projection.from_position !== query.from_position ||
    projection.through_position !== query.through_position ||
    events.some(
      (event) =>
        event.planning_scope_id !== projection.planning_scope_id ||
        event.authority.authority_id !== projection.authority_id ||
        event.source_stream.stream_id !== projection.stream_id ||
        event.source_stream.stream_version !== projection.stream_version ||
        event.source_position < projection.from_position ||
        event.source_position > projection.through_position,
    )
  ) {
    throw new ContractViolation("response.result", "timeline authority differs from query");
  }
  await verifyProjectionFingerprint(raw, "response.result");
  return projection;
}

export async function parseRequestResponse(
  value: unknown,
  query: ReplanningQueryDocument,
): Promise<ReplanRequestProjection> {
  const envelope = parseEnvelope<ReplanRequestProjection>(value, {
    operation: "GET_REPLAN_REQUEST",
    resourceType: "REPLAN_REQUEST",
    resourceId: query.resource_id,
    correlationId: query.correlation_id,
  });
  const raw = object(envelope.result, "response.result");
  exactKeys(
    raw,
    [
      "result_version",
      "query_fingerprint",
      "data_plane",
      "environment",
      "synthetic",
      "production_binding",
      "projection_fingerprint",
      "request",
      "attempt",
    ],
    "response.result",
  );
  literal(raw.result_version, "replan-request-workspace.v1", "response.result.result_version");
  simulationBoundary(raw, query, "response.result");
  const request = parseReplanRequest(raw.request, "response.result.request");
  const attempt = parseAttempt(raw.attempt, "response.result.attempt");
  if (
    request.request_id !== query.resource_id ||
    request.request_fingerprint !== query.request_fingerprint ||
    request.planning_scope_id !== query.planning_scope_id
  ) {
    throw new ContractViolation("response.result.request", "does not bind the query");
  }
  await verifyProjectionFingerprint(raw, "response.result");
  return { ...raw, result_version: "replan-request-workspace.v1", request, attempt } as ReplanRequestProjection;
}

export async function parseResultResponse(
  value: unknown,
  query: ReplanningQueryDocument,
): Promise<ReplanResultProjection> {
  const envelope = parseEnvelope<ReplanResultProjection>(value, {
    operation: "GET_REPLAN_RESULT",
    resourceType: "REPLAN_RESULT",
    resourceId: query.resource_id,
    correlationId: query.correlation_id,
  });
  const raw = object(envelope.result, "response.result");
  exactKeys(
    raw,
    [
      "result_version",
      "query_fingerprint",
      "data_plane",
      "environment",
      "synthetic",
      "production_binding",
      "projection_fingerprint",
      "request_id",
      "request_fingerprint",
      "attempt_id",
      "attempt_number",
      "planning_run_id",
      "planning_run_state",
      "new_schedule_version",
      "change_report",
      "failure_reason",
      "correlation_id",
    ],
    "response.result",
  );
  literal(raw.result_version, "replan-result-workspace.v1", "response.result.result_version");
  simulationBoundary(raw, query, "response.result");
  const state = planningState(raw.planning_run_state, "response.result.planning_run_state");
  const schedule =
    raw.new_schedule_version === null
      ? null
      : parseScheduleV2(raw.new_schedule_version, "response.result.new_schedule_version");
  const reportRaw =
    raw.change_report === null
      ? null
      : object(raw.change_report, "response.result.change_report");
  let report = null;
  if (reportRaw !== null) {
    exactKeys(
      reportRaw,
      ["change_report_version", "report_id", "report_fingerprint"],
      "response.result.change_report",
    );
    report = {
      change_report_version: literal(
        reportRaw.change_report_version,
        "change-report.v1",
        "response.result.change_report.change_report_version",
      ),
      report_id: string(reportRaw.report_id, "response.result.change_report.report_id"),
      report_fingerprint: fingerprint(
        reportRaw.report_fingerprint,
        "response.result.change_report.report_fingerprint",
      ),
    };
  }
  if ((state === "COMPLETED") !== (schedule !== null && report !== null)) {
    throw new ContractViolation(
      "response.result",
      "only COMPLETED may expose a new DRAFT and ChangeReport",
    );
  }
  const projection = {
    ...raw,
    result_version: "replan-result-workspace.v1",
    request_id: string(raw.request_id, "response.result.request_id"),
    request_fingerprint: fingerprint(
      raw.request_fingerprint,
      "response.result.request_fingerprint",
    ),
    attempt_id: string(raw.attempt_id, "response.result.attempt_id"),
    attempt_number: integer(raw.attempt_number, "response.result.attempt_number", 1),
    planning_run_id: string(raw.planning_run_id, "response.result.planning_run_id"),
    planning_run_state: state,
    new_schedule_version: schedule,
    change_report: report,
    failure_reason: nullableString(raw.failure_reason, "response.result.failure_reason"),
    correlation_id: string(raw.correlation_id, "response.result.correlation_id"),
  } as ReplanResultProjection;
  if (
    projection.request_id !== query.resource_id ||
    projection.request_fingerprint !== query.request_fingerprint ||
    projection.attempt_id !== query.attempt_id ||
    projection.correlation_id !== envelope.correlation_id
  ) {
    throw new ContractViolation("response.result", "does not bind request/attempt/correlation");
  }
  await verifyProjectionFingerprint(raw, "response.result");
  return projection;
}

export async function parseChangeReportResponse(
  value: unknown,
  query: ReplanningQueryDocument,
): Promise<ChangeReportWorkspaceProjection> {
  const envelope = parseEnvelope<ChangeReportWorkspaceProjection>(value, {
    operation: "GET_CHANGE_REPORT",
    resourceType: "CHANGE_REPORT",
    resourceId: query.resource_id,
    correlationId: query.correlation_id,
  });
  const raw = object(envelope.result, "response.result");
  exactKeys(
    raw,
    [
      "result_version",
      "read_model_version",
      "query_fingerprint",
      "data_plane",
      "environment",
      "synthetic",
      "production_binding",
      "projection_fingerprint",
      "report",
      "tardiness",
      "next_cursor",
      "publishable",
    ],
    "response.result",
  );
  literal(raw.result_version, "change-report-workspace.v1", "response.result.result_version");
  literal(raw.read_model_version, "change-report-read-model.v1", "response.result.read_model_version");
  literal(raw.publishable, false, "response.result.publishable");
  simulationBoundary(raw, query, "response.result");
  const report = parseChangeReport(raw.report, "response.result.report");
  const tardiness = parseTardiness(raw.tardiness, "response.result.tardiness");
  if (
    report.report_id !== query.resource_id ||
    report.report_fingerprint !== query.report_fingerprint ||
    report.before_kpi.artifact_id !== tardiness.before_kpi.artifact_id ||
    report.before_kpi.fingerprint !== tardiness.before_kpi.fingerprint ||
    report.after_kpi.artifact_id !== tardiness.after_kpi.artifact_id ||
    report.after_kpi.fingerprint !== tardiness.after_kpi.fingerprint
  ) {
    throw new ContractViolation("response.result", "ChangeReport/KPI lineage differs");
  }
  await verifyProjectionFingerprint(raw, "response.result");
  return {
    ...raw,
    result_version: "change-report-workspace.v1",
    read_model_version: "change-report-read-model.v1",
    report,
    tardiness,
    next_cursor: nullableString(raw.next_cursor, "response.result.next_cursor"),
    publishable: false,
  } as ChangeReportWorkspaceProjection;
}

export function parseActionResponse(
  value: unknown,
  request: ReplanAttemptActionDocument,
): DynamicReplanningEnvelope<ReplanActionAcknowledgement> {
  const envelope = parseEnvelope<ReplanActionAcknowledgement>(value, {
    operation:
      request.action === "CANCEL" ? "CANCEL_REPLAN_REQUEST" : "RETRY_REPLAN_REQUEST",
    resourceType: "REPLAN_REQUEST",
    resourceId: request.request_id,
    correlationId: request.correlation_id,
  });
  const raw = object(envelope.result, "response.result");
  exactKeys(
    raw,
    [
      "result_version",
      "action",
      "request_id",
      "attempt_id",
      "attempt_number",
      "expected_planning_run_state",
      "action_fingerprint",
      "accepted",
    ],
    "response.result",
  );
  if (
    raw.result_version !== "replan-attempt-action-result.v1" ||
    raw.action !== request.action ||
    raw.request_id !== request.request_id ||
    raw.attempt_id !== request.expected_attempt_id ||
    raw.attempt_number !== request.expected_attempt_number ||
    raw.expected_planning_run_state !== request.expected_planning_run_state ||
    raw.action_fingerprint !== request.action_fingerprint ||
    raw.accepted !== true
  ) {
    throw new ContractViolation("response.result", "action acknowledgement differs");
  }
  return envelope;
}
