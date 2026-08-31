import { sha256Fingerprint } from "../src/api/canonical";
import type { JsonObject } from "../src/api/types";
import type {
  DynamicReplanningEnvelope,
  ExecutionEventType,
  PlanningRunState,
  ReplanAttemptAction,
  ReplanningQueryDocument,
  ReplanningWorkspaceIdentity,
} from "../src/features/replanning/types";

export const p4Runtime = {
  apiBaseUrl: "/api/v1",
  dataPlane: "SIMULATION",
  environment: "TEST",
  synthetic: true,
  syntheticProvenance: {
    scenario_id: "SIM-P4-REPLANNING-UI-001",
    scenario_version: "1.0.0",
  },
} as const;

export const p4Fingerprint = (digit: string) => `sha256:${digit.repeat(64)}`;
export const p4RequestId = `replan-request-${"8".repeat(64)}`;
export const p4AttemptId = `replan-attempt-${"a".repeat(64)}`;
export const p4ReportId = `change-report-${"7".repeat(64)}`;

export const p4Identity: ReplanningWorkspaceIdentity = {
  planningScopeId: "planning-scope-p4-ui-001",
  authorityId: "authority-p4-ui-001",
  streamId: "execution-stream-p4-ui-001",
  streamVersion: "1.0.0",
  fromPosition: 1,
  throughPosition: 2,
  requestId: p4RequestId,
  requestFingerprint: p4Fingerprint("8"),
  attemptId: p4AttemptId,
};

const provenance = {
  scenario_id: "SIM-P4-REPLANNING-UI-001",
  scenario_version: "1.0.0",
  factory_profile_id: "PROFILE-P4-REPLANNING-UI-001",
  profile_version: "1.0.0",
  generator_id: "PLANTNEXUS-P4-PLAYWRIGHT",
  generator_version: "1.0.0",
  simulator_id: "PLANTNEXUS-EXECUTION-SIMULATOR",
  simulator_version: "1.0.0",
  seed: 20260831,
};

const freeze = {
  freeze_policy_version: "freeze-policy.v1",
  freeze_policy_id: "FREEZE-POLICY-P4-UI-001",
  freeze_policy_revision: "1.0.0",
  freeze_policy_fingerprint: p4Fingerprint("6"),
  source: {
    source_system: "plantnexus-synthetic-policy",
    source_version: "1.0.0",
    source_record_id: "SIM-P4-REPLANNING-UI-001",
  },
  window_seconds: 900,
  effective_from_utc: "2026-08-31T06:00:00Z",
  effective_until_utc: "2026-08-31T06:15:00Z",
  interval_semantics: "HALF_OPEN_START_INCLUSIVE_END_EXCLUSIVE",
  effective_lock_ids: ["lock-p4-ui-freeze-001"],
};

const beforeKpi = {
  document_version: "kpi.v2",
  artifact_id: "kpi-before-p4-ui-001",
  fingerprint: p4Fingerprint("4"),
};
const afterKpi = {
  document_version: "kpi.v2",
  artifact_id: "kpi-after-p4-ui-001",
  fingerprint: p4Fingerprint("5"),
};
const newVersion = {
  schedule_version_version: "schedule-version.v2",
  schedule_version_id: "schedule-version-p4-ui-draft-001",
  state: "DRAFT",
  content_fingerprint: p4Fingerprint("d"),
};

async function boundProjection(value: JsonObject): Promise<JsonObject> {
  return { ...value, projection_fingerprint: await sha256Fingerprint(value) };
}

function envelope(
  query: ReplanningQueryDocument,
  operation: string,
  resourceType: string,
  result: JsonObject,
): DynamicReplanningEnvelope<JsonObject> {
  return {
    response_version: "dynamic-replanning-response.v1",
    operation,
    resource_type: resourceType,
    resource_id: query.resource_id,
    result,
    replayed: false,
    correlation_id: query.correlation_id,
  };
}

export function p4Event(position: number, eventType: ExecutionEventType) {
  const idDigit = String(position % 10);
  return {
    execution_event_version: "execution-event.v1",
    schema_set_version: "2.8.0",
    canonicalization_version: "canonical-json.v1",
    event_id: `execution-event-${idDigit.repeat(64)}`,
    event_type: eventType,
    data_plane: "SIMULATION",
    environment: "TEST",
    factory_id: "factory-p4-ui-001",
    planning_scope_id: p4Identity.planningScopeId,
    authority: {
      authority_version: "execution-event-authority.v1",
      authority_id: p4Identity.authorityId,
      authority_scope: `SIMULATION/factory-p4-ui-001/${p4Identity.planningScopeId}`,
      source: {
        source_system: "plantnexus-execution-simulator",
        source_version: "1.0.0",
        source_record_id: "SIM-P4-REPLANNING-UI-001",
      },
      decision: "AUTHORIZED_SIMULATION_SOURCE",
      production_binding: false,
    },
    source_stream: {
      stream_id: p4Identity.streamId,
      stream_version: p4Identity.streamVersion,
      authority_id: p4Identity.authorityId,
    },
    source_position: position,
    occurred_at_utc: `2026-08-31T06:0${position - 1}:00Z`,
    received_at_utc: `2026-08-31T06:0${position - 1}:05Z`,
    entity_refs: [{ entity_type: "RESOURCE", entity_id: "resource-p4-ui-001" }],
    payload: {
      kind: eventType,
      resource_id: "resource-p4-ui-001",
      observation: eventType,
    },
    synthetic: true,
    synthetic_provenance: provenance,
    production_binding: false,
    correlation_id: `correlation-p4-event-${position}`,
    event_fingerprint: p4Fingerprint(idDigit),
  };
}

export function p4ReplanRequest(
  events = [p4Event(1, "MACHINE_UNAVAILABLE"), p4Event(2, "MACHINE_RECOVERED")],
) {
  return {
    replan_request_version: "replan-request.v1",
    schema_set_version: "2.8.0",
    canonicalization_version: "canonical-json.v1",
    request_id: p4RequestId,
    data_plane: "SIMULATION",
    environment: "TEST",
    factory_id: "factory-p4-ui-001",
    planning_scope_id: p4Identity.planningScopeId,
    base_schedule_version: {
      schedule_version_version: "schedule-version.v1",
      schedule_version_id: "schedule-version-p4-ui-published-001",
      state: "PUBLISHED",
      content_fingerprint: p4Fingerprint("b"),
    },
    base_snapshot: {
      document_version: "planning-snapshot.v2",
      artifact_id: "snapshot-p4-ui-base",
      fingerprint: p4Fingerprint("1"),
    },
    base_problem: {
      document_version: "planning-problem.v2",
      artifact_id: "problem-p4-ui-base",
      fingerprint: p4Fingerprint("2"),
    },
    new_snapshot: {
      document_version: "planning-snapshot.v2",
      artifact_id: "snapshot-p4-ui-new",
      fingerprint: p4Fingerprint("3"),
    },
    new_snapshot_cutoff_at_utc: "2026-08-31T06:01:00Z",
    new_problem: {
      document_version: "planning-problem.v2",
      artifact_id: "problem-p4-ui-new",
      fingerprint: p4Fingerprint("9"),
    },
    event_stream: {
      authority: { authority_id: p4Identity.authorityId },
      source_stream: {
        stream_id: p4Identity.streamId,
        stream_version: p4Identity.streamVersion,
      },
      from_position: 1,
      through_position: events.length,
      event_ids: events.map((item) => item.event_id),
      event_fingerprints: events.map((item) => item.event_fingerprint),
      stream_fingerprint: p4Fingerprint("3"),
      fact_checkpoint: {
        document_version: "execution-fact-checkpoint.v1",
        artifact_id: "fact-checkpoint-p4-ui-001",
        fingerprint: p4Fingerprint("4"),
      },
    },
    trigger_event_ids: [events[0]!.event_id],
    trigger_reason: "EXECUTION_FACT_CHANGED",
    freeze_resolution: freeze,
    planning_policy: {
      planning_policy_version: "planning-policy.v2",
      policy_id: "POLICY-P4-UI-001",
      policy_revision: "1.0.0",
      policy_fingerprint: p4Fingerprint("a"),
    },
    solve_limits: {
      solve_limits_version: "solve-limits.v1",
      limits_id: "LIMITS-P4-UI-001",
      limits_revision: "1.0.0",
      limits_fingerprint: p4Fingerprint("c"),
      max_wall_time_seconds: 30,
      max_workers: 1,
      random_seed: 20260831,
    },
    synthetic: true,
    synthetic_provenance: provenance,
    production_binding: false,
    requested_at_utc: "2026-08-31T06:01:06Z",
    correlation_id: "correlation-p4-request-ui-001",
    request_fingerprint: p4Fingerprint("8"),
  };
}

function changeReport() {
  const operations = [
    {
      operation_id: "operation-p4-ui-001",
      classification: "UNCHANGED",
      base_assignment: {
        operation_id: "operation-p4-ui-001",
        resource_id: "resource-p4-ui-001",
        start_at_utc: "2026-08-31T06:00:00Z",
        end_at_utc: "2026-08-31T06:05:00Z",
      },
      new_assignment: {
        operation_id: "operation-p4-ui-001",
        resource_id: "resource-p4-ui-001",
        start_at_utc: "2026-08-31T06:00:00Z",
        end_at_utc: "2026-08-31T06:05:00Z",
      },
      deltas: { resource_changed: false, absolute_start_shift_seconds: 0 },
      reasons: [{ reason_code: "NO_CHANGE", evidence_refs: [] }],
    },
    {
      operation_id: "operation-p4-ui-002",
      classification: "CHANGED",
      base_assignment: {
        operation_id: "operation-p4-ui-002",
        resource_id: "resource-p4-ui-002",
        start_at_utc: "2026-08-31T06:05:00Z",
        end_at_utc: "2026-08-31T06:10:00Z",
      },
      new_assignment: {
        operation_id: "operation-p4-ui-002",
        resource_id: "resource-p4-ui-003",
        start_at_utc: "2026-08-31T06:10:00Z",
        end_at_utc: "2026-08-31T06:15:00Z",
      },
      deltas: { resource_changed: true, absolute_start_shift_seconds: 300 },
      reasons: [{ reason_code: "MACHINE_UNAVAILABLE", evidence_refs: [] }],
    },
  ];
  return {
    change_report_version: "change-report.v1",
    schema_set_version: "2.8.0",
    canonicalization_version: "canonical-json.v1",
    report_id: p4ReportId,
    report_fingerprint: p4Fingerprint("7"),
    data_plane: "SIMULATION",
    environment: "TEST",
    synthetic: true,
    synthetic_provenance: provenance,
    production_binding: false,
    base_schedule_version: p4ReplanRequest().base_schedule_version,
    new_schedule_version: newVersion,
    lineage: {
      replan_request: {
        request_id: p4RequestId,
        request_fingerprint: p4Fingerprint("8"),
      },
      planning_run_id: "planning-run-p4-ui-001",
    },
    freeze_evidence: freeze,
    before_kpi: beforeKpi,
    after_kpi: afterKpi,
    operation_universe_count: 2,
    operations,
    stability: {
      soft_lock_violations: 0,
      changed_existing_operations: 1,
      resource_changes: 1,
      absolute_start_shift_seconds: 300,
      unchanged_existing: 1,
      comparable_existing: 2,
      unchanged_ratio: { status: "APPLICABLE", numerator: 1, denominator: 2 },
    },
    generated_at_utc: "2026-08-31T06:01:10Z",
    correlation_id: "correlation-p4-change-ui-001",
  };
}

export async function responseForQuery(
  query: ReplanningQueryDocument,
  state: PlanningRunState = "COMPLETED",
  allowedActions: ReplanAttemptAction[] = [],
  timelineEvents = [
    p4Event(1, "MACHINE_UNAVAILABLE"),
    p4Event(2, "MACHINE_RECOVERED"),
  ],
): Promise<DynamicReplanningEnvelope<JsonObject>> {
  const boundary = {
    query_fingerprint: query.query_fingerprint,
    data_plane: "SIMULATION",
    environment: "TEST",
    synthetic: true,
    production_binding: false,
  } as const;
  if (query.query_kind === "EXECUTION_EVENT_STREAM") {
    return envelope(
      query,
      "LIST_EXECUTION_EVENTS",
      "EXECUTION_EVENT_STREAM",
      await boundProjection({
        result_version: "execution-event-timeline.v1",
        ...boundary,
        planning_scope_id: p4Identity.planningScopeId,
        authority_id: p4Identity.authorityId,
        stream_id: p4Identity.streamId,
        stream_version: p4Identity.streamVersion,
        from_position: query.from_position,
        through_position: query.through_position,
        events: timelineEvents,
        next_cursor: null,
        allowed_actions: ["view"],
      }),
    );
  }
  if (query.query_kind === "REPLAN_REQUEST") {
    return envelope(
      query,
      "GET_REPLAN_REQUEST",
      "REPLAN_REQUEST",
      await boundProjection({
        result_version: "replan-request-workspace.v1",
        ...boundary,
        request: p4ReplanRequest(timelineEvents),
        attempt: {
          attempt_id: p4AttemptId,
          attempt_number: 1,
          planning_run_id: "planning-run-p4-ui-001",
          state,
          allowed_actions: allowedActions,
          updated_at_utc: "2026-08-31T06:01:09Z",
        },
      }),
    );
  }
  if (query.query_kind === "REPLAN_RESULT") {
    const completed = state === "COMPLETED";
    return envelope(
      query,
      "GET_REPLAN_RESULT",
      "REPLAN_RESULT",
      await boundProjection({
        result_version: "replan-result-workspace.v1",
        ...boundary,
        request_id: p4RequestId,
        request_fingerprint: p4Fingerprint("8"),
        attempt_id: p4AttemptId,
        attempt_number: 1,
        planning_run_id: "planning-run-p4-ui-001",
        planning_run_state: state,
        new_schedule_version: completed ? newVersion : null,
        change_report: completed
          ? {
              change_report_version: "change-report.v1",
              report_id: p4ReportId,
              report_fingerprint: p4Fingerprint("7"),
            }
          : null,
        failure_reason: state === "FAILED" ? "SYSTEM_ERROR" : null,
        correlation_id: query.correlation_id,
      }),
    );
  }
  return envelope(
    query,
    "GET_CHANGE_REPORT",
    "CHANGE_REPORT",
    await boundProjection({
      result_version: "change-report-workspace.v1",
      read_model_version: "change-report-read-model.v1",
      ...boundary,
      report: changeReport(),
      tardiness: {
        metric: "priority_weighted_tardiness_seconds",
        before_seconds: 600,
        after_seconds: 300,
        delta_seconds: -300,
        before_kpi: beforeKpi,
        after_kpi: afterKpi,
      },
      next_cursor: null,
      publishable: false,
    }),
  );
}
