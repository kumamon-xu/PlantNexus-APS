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
}

function sortFor(view: WorkspaceView): JsonObject[] {
  if (view === "AUDIT") {
    return [
      { field: "OCCURRED_AT_UTC", direction: "ASC" },
      { field: "ITEM_ID", direction: "ASC" },
    ];
  }
  return [{ field: "ITEM_ID", direction: "ASC" }];
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
    query_kind: "WORKSPACE_VIEW",
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
    filters: {
      order_ids: [],
      operation_ids: [],
      resource_ids: [],
      states: [],
      start_at_or_after_utc: null,
      start_before_utc: null,
    },
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
