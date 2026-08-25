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
  | "KPI"
  | "DIAGNOSTICS"
  | "AUDIT";

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
  query_kind: "WORKSPACE_VIEW";
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
