import { sha256Fingerprint } from "../src/api/canonical";
import { buildWorkspaceQuery } from "../src/api/query";
import type {
  ArtifactReference,
  JsonObject,
  ScheduleLineage,
  ScheduleVersion,
  WorkspaceHttpResponse,
  WorkspacePayloadItem,
  WorkspaceQueryDocument,
  WorkspaceView,
} from "../src/api/types";

function artifact(name: string, digit: string): ArtifactReference {
  return {
    document_version: `${name}.v1`,
    artifact_id: `${name}-test-001`,
    fingerprint: `sha256:${digit.repeat(64)}`,
  };
}

export const testLineage: ScheduleLineage = {
  planning_run_id: "planning-run-test-001",
  snapshot: artifact("planning-snapshot", "1"),
  problem: artifact("planning-problem", "2"),
  planning_solution: artifact("planning-solution", "3"),
  validation_report: artifact("validation-report", "4"),
  kpi: artifact("kpi", "5"),
  solver_report: artifact("solver-report", "6"),
  code_commit: "3bca1cc10ebedc4d47227bafb2f3f66854ccb526",
};

export const testScheduleVersion: ScheduleVersion = {
  schedule_version_version: "schedule-version.v1",
  schema_set_version: "2.6.0",
  canonicalization_version: "canonical-json.v1",
  schedule_version_id: "schedule-version-test-001",
  revision: 1,
  state: "DRAFT",
  data_plane: "PRODUCTION",
  environment: "PRODUCTION",
  synthetic: false,
  synthetic_provenance: null,
  parent_schedule_version: null,
  source_kind: "VALIDATED_SOLUTION",
  lineage: testLineage,
  content: { assignments: [], locks: [] },
  content_fingerprint: `sha256:${"a".repeat(64)}`,
  validation: {
    status: "PASS",
    hard_violation_count: 0,
    validated_at_utc: "2026-08-25T01:02:03Z",
  },
  decision: null,
  publication: null,
  superseded_by: null,
  allowed_actions: ["view"],
  created_at_utc: "2026-08-25T01:03:04Z",
  created_by_actor_ref: "actor:test-reader",
};

export const syntheticProvenance: JsonObject = {
  scenario_id: "SIM-P3-HUMAN-CONTROL-001",
  scenario_version: "1.0.0",
  seed: 20260826,
  factory_profile_id: "PROFILE-P3-UI-E2E-001",
  profile_version: "1.0.0",
  generator_id: "PLANTNEXUS-P3-UI-FIXTURE",
  generator_version: "1.0.0",
};

export const syntheticDraftVersion: ScheduleVersion = {
  ...testScheduleVersion,
  schedule_version_id: "schedule-version-sim-ui-001",
  data_plane: "SIMULATION",
  environment: "TEST",
  synthetic: true,
  synthetic_provenance: syntheticProvenance,
  allowed_actions: ["view", "edit", "lock", "audit"],
};

export const comparedScheduleVersion: ScheduleVersion = {
  ...testScheduleVersion,
  schedule_version_id: "schedule-version-test-002",
  revision: 2,
  state: "READY_FOR_REVIEW",
  parent_schedule_version: {
    schedule_version_id: testScheduleVersion.schedule_version_id,
    state: testScheduleVersion.state,
    content_fingerprint: testScheduleVersion.content_fingerprint,
  },
  content_fingerprint: `sha256:${"b".repeat(64)}`,
  created_at_utc: "2026-08-25T02:03:04Z",
};

export function ganttPayload(index = 0): JsonObject {
  const minute = String(index % 60).padStart(2, "0");
  return {
    operation_id: `operation-test-${index + 1}`,
    order_id: `order-test-${Math.floor(index / 3) + 1}`,
    resource_id: `resource-test-${(index % 4) + 1}`,
    resource_code: `M-${(index % 4) + 1}`,
    factory_id: "factory-test-1",
    workshop_id: `workshop-test-${(index % 2) + 1}`,
    production_line_id: null,
    resource_group_id: "resource-group-test-1",
    start_at_utc: `2026-08-25T01:${minute}:00Z`,
    end_at_utc: `2026-08-25T02:${minute}:00Z`,
    duration_seconds: 3600,
    start_tick: index * 60,
    end_tick: index * 60 + 60,
    lock_ids: [],
    execution_fact_ids: [],
  };
}

export const resourceLoadPayload: JsonObject = {
  resource_id: "resource-test-1",
  resource_code: "M-1",
  calendar_id: "calendar-test-1",
  start_at_utc: "2026-08-25T00:00:00Z",
  end_at_utc: "2026-08-26T00:00:00Z",
  bucket_kind: "PLANNING_HORIZON",
  assignment_count: 4,
  planned_busy_seconds: 14400,
  available_seconds: 28800,
  utilization: 0.5,
};

export const comparisonPayload: JsonObject = {
  schedule_version_comparison_version: "schedule-version-comparison.v1",
  schema_set_version: "2.6.0",
  canonicalization_version: "canonical-json.v1",
  comparison_id: "comparison-test-001",
  data_plane: "PRODUCTION",
  environment: "PRODUCTION",
  synthetic: false,
  base_version: {
    schedule_version_id: testScheduleVersion.schedule_version_id,
    state: testScheduleVersion.state,
    content_fingerprint: testScheduleVersion.content_fingerprint,
  },
  compared_version: {
    schedule_version_id: comparedScheduleVersion.schedule_version_id,
    state: comparedScheduleVersion.state,
    content_fingerprint: comparedScheduleVersion.content_fingerprint,
  },
  query_fingerprint: `sha256:${"c".repeat(64)}`,
  operation_deltas: [
    {
      operation_id: "operation-test-1",
      change_kind: "START_SHIFT",
      base_resource_id: "resource-test-1",
      compared_resource_id: "resource-test-1",
      base_start_at_utc: "2026-08-25T01:00:00Z",
      compared_start_at_utc: "2026-08-25T01:30:00Z",
      base_end_at_utc: "2026-08-25T02:00:00Z",
      compared_end_at_utc: "2026-08-25T02:30:00Z",
    },
    {
      operation_id: "operation-test-2",
      change_kind: "UNCHANGED",
      base_resource_id: "resource-test-2",
      compared_resource_id: "resource-test-2",
      base_start_at_utc: "2026-08-25T02:00:00Z",
      compared_start_at_utc: "2026-08-25T02:00:00Z",
      base_end_at_utc: "2026-08-25T03:00:00Z",
      compared_end_at_utc: "2026-08-25T03:00:00Z",
    },
  ],
  kpi_deltas: [
    { metric: "WEIGHTED_TARDINESS", base_value: 10, compared_value: 5, delta: -5 },
  ],
  summary: {
    operation_count: 2,
    changed_operation_count: 1,
    added_operation_count: 0,
    removed_operation_count: 0,
    resource_changed_count: 0,
  },
  comparison_fingerprint: `sha256:${"d".repeat(64)}`,
  generated_at_utc: "2026-08-25T03:04:05Z",
};

export async function workspaceResponse(
  view: WorkspaceView = "DATA_HEALTH",
  options: {
    found?: boolean;
    payloads?: JsonObject[];
    freshness?: string;
    scheduleVersion?: ScheduleVersion;
    itemType?: string;
    request?: WorkspaceQueryDocument;
  } = {},
): Promise<WorkspaceHttpResponse> {
  const found = options.found ?? true;
  const payloads = options.payloads ?? [{ status: "HEALTHY", observed_at_utc: "2026-08-25T01:00:00Z" }];
  const items: WorkspacePayloadItem[] = [];
  for (let index = 0; index < payloads.length; index += 1) {
    const payload = payloads[index];
    if (payload === undefined) continue;
    items.push({
      item_id: `item-test-${index + 1}`,
      item_type:
        options.itemType ??
        (view === "GANTT"
          ? "GANTT_SEGMENT"
          : view === "RESOURCE_LOAD"
            ? "RESOURCE_LOAD"
            : view === "VERSION_COMPARISON"
              ? "VERSION_COMPARISON"
              : view),
      payload,
      payload_fingerprint: await sha256Fingerprint(payload),
    });
  }
  const request = options.request ?? await buildWorkspaceQuery({
    authority: {
      dataPlane: "PRODUCTION",
      environment: "PRODUCTION",
      synthetic: false,
    },
    view,
    scheduleVersion: options.scheduleVersion,
    correlationId: "correlation-frontend-test-001",
  });
  const carrierItems = items.map(({ item_id, item_type, payload_fingerprint }) => ({
    item_id,
    item_type,
    payload_fingerprint,
  }));
  const result = {
    result_version: "workspace-query-result.v1",
    found,
    authoritative_schedule_version:
      options.scheduleVersion === undefined
        ? null
        : {
            schedule_version_id: options.scheduleVersion.schedule_version_id,
            state: options.scheduleVersion.state,
            content_fingerprint: options.scheduleVersion.content_fingerprint,
          },
    lineage: options.scheduleVersion?.lineage ?? null,
    items: carrierItems,
    next_cursor: null,
    observed_count: items.length,
    allowed_actions: [] as JsonObject[],
    freshness: options.freshness ?? "FRESH",
    generated_at_utc: "2026-08-25T01:04:05Z",
  };
  const document = {
    ...request,
    direction: "RESULT",
    result,
  } as WorkspaceQueryDocument;
  return {
    document,
    items,
    collection_fingerprint: found
      ? await sha256Fingerprint({ items: carrierItems })
      : null,
    source_fingerprint: found
      ? await sha256Fingerprint({ source: "frontend-test" })
      : null,
    correlation_id: request.correlation_id,
  };
}
