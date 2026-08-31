import type {
  DataPlane,
  JsonObject,
  RuntimeEnvironment,
} from "../../api/types";

export const executionEventTypes = [
  "OPERATION_STARTED",
  "OPERATION_COMPLETED",
  "MACHINE_UNAVAILABLE",
  "MACHINE_RECOVERED",
  "MATERIAL_READY",
  "MATERIAL_DELAYED",
  "PROCESSING_DURATION_CHANGED",
  "PROCESSING_REMAINING_CHANGED",
  "URGENT_DEMAND_RECEIVED",
  "LOCK_CREATED",
  "LOCK_RELEASED",
] as const;

export type ExecutionEventType = (typeof executionEventTypes)[number];

export const planningRunStates = [
  "CREATED",
  "INGESTING",
  "VALIDATING",
  "SNAPSHOTTED",
  "BUILDING",
  "SOLVING",
  "SOLVED",
  "VERIFYING",
  "COMPLETED",
  "DATA_REJECTED",
  "MODEL_INVALID",
  "INFEASIBLE",
  "NO_SOLUTION_WITHIN_LIMIT",
  "VALIDATION_FAILED",
  "CANCELLED",
  "FAILED",
] as const;

export type PlanningRunState = (typeof planningRunStates)[number];

export const replanAttemptActions = ["CANCEL", "RETRY"] as const;
export type ReplanAttemptAction = (typeof replanAttemptActions)[number];

export const changeClassifications = [
  "UNCHANGED",
  "CHANGED",
  "ADDED",
  "REMOVED_BY_FACT",
] as const;
export type ChangeClassification = (typeof changeClassifications)[number];

export interface ReplanningPage extends JsonObject {
  size: number;
  cursor: string | null;
}

export type ReplanningQueryKind =
  | "EXECUTION_EVENT_STREAM"
  | "REPLAN_REQUEST"
  | "REPLAN_RESULT"
  | "CHANGE_REPORT";

export interface ReplanningQueryDocument extends JsonObject {
  replanning_query_version: "dynamic-replanning-query.v1";
  api_contract_version: "dynamic-replanning-http.v1";
  canonicalization_version: "canonical-json.v1";
  query_kind: ReplanningQueryKind;
  resource_id: string | null;
  planning_scope_id: string;
  authority_id: string | null;
  stream_id: string | null;
  stream_version: string | null;
  from_position: number | null;
  through_position: number | null;
  attempt_id: string | null;
  request_fingerprint: string | null;
  report_fingerprint: string | null;
  page: ReplanningPage;
  data_plane: "SIMULATION";
  environment: "DEVELOPMENT" | "TEST" | "BENCHMARK";
  production_binding: false;
  correlation_id: string;
  query_fingerprint: string;
}

export interface ReplanningWorkspaceIdentity {
  planningScopeId: string;
  authorityId: string;
  streamId: string;
  streamVersion: string;
  fromPosition: number;
  throughPosition: number;
  requestId: string;
  requestFingerprint: string;
  attemptId: string;
}

export interface ArtifactReference extends JsonObject {
  document_version: string;
  artifact_id: string;
  fingerprint: string;
}

export interface ExecutionEventDocument extends JsonObject {
  execution_event_version: "execution-event.v1";
  schema_set_version: "2.8.0";
  canonicalization_version: "canonical-json.v1";
  event_id: string;
  event_type: ExecutionEventType;
  data_plane: "SIMULATION";
  environment: "DEVELOPMENT" | "TEST" | "BENCHMARK";
  factory_id: string;
  planning_scope_id: string;
  authority: JsonObject;
  source_stream: JsonObject;
  source_position: number;
  occurred_at_utc: string;
  received_at_utc: string;
  entity_refs: JsonObject[];
  payload: JsonObject;
  synthetic: true;
  synthetic_provenance: JsonObject;
  production_binding: false;
  correlation_id: string;
  event_fingerprint: string;
}

export interface FreezeResolution extends JsonObject {
  freeze_policy_version: "freeze-policy.v1";
  freeze_policy_id: string;
  freeze_policy_revision: string;
  freeze_policy_fingerprint: string;
  source: JsonObject;
  window_seconds: number;
  effective_from_utc: string;
  effective_until_utc: string;
  interval_semantics: "HALF_OPEN_START_INCLUSIVE_END_EXCLUSIVE";
  effective_lock_ids: string[];
}

export interface ReplanRequestDocument extends JsonObject {
  replan_request_version: "replan-request.v1";
  schema_set_version: "2.8.0";
  canonicalization_version: "canonical-json.v1";
  request_id: string;
  data_plane: "SIMULATION";
  environment: "DEVELOPMENT" | "TEST" | "BENCHMARK";
  factory_id: string;
  planning_scope_id: string;
  base_schedule_version: JsonObject;
  base_snapshot: ArtifactReference;
  base_problem: ArtifactReference;
  new_snapshot: ArtifactReference;
  new_snapshot_cutoff_at_utc: string;
  new_problem: ArtifactReference;
  event_stream: JsonObject;
  trigger_event_ids: string[];
  trigger_reason: string;
  freeze_resolution: FreezeResolution;
  planning_policy: JsonObject;
  solve_limits: JsonObject;
  synthetic: true;
  synthetic_provenance: JsonObject;
  production_binding: false;
  requested_at_utc: string;
  correlation_id: string;
  request_fingerprint: string;
}

export interface ReplanAttemptProjection extends JsonObject {
  attempt_id: string;
  attempt_number: number;
  planning_run_id: string;
  state: PlanningRunState;
  allowed_actions: ReplanAttemptAction[];
  updated_at_utc: string;
}

interface ProjectionBoundary extends JsonObject {
  query_fingerprint: string;
  data_plane: "SIMULATION";
  environment: "DEVELOPMENT" | "TEST" | "BENCHMARK";
  synthetic: true;
  production_binding: false;
  projection_fingerprint: string;
}

export interface ExecutionEventTimelineProjection extends ProjectionBoundary {
  result_version: "execution-event-timeline.v1";
  planning_scope_id: string;
  authority_id: string;
  stream_id: string;
  stream_version: string;
  from_position: number;
  through_position: number;
  events: ExecutionEventDocument[];
  next_cursor: string | null;
  allowed_actions: ["view"];
}

export interface ReplanRequestProjection extends ProjectionBoundary {
  result_version: "replan-request-workspace.v1";
  request: ReplanRequestDocument;
  attempt: ReplanAttemptProjection;
}

export interface ScheduleVersionV2Reference extends JsonObject {
  schedule_version_version: "schedule-version.v2";
  schedule_version_id: string;
  state: "DRAFT";
  content_fingerprint: string;
}

export interface ChangeReportReference extends JsonObject {
  change_report_version: "change-report.v1";
  report_id: string;
  report_fingerprint: string;
}

export interface ReplanResultProjection extends ProjectionBoundary {
  result_version: "replan-result-workspace.v1";
  request_id: string;
  request_fingerprint: string;
  attempt_id: string;
  attempt_number: number;
  planning_run_id: string;
  planning_run_state: PlanningRunState;
  new_schedule_version: ScheduleVersionV2Reference | null;
  change_report: ChangeReportReference | null;
  failure_reason: string | null;
  correlation_id: string;
}

export interface ChangeReportOperation extends JsonObject {
  operation_id: string;
  classification: ChangeClassification;
  base_assignment: JsonObject | null;
  new_assignment: JsonObject | null;
  deltas: JsonObject;
  reasons: JsonObject[];
}

export interface StabilityProjection extends JsonObject {
  soft_lock_violations: number;
  changed_existing_operations: number;
  resource_changes: number;
  absolute_start_shift_seconds: number;
  unchanged_existing: number;
  comparable_existing: number;
  unchanged_ratio: JsonObject;
}

export interface ChangeReportDocument extends JsonObject {
  change_report_version: "change-report.v1";
  schema_set_version: "2.8.0";
  canonicalization_version: "canonical-json.v1";
  report_id: string;
  report_fingerprint: string;
  data_plane: "SIMULATION";
  environment: "DEVELOPMENT" | "TEST" | "BENCHMARK";
  synthetic: true;
  synthetic_provenance: JsonObject;
  production_binding: false;
  base_schedule_version: JsonObject;
  new_schedule_version: ScheduleVersionV2Reference;
  lineage: JsonObject;
  freeze_evidence: FreezeResolution;
  before_kpi: ArtifactReference;
  after_kpi: ArtifactReference;
  operation_universe_count: number;
  operations: ChangeReportOperation[];
  stability: StabilityProjection;
  generated_at_utc: string;
  correlation_id: string;
}

export interface TardinessComparison extends JsonObject {
  metric: "priority_weighted_tardiness_seconds";
  before_seconds: number;
  after_seconds: number;
  delta_seconds: number;
  before_kpi: ArtifactReference;
  after_kpi: ArtifactReference;
}

export interface ChangeReportWorkspaceProjection extends ProjectionBoundary {
  result_version: "change-report-workspace.v1";
  read_model_version: "change-report-read-model.v1";
  report: ChangeReportDocument;
  tardiness: TardinessComparison;
  next_cursor: string | null;
  publishable: false;
}

export interface ReplanningWorkspaceProjection {
  timeline: ExecutionEventTimelineProjection;
  request: ReplanRequestProjection;
  result: ReplanResultProjection;
  report: ChangeReportWorkspaceProjection | null;
}

export interface ReplanAttemptActionDocument extends JsonObject {
  replan_action_version: "replan-attempt-action-http.v1";
  api_contract_version: "dynamic-replanning-http.v1";
  canonicalization_version: "canonical-json.v1";
  action_id: string;
  action: ReplanAttemptAction;
  request_id: string;
  request_fingerprint: string;
  expected_attempt_id: string;
  expected_attempt_number: number;
  expected_planning_run_state: PlanningRunState;
  reason: string;
  data_plane: "SIMULATION";
  environment: "DEVELOPMENT" | "TEST" | "BENCHMARK";
  production_binding: false;
  correlation_id: string;
  idempotency_key_reference: string;
  action_fingerprint: string;
}

export interface ReplanActionRequest {
  document: ReplanAttemptActionDocument;
  idempotencyKey: string;
  planningScopeId: string;
}

export interface ReplanActionAcknowledgement extends JsonObject {
  result_version: "replan-attempt-action-result.v1";
  action: ReplanAttemptAction;
  request_id: string;
  attempt_id: string;
  attempt_number: number;
  expected_planning_run_state: PlanningRunState;
  action_fingerprint: string;
  accepted: true;
}

export interface DynamicReplanningEnvelope<T extends JsonObject> {
  response_version: "dynamic-replanning-response.v1";
  operation: string;
  resource_type: string;
  resource_id: string | null;
  result: T;
  replayed: boolean;
  correlation_id: string;
}

export interface ReplanningAuthority {
  dataPlane: DataPlane;
  environment: RuntimeEnvironment;
}
