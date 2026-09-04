import type {
  DemoBootstrap,
  DemoComparisonView,
  DemoFactoryView,
  DemoJob,
  DemoScheduleView,
  DemoScheduleSummary,
  ScenarioManifest,
} from "../src/api/types";

const runId = "run-11111111111111111111111111111111";
const versionId = "schedule-version-demo-11111111111111111111111111111111";
const fingerprint = `sha256:${"1".repeat(64)}`;
const draftVersionId = "schedule-version-demo-draft-22222222222222222222222222222222";

export const presentationConfiguration: DemoBootstrap["configuration"] = {
  configuration_version: "cnc-demo-presentation-configuration.v1",
  factory_timezone: "Asia/Shanghai",
  route_template_version: "cnc-route-templates.v1",
  route_templates: [
    { template_id: "CNC-ROUTE-3", product_family_zh: "短轴类", operation_count: 3, operation_names_zh: ["锯切下料", "数控车削", "终检"] },
    { template_id: "CNC-ROUTE-4", product_family_zh: "法兰类", operation_count: 4, operation_names_zh: ["锯切下料", "数控车削", "铣削加工", "终检"] },
    { template_id: "CNC-ROUTE-5", product_family_zh: "精密套筒类", operation_count: 5, operation_names_zh: ["锯切下料", "数控车削", "铣削加工", "精密磨削", "终检"] },
    { template_id: "CNC-ROUTE-6", product_family_zh: "复杂壳体类", operation_count: 6, operation_names_zh: ["锯切下料", "数控车削", "粗铣", "五轴精铣", "精密磨削", "终检"] },
  ],
  priority_policy_version: "cnc-demo-priority-policy.v1",
  priority_classes: [
    { class_id: "NORMAL", label_zh: "普通", priority_weight: 1 },
    { class_id: "KEY", label_zh: "重点", priority_weight: 4 },
    { class_id: "URGENT", label_zh: "加急", priority_weight: 12 },
  ],
};

export const scenarioManifest: ScenarioManifest = {
  manifest_version: "cnc-demo-scenario-manifest.v1",
  run_id: runId,
  scenario_id: "CNC-DEMO-SMOKE",
  scenario_version: "1.0.0",
  profile_name: "smoke",
  seed: 20260902,
  assets_digest: "assets-demo-digest",
  dataset_hash: fingerprint,
  snapshot_id: "planning-snapshot-demo",
  snapshot_hash: fingerprint,
  problem_hash: fingerprint,
  horizon_start_utc: "2026-09-06T22:00:00Z",
  horizon_end_utc: "2026-09-13T22:00:00Z",
  initial_solve_seconds: 5,
  replan_solve_seconds: 8,
  source_counts: {
    demand_orders: 24,
    routing_operations: 108,
    resources: 12,
    workshops: 3,
    execution_facts: 9,
    operation_locks: 3,
  },
  problem_counts: {
    orders: 24,
    active_operations: 102,
    resources: 12,
    running_operations: 3,
    hard_locks: 1,
    soft_locks: 2,
    unavailable_intervals: 231,
  },
};

export function emptyBootstrap(): DemoBootstrap {
  return {
    bootstrap_version: "cnc-demo-bootstrap.v1",
    story_state: "EMPTY",
    run: null,
    active_job: null,
    schedule_version: null,
    current_publication: null,
    scenario_manifest: null,
    comparison_reference: null,
    configuration: presentationConfiguration,
    simulation_only: true,
    production_authority: false,
    correlation_id: "correlation-demo-empty",
    active_run_id: null,
  };
}

export function initializedBootstrap(): DemoBootstrap {
  return {
    ...emptyBootstrap(),
    story_state: "INITIALIZED",
    run: {
      run_id: runId,
      scenario_id: "CNC-DEMO-SMOKE",
      seed: 20260902,
      status: "ACTIVE",
      created_at_utc: "2026-09-02T08:00:00Z",
    },
    scenario_manifest: scenarioManifest,
    active_run_id: runId,
    correlation_id: "correlation-demo-initialized",
  };
}

export function readyBootstrap(): DemoBootstrap {
  return {
    ...initializedBootstrap(),
    story_state: "READY_FOR_REVIEW",
    schedule_version: {
      schedule_version_id: versionId,
      state: "READY_FOR_REVIEW",
      content_fingerprint: fingerprint,
    },
  };
}

export function publishedBootstrap(): DemoBootstrap {
  return {
    ...readyBootstrap(),
    story_state: "BASELINE_PUBLISHED",
    schedule_version: {
      schedule_version_id: versionId,
      state: "PUBLISHED",
      content_fingerprint: fingerprint,
    },
    current_publication: {
      schedule_version_id: versionId,
      content_fingerprint: fingerprint,
      publication_id: "publication-demo-1",
      reference_revision: 1,
    },
  };
}

export function comparisonBootstrap(): DemoBootstrap {
  return {
    ...publishedBootstrap(),
    story_state: "DRAFT_COMPARISON_READY",
    schedule_version: {
      schedule_version_id: draftVersionId,
      state: "DRAFT",
      content_fingerprint: fingerprint,
    },
    comparison_reference: {
      request_id: "replan-request-demo-1",
      before_schedule_version_id: versionId,
      after_schedule_version_id: draftVersionId,
      change_report_id: "change-report-demo-1",
      demand_order_id: "order-demo-urgent",
    },
  };
}

export function scheduleSummary(state: "READY_FOR_REVIEW" | "APPROVED" | "PUBLISHED" = "READY_FOR_REVIEW"): DemoScheduleSummary {
  return {
    view_version: "cnc-demo-schedule-view.v1",
    run_id: runId,
    scenario_id: "CNC-DEMO-SMOKE",
    timezone: "Asia/Shanghai",
    version: {
      schedule_version_id: versionId,
      contract_version: "schedule-version.v1",
      revision: state === "READY_FOR_REVIEW" ? 1 : state === "APPROVED" ? 2 : 3,
      state,
      content_fingerprint: fingerprint,
      created_at: {
        utc: "2026-09-02T08:01:00Z",
        local: "2026-09-02T16:01:00+08:00",
      },
    },
    solver: {
      solver_status: "OPTIMAL",
      limit_seconds: 5,
      solve_seconds: 0.14,
      total_seconds: 0.31,
      optimality_claim: true,
    },
    validation: {
      status: "PASS",
      hard_violation_count: 0,
      fingerprint,
    },
    kpis: {
      fingerprint,
      delivery: {
        order_count: 24,
        on_time_order_count: 22,
        on_time_order_ratio: 22 / 24,
        late_order_count: 2,
        total_tardiness_seconds: 1800,
      },
      planning: {
        makespan_seconds: 230400,
        scheduled_operation_count: 102,
        unscheduled_operation_count: 0,
      },
    },
    boundary: {
      data_plane: "SIMULATION",
      simulation_only: true,
      production_authority: false,
      publishable: false,
    },
    view_fingerprint: fingerprint,
  };
}

const resourceOneId = "resource-demo-lathe-01";
const resourceTwoId = "resource-demo-cmm-01";
const workshopId = "workshop-demo-ws10";

export function factoryView(): DemoFactoryView {
  return {
    view_version: "cnc-demo-factory-view.v1",
    run_id: runId,
    scenario_id: "CNC-DEMO-SMOKE",
    profile_name: "smoke",
    seed: 20260902,
    horizon_start: {
      utc: "2026-09-06T22:00:00Z",
      local: "2026-09-07T06:00:00+08:00",
    },
    horizon_end: {
      utc: "2026-09-13T22:00:00Z",
      local: "2026-09-14T06:00:00+08:00",
    },
    factory: {
      factory_id: "factory-demo-1",
      source_factory_id: "factory-cnc-1",
      factory_code: "CNC-F01",
      factory_name: "华东精密制造一厂",
      timezone: "Asia/Shanghai",
      workshops: [
        {
          workshop_id: workshopId,
          source_workshop_id: "workshop-ws10",
          workshop_code: "WS10",
          workshop_name: "精密车削车间",
          production_line: {
            production_line_id: "line-demo-1",
            source_production_line_id: "line-cnc-1",
            production_line_code: "LINE-10",
            resource_groups: [
              {
                resource_group_id: "group-demo-1",
                source_resource_group_id: "group-cnc-1",
                resource_group_code: "RG-10",
                resources: [
                  {
                    resource_id: resourceOneId,
                    source_resource_id: "resource-lathe-01",
                    resource_code: "LATHE-01",
                    resource_name: "数控车床 01",
                    family: "LATHE",
                    status: "ACTIVE",
                    capabilities: ["TURNING"],
                    calendar_id: "calendar-lathe-01",
                    unavailable_intervals: [
                      {
                        interval_id: "interval-shift-1",
                        kind: "SHIFT",
                        reason: "夜班外非工作时段",
                        start: {
                          utc: "2026-09-07T14:00:00Z",
                          local: "2026-09-07T22:00:00+08:00",
                        },
                        end: {
                          utc: "2026-09-07T22:00:00Z",
                          local: "2026-09-08T06:00:00+08:00",
                        },
                      },
                    ],
                  },
                  {
                    resource_id: resourceTwoId,
                    source_resource_id: "resource-cmm-01",
                    resource_code: "CMM-01",
                    resource_name: "三坐标测量机 01",
                    family: "INSPECTION",
                    status: "ACTIVE",
                    capabilities: ["INSPECTION"],
                    calendar_id: "calendar-cmm-01",
                    unavailable_intervals: [
                      {
                        interval_id: "interval-maintenance-1",
                        kind: "MAINTENANCE",
                        reason: "预防性保养",
                        start: {
                          utc: "2026-09-08T04:00:00Z",
                          local: "2026-09-08T12:00:00+08:00",
                        },
                        end: {
                          utc: "2026-09-08T07:00:00Z",
                          local: "2026-09-08T15:00:00+08:00",
                        },
                      },
                    ],
                  },
                ],
              },
            ],
          },
        },
      ],
    },
    maintenance_events: [
      {
        event_id: "maintenance-demo-1",
        resource_id: resourceTwoId,
        source_resource_id: "resource-cmm-01",
        resource_code: "CMM-01",
        reason: "预防性保养",
        start: {
          utc: "2026-09-08T04:00:00Z",
          local: "2026-09-08T12:00:00+08:00",
        },
        end: {
          utc: "2026-09-08T07:00:00Z",
          local: "2026-09-08T15:00:00+08:00",
        },
      },
    ],
    counts: {
      workshops: 1,
      production_lines: 1,
      resource_groups: 1,
      resources: 2,
      maintenance_events: 1,
      unavailable_intervals: 2,
    },
    provenance: {
      asset_pack_version: "cnc-demo-assets.v1",
      asset_pack_fingerprint: fingerprint,
      snapshot: {
        document_version: "planning-snapshot.v2",
        artifact_id: "snapshot-demo-1",
        fingerprint,
      },
    },
    boundary: {
      data_plane: "SIMULATION",
      environment: "TEST",
      simulation_only: true,
      production_authority: false,
      publishable: false,
    },
    view_fingerprint: fingerprint,
  };
}

export function scheduleView(
  state: "READY_FOR_REVIEW" | "APPROVED" | "PUBLISHED" = "READY_FOR_REVIEW",
): DemoScheduleView {
  const summary = scheduleSummary(state);
  return {
    ...summary,
    version: {
      ...summary.version,
      source_kind: "VALIDATED_SOLUTION",
      parent_schedule_version_id: null,
    },
    solver: {
      ...summary.solver,
      solver_report_version: "solver-report.v1",
      report_id: "solver-report-demo-1",
      evidence_kind: "SOLVER_RUN",
      objective_value: 0,
      best_bound: 0,
      relative_gap: 0,
    },
    validation: {
      ...summary.validation,
      validation_report_version: "validation-report.v2",
    },
    kpis: {
      ...summary.kpis,
      kpi_id: "kpi-demo-1",
      kpi_version: "kpi.v2",
      delivery: {
        order_count: 2,
        on_time_order_count: 1,
        on_time_order_ratio: 0.5,
        late_order_count: 1,
        total_tardiness_seconds: 3600,
        priority_weighted_tardiness_seconds: 14400,
      },
      planning: {
        makespan_seconds: 93600,
        scheduled_operation_count: 3,
        unscheduled_operation_count: 0,
      },
      stability: {
        status: "NOT_APPLICABLE_NO_BASE_SCHEDULE",
        changed_operation_count: null,
        resource_changed_count: null,
        start_shift_seconds: null,
        schedule_stability_ratio: null,
      },
    },
    orders: [
      {
        demand_order_id: "order-demo-1",
        order_code: "CNC-001",
        product_code: "SHAFT-A",
        quantity: 20,
        quantity_unit: "件",
        priority_class: "KEY",
        priority_weight: 4,
        release_at: {
          utc: "2026-09-06T22:00:00Z",
          local: "2026-09-07T06:00:00+08:00",
        },
        material_ready_at: {
          utc: "2026-09-06T22:00:00Z",
          local: "2026-09-07T06:00:00+08:00",
        },
        due_at: {
          utc: "2026-09-08T00:00:00Z",
          local: "2026-09-08T08:00:00+08:00",
        },
        completion_at: {
          utc: "2026-09-08T01:00:00Z",
          local: "2026-09-08T09:00:00+08:00",
        },
        tardiness_seconds: 3600,
        on_time: false,
        operation_count: 3,
        scheduled_operation_count: 2,
        completed_operation_count: 1,
        running_operation_count: 1,
      },
      {
        demand_order_id: "order-demo-2",
        order_code: "CNC-002",
        product_code: "HOUSING-B",
        quantity: 12,
        quantity_unit: "件",
        priority_class: "URGENT",
        priority_weight: 12,
        release_at: {
          utc: "2026-09-06T22:00:00Z",
          local: "2026-09-07T06:00:00+08:00",
        },
        material_ready_at: {
          utc: "2026-09-07T00:00:00Z",
          local: "2026-09-07T08:00:00+08:00",
        },
        due_at: {
          utc: "2026-09-09T00:00:00Z",
          local: "2026-09-09T08:00:00+08:00",
        },
        completion_at: {
          utc: "2026-09-08T20:00:00Z",
          local: "2026-09-09T04:00:00+08:00",
        },
        tardiness_seconds: 0,
        on_time: true,
        operation_count: 1,
        scheduled_operation_count: 1,
        completed_operation_count: 0,
        running_operation_count: 0,
      },
    ],
    resources: [
      {
        resource_id: resourceOneId,
        source_resource_id: "resource-lathe-01",
        resource_code: "LATHE-01",
        resource_name: "数控车床 01",
        workshop_id: workshopId,
        workshop_code: "WS10",
        available_seconds: 172800,
        planned_busy_seconds: 129600,
        utilization: 0.75,
        formula: "planned_busy_seconds / available_seconds",
        evidence: {
          document_version: "planning-solution.v1",
          artifact_id: "solution-demo-1",
          fingerprint,
        },
      },
      {
        resource_id: resourceTwoId,
        source_resource_id: "resource-cmm-01",
        resource_code: "CMM-01",
        resource_name: "三坐标测量机 01",
        workshop_id: workshopId,
        workshop_code: "WS10",
        available_seconds: 162000,
        planned_busy_seconds: 64800,
        utilization: 0.4,
        formula: "planned_busy_seconds / available_seconds",
        evidence: {
          document_version: "planning-solution.v1",
          artifact_id: "solution-demo-1",
          fingerprint,
        },
      },
    ],
    execution_segments: [
      {
        execution_fact_id: "fact-completed-demo-1",
        operation_id: "operation-completed-demo-1",
        demand_order_id: "order-demo-1",
        resource_id: resourceOneId,
        resource_code: "LATHE-01",
        status: "COMPLETED",
        actual_start: {
          utc: "2026-09-06T18:00:00Z",
          local: "2026-09-07T02:00:00+08:00",
        },
        actual_end: {
          utc: "2026-09-06T18:30:00Z",
          local: "2026-09-07T02:30:00+08:00",
        },
        remaining_seconds: null,
      },
      {
        execution_fact_id: "fact-running-demo-1",
        operation_id: "operation-running-demo-1",
        demand_order_id: "order-demo-1",
        resource_id: resourceOneId,
        resource_code: "LATHE-01",
        status: "RUNNING",
        actual_start: {
          utc: "2026-09-06T21:00:00Z",
          local: "2026-09-07T05:00:00+08:00",
        },
        actual_end: null,
        remaining_seconds: 1800,
      },
    ],
    assignments: [
      {
        operation_id: "operation-running-demo-1",
        operation_code: "TURN-001",
        operation_name: "精车",
        operation_sequence: 2,
        demand_order_id: "order-demo-1",
        order_code: "CNC-001",
        product_code: "SHAFT-A",
        resource_id: resourceOneId,
        source_resource_id: "resource-lathe-01",
        resource_code: "LATHE-01",
        resource_name: "数控车床 01",
        workshop_id: workshopId,
        source_workshop_id: "workshop-ws10",
        workshop_code: "WS10",
        workshop_name: "精密车削车间",
        start: {
          utc: "2026-09-06T22:00:00Z",
          local: "2026-09-07T06:00:00+08:00",
        },
        end: {
          utc: "2026-09-06T22:30:00Z",
          local: "2026-09-07T06:30:00+08:00",
        },
        duration_seconds: 1800,
        operation_state: "RUNNING",
        candidate_resource_count: 2,
        lock_ids: [],
        execution_fact_ids: [],
        protection: "RUNNING",
      },
      {
        operation_id: "operation-soft-demo-1",
        operation_code: "INSPECT-001",
        operation_name: "终检",
        operation_sequence: 3,
        demand_order_id: "order-demo-1",
        order_code: "CNC-001",
        product_code: "SHAFT-A",
        resource_id: resourceTwoId,
        source_resource_id: "resource-cmm-01",
        resource_code: "CMM-01",
        resource_name: "三坐标测量机 01",
        workshop_id: workshopId,
        source_workshop_id: "workshop-ws10",
        workshop_code: "WS10",
        workshop_name: "精密车削车间",
        start: {
          utc: "2026-09-07T02:00:00Z",
          local: "2026-09-07T10:00:00+08:00",
        },
        end: {
          utc: "2026-09-07T02:20:00Z",
          local: "2026-09-07T10:20:00+08:00",
        },
        duration_seconds: 1200,
        operation_state: "NOT_STARTED",
        candidate_resource_count: 1,
        lock_ids: ["lock-soft-demo-1"],
        execution_fact_ids: [],
        protection: "SOFT_LOCK",
      },
      {
        operation_id: "operation-hard-demo-2",
        operation_code: "TURN-002",
        operation_name: "粗车",
        operation_sequence: 1,
        demand_order_id: "order-demo-2",
        order_code: "CNC-002",
        product_code: "HOUSING-B",
        resource_id: resourceOneId,
        source_resource_id: "resource-lathe-01",
        resource_code: "LATHE-01",
        resource_name: "数控车床 01",
        workshop_id: workshopId,
        source_workshop_id: "workshop-ws10",
        workshop_code: "WS10",
        workshop_name: "精密车削车间",
        start: {
          utc: "2026-09-08T00:00:00Z",
          local: "2026-09-08T08:00:00+08:00",
        },
        end: {
          utc: "2026-09-08T00:40:00Z",
          local: "2026-09-08T08:40:00+08:00",
        },
        duration_seconds: 2400,
        operation_state: "NOT_STARTED",
        candidate_resource_count: 2,
        lock_ids: ["lock-hard-demo-2"],
        execution_fact_ids: [],
        protection: "HARD_LOCK",
      },
    ],
    query: {
      resource_ids: [],
      workshop_ids: [],
      demand_order_ids: [],
      states: [],
      start_at_utc: "2026-09-06T16:00:00.000Z",
      end_at_utc: "2026-09-09T16:00:00.000Z",
      sort: "START_ASC",
      offset: 0,
      limit: 160,
    },
    page: {
      offset: 0,
      limit: 160,
      returned: 3,
      filtered_total: 3,
      unfiltered_total: 3,
      has_more: false,
    },
    provenance: {
      planning_run_id: "planning-run-demo-1",
      schedule_content_fingerprint: fingerprint,
      artifacts: [
        {
          document_version: "planning-solution.v1",
          artifact_id: "solution-demo-1",
          fingerprint,
        },
        {
          document_version: "validation-report.v2",
          artifact_id: "validation-demo-1",
          fingerprint,
        },
      ],
    },
    boundary: {
      data_plane: "SIMULATION",
      environment: "TEST",
      simulation_only: true,
      production_authority: false,
      publishable: false,
    },
    view_fingerprint: fingerprint,
  };
}

export function runningPlanJob(): DemoJob {
  return {
    job_version: "cnc-demo-job.v1",
    job_id: "job-initial-plan-demo-1",
    job_kind: "INITIAL_PLAN",
    run_id: runId,
    status: "RUNNING",
    stage: "SOLVING",
    attempt: 1,
    result: null,
    error_code: null,
    created_at_utc: "2026-09-02T08:00:00Z",
    updated_at_utc: "2026-09-02T08:00:02Z",
    stages: [
      {
        attempt: 1,
        sequence: 1,
        stage: "GENERATING",
        status: "SUCCEEDED",
        started_at_utc: "2026-09-02T08:00:00Z",
        finished_at_utc: "2026-09-02T08:00:01Z",
        elapsed_seconds: 1,
        evidence_ref: null,
      },
      {
        attempt: 1,
        sequence: 4,
        stage: "SOLVING",
        status: "RUNNING",
        started_at_utc: "2026-09-02T08:00:02Z",
        finished_at_utc: null,
        elapsed_seconds: null,
        evidence_ref: null,
      },
    ],
    correlation_id: "correlation-demo-job",
    active_run_id: runId,
  };
}

export function completedResetJob(): DemoJob {
  return {
    ...runningPlanJob(),
    job_id: "job-reset-demo-1",
    job_kind: "RESET",
    status: "SUCCEEDED",
    stage: "COMPLETE",
    result: { run_id: runId },
    updated_at_utc: "2026-09-02T08:00:04Z",
    stages: [
      {
        attempt: 1,
        sequence: 1,
        stage: "MIGRATING",
        status: "SUCCEEDED",
        started_at_utc: "2026-09-02T08:00:00Z",
        finished_at_utc: "2026-09-02T08:00:01Z",
        elapsed_seconds: 1,
        evidence_ref: null,
      },
    ],
  };
}

export function comparisonView(): DemoComparisonView {
  const baseKpis: DemoComparisonView["before_kpis"] = {
    kpi_id: "kpi-demo-before",
    kpi_version: "kpi.v2",
    fingerprint,
    delivery: {
      order_count: 2,
      on_time_order_count: 1,
      on_time_order_ratio: 0.5,
      late_order_count: 1,
      total_tardiness_seconds: 3600,
      priority_weighted_tardiness_seconds: 14400,
    },
    planning: {
      makespan_seconds: 93600,
      scheduled_operation_count: 3,
      unscheduled_operation_count: 0,
    },
    stability: {
      status: "NOT_APPLICABLE_NO_BASE_SCHEDULE",
      changed_operation_count: null,
      resource_changed_count: null,
      start_shift_seconds: null,
      schedule_stability_ratio: null,
    },
  };
  const afterKpis: DemoComparisonView["after_kpis"] = {
    ...baseKpis,
    kpi_id: "kpi-demo-after",
    delivery: {
      order_count: 3,
      on_time_order_count: 2,
      on_time_order_ratio: 2 / 3,
      late_order_count: 1,
      total_tardiness_seconds: 5400,
      priority_weighted_tardiness_seconds: 21600,
    },
    planning: {
      makespan_seconds: 97200,
      scheduled_operation_count: 4,
      unscheduled_operation_count: 0,
    },
    stability: {
      status: "APPLICABLE",
      changed_operation_count: 1,
      resource_changed_count: 1,
      start_shift_seconds: 3600,
      schedule_stability_ratio: 0.5,
    },
  };
  return {
    view_version: "cnc-demo-comparison-view.v1",
    run_id: runId,
    scenario_id: "CNC-DEMO-SMOKE",
    request_id: "replan-request-demo-1",
    timezone: "Asia/Shanghai",
    before: {
      schedule_version_id: versionId,
      contract_version: "schedule-version.v1",
      revision: 3,
      state: "PUBLISHED",
      source_kind: "VALIDATED_SOLUTION",
      parent_schedule_version_id: null,
      content_fingerprint: fingerprint,
      created_at: {
        utc: "2026-09-02T08:01:00Z",
        local: "2026-09-02T16:01:00+08:00",
      },
    },
    after: {
      schedule_version_id: draftVersionId,
      contract_version: "schedule-version.v2",
      revision: 1,
      state: "DRAFT",
      source_kind: "DYNAMIC_REPLAN",
      parent_schedule_version_id: versionId,
      content_fingerprint: fingerprint,
      created_at: {
        utc: "2026-09-02T08:10:00Z",
        local: "2026-09-02T16:10:00+08:00",
      },
    },
    before_kpis: baseKpis,
    after_kpis: afterKpis,
    delivery_delta: {
      order_count: 1,
      on_time_order_count: 1,
      on_time_order_ratio: 1 / 6,
      late_order_count: 0,
      total_tardiness_seconds: 1800,
      priority_weighted_tardiness_seconds: 7200,
      makespan_seconds: 3600,
      formula: "after - before",
    },
    operation_universe_count: 3,
    change_counts: {
      unchanged: 1,
      changed: 1,
      added: 1,
      removed_by_fact: 0,
    },
    stability: {
      soft_lock_violations: 0,
      changed_existing_operations: 1,
      resource_changes: 1,
      absolute_start_shift_seconds: 3600,
      unchanged_existing: 1,
      comparable_existing: 2,
      unchanged_ratio: 0.5,
    },
    affected_orders: [
      { demand_order_id: "order-demo-1", order_code: "CNC-001", change_count: 1 },
      { demand_order_id: "order-demo-urgent", order_code: "CNC-URGENT-001", change_count: 1 },
    ],
    operations: [
      {
        operation_id: "operation-changed-demo-1",
        operation_code: "TURN-001",
        operation_name: "数控车削",
        demand_order_id: "order-demo-1",
        order_code: "CNC-001",
        classification: "CHANGED",
        base_assignment: {
          resource_id: resourceOneId,
          source_resource_id: "resource-lathe-01",
          resource_code: "LATHE-01",
          workshop_id: workshopId,
          workshop_code: "WS10",
          start: { utc: "2026-09-07T00:00:00Z", local: "2026-09-07T08:00:00+08:00" },
          end: { utc: "2026-09-07T01:00:00Z", local: "2026-09-07T09:00:00+08:00" },
          duration_seconds: 3600,
        },
        new_assignment: {
          resource_id: resourceTwoId,
          source_resource_id: "resource-cmm-01",
          resource_code: "CMM-01",
          workshop_id: workshopId,
          workshop_code: "WS10",
          start: { utc: "2026-09-07T01:00:00Z", local: "2026-09-07T09:00:00+08:00" },
          end: { utc: "2026-09-07T02:00:00Z", local: "2026-09-07T10:00:00+08:00" },
          duration_seconds: 3600,
        },
        deltas: {
          resource_changed: true,
          start_shift_seconds: 3600,
          absolute_start_shift_seconds: 3600,
          end_shift_seconds: 3600,
          duration_delta_seconds: 0,
        },
        reason_codes: ["RESOURCE_CHANGED", "START_TIME_CHANGED"],
      },
      {
        operation_id: "operation-added-demo-1",
        operation_code: "CUT-URGENT",
        operation_name: "锯切下料",
        demand_order_id: "order-demo-urgent",
        order_code: "CNC-URGENT-001",
        classification: "ADDED",
        base_assignment: null,
        new_assignment: {
          resource_id: resourceOneId,
          source_resource_id: "resource-lathe-01",
          resource_code: "LATHE-01",
          workshop_id: workshopId,
          workshop_code: "WS10",
          start: { utc: "2026-09-07T03:00:00Z", local: "2026-09-07T11:00:00+08:00" },
          end: { utc: "2026-09-07T03:30:00Z", local: "2026-09-07T11:30:00+08:00" },
          duration_seconds: 1800,
        },
        deltas: {
          resource_changed: false,
          start_shift_seconds: 0,
          absolute_start_shift_seconds: 0,
          end_shift_seconds: 0,
          duration_delta_seconds: 1800,
        },
        reason_codes: ["URGENT_ORDER_ADDED"],
      },
    ],
    query: {
      classifications: ["ADDED", "CHANGED", "REMOVED_BY_FACT"],
      resource_ids: [],
      workshop_ids: [],
      demand_order_ids: [],
      start_at_utc: null,
      end_at_utc: null,
      sort: "SHIFT_DESC",
      offset: 0,
      limit: 120,
    },
    page: {
      offset: 0,
      limit: 120,
      returned: 2,
      filtered_total: 2,
      unfiltered_total: 3,
      has_more: false,
    },
    provenance: {
      attempt_id: "replan-attempt-demo-1",
      result_id: "replan-result-demo-1",
      result_fingerprint: fingerprint,
      change_report: {
        document_version: "change-report.v1",
        artifact_id: "change-report-demo-1",
        fingerprint,
      },
      before_kpi: {
        document_version: "kpi.v2",
        artifact_id: "kpi-demo-before",
        fingerprint,
      },
      after_kpi: {
        document_version: "kpi.v2",
        artifact_id: "kpi-demo-after",
        fingerprint,
      },
      validation_status: "PASS",
    },
    boundary: {
      data_plane: "SIMULATION",
      environment: "TEST",
      simulation_only: true,
      production_authority: false,
      publishable: false,
    },
    view_fingerprint: fingerprint,
  };
}

export function draftScheduleSummary(): DemoScheduleSummary {
  const summary = scheduleSummary("PUBLISHED");
  return {
    ...summary,
    version: {
      ...summary.version,
      schedule_version_id: draftVersionId,
      contract_version: "schedule-version.v2",
      revision: 1,
      state: "DRAFT",
    },
    solver: {
      ...summary.solver,
      solver_status: "FEASIBLE",
      optimality_claim: false,
    },
  };
}

export function draftScheduleView(): DemoScheduleView {
  const view = scheduleView("PUBLISHED");
  return {
    ...view,
    version: {
      ...view.version,
      schedule_version_id: draftVersionId,
      contract_version: "schedule-version.v2",
      revision: 1,
      state: "DRAFT",
      source_kind: "DYNAMIC_REPLAN",
      parent_schedule_version_id: versionId,
    },
    solver: {
      ...view.solver,
      solver_status: "FEASIBLE",
      optimality_claim: false,
    },
  };
}
