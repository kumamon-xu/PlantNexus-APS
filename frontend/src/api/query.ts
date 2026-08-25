import { workspaceQueryFingerprint } from "./canonical";
import type {
  DataPlane,
  JsonObject,
  RuntimeEnvironment,
  VersionReference,
  WorkspaceQueryDocument,
  WorkspaceView,
} from "./types";

export interface QueryAuthority {
  dataPlane: DataPlane;
  environment: RuntimeEnvironment;
  synthetic: boolean;
  syntheticProvenance?: JsonObject;
}

export interface WorkspaceQueryOptions {
  authority: QueryAuthority;
  view: WorkspaceView;
  scheduleVersion?: VersionReference;
  cursor?: string | null;
  pageSize?: number;
  correlationId?: string;
  filters?: Partial<WorkspaceQueryFilters>;
}

export interface WorkspaceQueryFilters {
  order_ids: string[];
  operation_ids: string[];
  resource_ids: string[];
  states: string[];
  start_at_or_after_utc: string | null;
  start_before_utc: string | null;
}

const emptyFilters: WorkspaceQueryFilters = {
  order_ids: [],
  operation_ids: [],
  resource_ids: [],
  states: [],
  start_at_or_after_utc: null,
  start_before_utc: null,
};

function sortFor(view: WorkspaceView): JsonObject[] {
  if (view === "AUDIT") {
    return [
      { field: "OCCURRED_AT_UTC", direction: "ASC" },
      { field: "ITEM_ID", direction: "ASC" },
    ];
  }
  if (view === "GANTT") {
    return [
      { field: "START_AT_UTC", direction: "ASC" },
      { field: "ITEM_ID", direction: "ASC" },
    ];
  }
  if (view === "RESOURCE_LOAD") {
    return [
      { field: "RESOURCE_ID", direction: "ASC" },
      { field: "ITEM_ID", direction: "ASC" },
    ];
  }
  return [{ field: "ITEM_ID", direction: "ASC" }];
}

function queryKindFor(view: WorkspaceView): WorkspaceQueryDocument["query_kind"] {
  if (view === "AUDIT") return "AUDIT_LOG";
  if (view === "VERSION_COMPARISON") return "SCHEDULE_VERSION_COMPARISON";
  return "WORKSPACE_VIEW";
}

function filtersFor(options: WorkspaceQueryOptions): WorkspaceQueryFilters {
  const filters = { ...emptyFilters, ...options.filters };
  for (const field of ["order_ids", "operation_ids", "resource_ids", "states"] as const) {
    if (!Array.isArray(filters[field]) || filters[field].some((value) => typeof value !== "string" || value.length === 0)) {
      throw new Error(`Workspace filter ${field} requires non-empty strings`);
    }
  }
  return filters;
}

export async function buildWorkspaceQuery(
  options: WorkspaceQueryOptions,
): Promise<WorkspaceQueryDocument> {
  const { authority, scheduleVersion, view } = options;
  if (authority.dataPlane === "PRODUCTION" && authority.synthetic) {
    throw new Error("Production workspace query cannot be synthetic");
  }
  if (authority.synthetic && authority.syntheticProvenance === undefined) {
    throw new Error("Synthetic workspace query requires explicit provenance");
  }
  const pageSize = options.pageSize ?? 100;
  if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 500) {
    throw new Error("Workspace page size must be an integer from 1 through 500");
  }
  const isWorkspace = scheduleVersion === undefined;
  const document: JsonObject = {
    workspace_query_version: "workspace-query.v1",
    schema_set_version: "2.6.0",
    canonicalization_version: "canonical-json.v1",
    direction: "REQUEST",
    query_kind: queryKindFor(view),
    data_plane: authority.dataPlane,
    environment: authority.environment,
    synthetic: authority.synthetic,
    resource: {
      resource_type: isWorkspace ? "WORKSPACE" : "SCHEDULE_VERSION",
      resource_id: isWorkspace ? null : scheduleVersion.schedule_version_id,
    },
    view,
    schedule_version_precondition: isWorkspace ? null : scheduleVersion,
    sort: sortFor(view),
    filters: filtersFor(options) as unknown as JsonObject,
    page: { size: pageSize, cursor: options.cursor ?? null },
    query_fingerprint: `sha256:${"0".repeat(64)}`,
    correlation_id: options.correlationId ?? globalThis.crypto.randomUUID(),
    result: null,
  };
  if (authority.syntheticProvenance !== undefined) {
    document.synthetic_provenance = authority.syntheticProvenance;
  }
  document.query_fingerprint = await workspaceQueryFingerprint(document);
  return document as WorkspaceQueryDocument;
}
