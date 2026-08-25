export type JsonPrimitive = boolean | number | string | null;
export type JsonValue = JsonPrimitive | JsonObject | JsonValue[];
export type JsonObject = { [key: string]: JsonValue };

export const scheduleStates = [
  "DRAFT",
  "READY_FOR_REVIEW",
  "APPROVED",
  "PUBLISHED",
  "SUPERSEDED",
  "REJECTED",
] as const;

export type ScheduleState = (typeof scheduleStates)[number];
export type DataPlane = "SIMULATION" | "PRODUCTION";
export type RuntimeEnvironment =
  | "DEVELOPMENT"
  | "TEST"
  | "BENCHMARK"
  | "PRODUCTION";

export type WorkspaceView =
  | "DATA_HEALTH"
  | "IMPORT_RUNS"
  | "PLANNING_RUNS"
  | "ORDERS"
  | "OPERATIONS"
  | "RESOURCES"
  | "CALENDARS"
  | "GANTT"
  | "RESOURCE_LOAD"
  | "KPI"
  | "DIAGNOSTICS"
  | "AUDIT"
  | "VERSION_COMPARISON";

export type WorkspaceQueryKind =
  | "WORKSPACE_VIEW"
  | "SCHEDULE_VERSION_COMPARISON"
  | "AUDIT_LOG";

export interface ArtifactReference extends JsonObject {
  document_version: string;
  artifact_id: string;
  fingerprint: string;
}

export interface VersionReference extends JsonObject {
  schedule_version_id: string;
  state: ScheduleState;
  content_fingerprint: string;
}

export interface ScheduleLineage extends JsonObject {
  planning_run_id: string;
  snapshot: ArtifactReference;
  problem: ArtifactReference;
  planning_solution: ArtifactReference;
  validation_report: ArtifactReference;
  kpi: ArtifactReference;
  solver_report: ArtifactReference;
  code_commit: string;
}

export interface ScheduleVersion extends JsonObject {
  schedule_version_version: "schedule-version.v1";
  schema_set_version: "2.6.0";
  canonicalization_version: "canonical-json.v1";
  schedule_version_id: string;
  revision: number;
  state: ScheduleState;
  data_plane: DataPlane;
  environment: RuntimeEnvironment;
  synthetic: boolean;
  parent_schedule_version: VersionReference | null;
  lineage: ScheduleLineage;
  content_fingerprint: string;
  validation: JsonObject;
  allowed_actions: JsonValue[];
  created_at_utc: string;
  created_by_actor_ref: string;
}

export interface WorkspaceQueryResultBody extends JsonObject {
  result_version: "workspace-query-result.v1";
  found: boolean;
  authoritative_schedule_version: VersionReference | null;
  lineage: ScheduleLineage | null;
  items: JsonObject[];
  next_cursor: string | null;
  observed_count: number;
  allowed_actions: JsonValue[];
  freshness: string;
  generated_at_utc: string;
}

export interface WorkspaceQueryDocument extends JsonObject {
  workspace_query_version: "workspace-query.v1";
  schema_set_version: "2.6.0";
  canonicalization_version: "canonical-json.v1";
  direction: "REQUEST" | "RESULT";
  query_kind: WorkspaceQueryKind;
  data_plane: DataPlane;
  environment: RuntimeEnvironment;
  synthetic: boolean;
  resource: JsonObject;
  view: WorkspaceView;
  schedule_version_precondition: VersionReference | null;
  sort: JsonObject[];
  filters: JsonObject;
  page: JsonObject;
  query_fingerprint: string;
  correlation_id: string;
  result: WorkspaceQueryResultBody | null;
}

export interface WorkspacePayloadItem extends JsonObject {
  item_id: string;
  item_type: string;
  payload: JsonObject;
  payload_fingerprint: string;
}

export interface GanttSegment extends JsonObject {
  item_id: string;
  operation_id: string;
  order_id: string;
  resource_id: string;
  resource_code: string;
  factory_id: string | null;
  workshop_id: string | null;
  production_line_id: string | null;
  resource_group_id: string | null;
  start_at_utc: string;
  end_at_utc: string;
  duration_seconds: number;
  start_tick: number;
  end_tick: number;
  lock_ids: string[];
  execution_fact_ids: string[];
}

export interface ResourceLoad extends JsonObject {
  item_id: string;
  resource_id: string;
  resource_code: string;
  calendar_id: string;
  start_at_utc: string;
  end_at_utc: string;
  bucket_kind: "PLANNING_HORIZON";
  assignment_count: number;
  planned_busy_seconds: number;
  available_seconds: number;
  utilization: number;
}

export const comparisonChangeKinds = [
  "ADDED",
  "REMOVED",
  "RESOURCE_CHANGE",
  "DURATION_CHANGE",
  "START_SHIFT",
  "UNCHANGED",
] as const;

export type ComparisonChangeKind = (typeof comparisonChangeKinds)[number];

export interface OperationDelta extends JsonObject {
  operation_id: string;
  change_kind: ComparisonChangeKind;
  base_resource_id: string | null;
  compared_resource_id: string | null;
  base_start_at_utc: string | null;
  compared_start_at_utc: string | null;
  base_end_at_utc: string | null;
  compared_end_at_utc: string | null;
}

export interface KpiDelta extends JsonObject {
  metric: string;
  base_value: number;
  compared_value: number;
  delta: number;
}

export interface ComparisonSummary extends JsonObject {
  operation_count: number;
  changed_operation_count: number;
  added_operation_count: number;
  removed_operation_count: number;
  resource_changed_count: number;
}

export interface ScheduleVersionComparison extends JsonObject {
  schedule_version_comparison_version: "schedule-version-comparison.v1";
  schema_set_version: "2.6.0";
  canonicalization_version: "canonical-json.v1";
  comparison_id: string;
  data_plane: DataPlane;
  environment: RuntimeEnvironment;
  synthetic: boolean;
  base_version: VersionReference;
  compared_version: VersionReference;
  query_fingerprint: string;
  operation_deltas: OperationDelta[];
  kpi_deltas: KpiDelta[];
  summary: ComparisonSummary;
  comparison_fingerprint: string;
  generated_at_utc: string;
}

export interface WorkspaceHttpResponse extends JsonObject {
  document: WorkspaceQueryDocument;
  items: WorkspacePayloadItem[];
  collection_fingerprint: string | null;
  source_fingerprint: string | null;
  correlation_id: string;
}

export type WorkspaceUiState =
  | "loading"
  | "empty"
  | "ready"
  | "stale"
  | "authorization_denied"
  | "contract_error"
  | "server_error";

export type ClientFailureKind = Exclude<WorkspaceUiState, "loading" | "empty" | "ready">;
