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
  code_commit: "26dd519b1f1f84e08d415cfdfce43f286fa82988",
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

export async function workspaceResponse(
  view: WorkspaceView = "DATA_HEALTH",
  options: { found?: boolean; payloads?: JsonObject[]; freshness?: string } = {},
): Promise<WorkspaceHttpResponse> {
  const found = options.found ?? true;
  const payloads = options.payloads ?? [{ status: "HEALTHY", observed_at_utc: "2026-08-25T01:00:00Z" }];
  const items: WorkspacePayloadItem[] = [];
  for (let index = 0; index < payloads.length; index += 1) {
    const payload = payloads[index];
    if (payload === undefined) continue;
    items.push({
      item_id: `item-test-${index + 1}`,
      item_type: view,
      payload,
      payload_fingerprint: await sha256Fingerprint(payload),
    });
  }
  const request = await buildWorkspaceQuery({
    authority: {
      dataPlane: "PRODUCTION",
      environment: "PRODUCTION",
      synthetic: false,
    },
    view,
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
    authoritative_schedule_version: null,
    lineage: null,
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
    correlation_id: "correlation-frontend-test-001",
  };
}
