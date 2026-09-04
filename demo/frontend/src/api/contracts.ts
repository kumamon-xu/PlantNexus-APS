import {
  storyStates,
  type ActiveJobSummary,
  type BaselineActivationResult,
  type ArtifactReference,
  type ChangeClassification,
  type ComparisonAssignment,
  type ComparisonKpiSummary,
  type ComparisonPresentationQuery,
  type ComparisonReference,
  type ComparisonVersionSummary,
  type DemoBootstrap,
  type DemoComparisonView,
  type DemoFactoryView,
  type DemoJob,
  type DemoJobStage,
  type DemoScheduleView,
  type DemoScheduleSummary,
  type ExecutionSegment,
  type FactoryResource,
  type FactoryUnavailableInterval,
  type JobAccepted,
  type JobStatus,
  type MaintenanceEvent,
  type OperationState,
  type PublicationReference,
  type ResourceLoad,
  type ScenarioManifest,
  type ScheduleAssignment,
  type ScheduleOrder,
  type SchedulePresentationQuery,
  type ScheduleSort,
  type ScheduleState,
  type ScheduleVersionReference,
  type TimePair,
  type UrgentReplanResult,
} from "./types";

export class DemoContractError extends Error {
  constructor(readonly contract: string) {
    super(`Demo response contract rejected: ${contract}`);
    this.name = "DemoContractError";
  }
}

type JsonRecord = Record<string, unknown>;

const jobStatuses = new Set<JobStatus>([
  "QUEUED",
  "RUNNING",
  "SUCCEEDED",
  "FAILED",
  "INTERRUPTED",
  "CANCELLING",
  "CANCELLED",
]);

const scheduleStates = new Set<ScheduleState>([
  "DRAFT",
  "READY_FOR_REVIEW",
  "APPROVED",
  "PUBLISHED",
  "SUPERSEDED",
  "REJECTED",
]);

function reject(contract: string): never {
  throw new DemoContractError(contract);
}

function record(value: unknown, contract: string): JsonRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    reject(contract);
  }
  return value as JsonRecord;
}

function text(value: unknown, contract: string): string {
  if (typeof value !== "string" || value.length === 0) {
    reject(contract);
  }
  return value;
}

function nullableText(value: unknown, contract: string): string | null {
  return value === null ? null : text(value, contract);
}

function numberValue(value: unknown, contract: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    reject(contract);
  }
  return value;
}

function integer(value: unknown, contract: string): number {
  const parsed = numberValue(value, contract);
  if (!Number.isInteger(parsed)) {
    reject(contract);
  }
  return parsed;
}

function booleanValue(value: unknown, contract: string): boolean {
  if (typeof value !== "boolean") {
    reject(contract);
  }
  return value;
}

function literal<T extends string | number | boolean>(
  value: unknown,
  expected: T,
  contract: string,
): T {
  if (value !== expected) {
    reject(contract);
  }
  return expected;
}

function enumValue<T extends string>(
  value: unknown,
  allowed: ReadonlySet<T>,
  contract: string,
): T {
  const parsed = text(value, contract) as T;
  if (!allowed.has(parsed)) {
    reject(contract);
  }
  return parsed;
}

function nullableRecord(value: unknown, contract: string): JsonRecord | null {
  return value === null ? null : record(value, contract);
}

function arrayValue(value: unknown, contract: string): readonly unknown[] {
  if (!Array.isArray(value)) reject(contract);
  return value;
}

function nonNegativeInteger(value: unknown, contract: string): number {
  const parsed = integer(value, contract);
  if (parsed < 0) reject(contract);
  return parsed;
}

function positiveInteger(value: unknown, contract: string): number {
  const parsed = integer(value, contract);
  if (parsed < 1) reject(contract);
  return parsed;
}

function nullableNumber(value: unknown, contract: string): number | null {
  return value === null ? null : numberValue(value, contract);
}

function nullableNonNegativeInteger(
  value: unknown,
  contract: string,
): number | null {
  return value === null ? null : nonNegativeInteger(value, contract);
}

function fingerprintValue(value: unknown, contract: string): string {
  const parsed = text(value, contract);
  if (!/^sha256:[0-9a-f]{64}$/.test(parsed)) reject(contract);
  return parsed;
}

function utcInstant(value: unknown, contract: string): string {
  const parsed = text(value, contract);
  if (!parsed.endsWith("Z") || Number.isNaN(Date.parse(parsed))) reject(contract);
  return parsed;
}

function timePair(value: unknown, contract: string): TimePair {
  const item = record(value, contract);
  const utc = utcInstant(item.utc, `${contract}.utc`);
  const local = text(item.local, `${contract}.local`);
  if (Number.isNaN(Date.parse(local))) reject(`${contract}.local`);
  return { utc, local };
}

function assertTimeRange(start: TimePair, end: TimePair, contract: string): void {
  if (Date.parse(end.utc) <= Date.parse(start.utc)) reject(contract);
}

function stringArray(value: unknown, contract: string): readonly string[] {
  return arrayValue(value, contract).map((item, index) =>
    text(item, `${contract}.${index}`),
  );
}

function assertSortedUnique(values: readonly string[], contract: string): void {
  const normalized = [...new Set(values)].sort();
  if (
    normalized.length !== values.length ||
    normalized.some((value, index) => value !== values[index])
  ) {
    reject(contract);
  }
}

function artifactReference(value: unknown, contract: string): ArtifactReference {
  const item = record(value, contract);
  return {
    document_version: text(item.document_version, `${contract}.document_version`),
    artifact_id: text(item.artifact_id, `${contract}.artifact_id`),
    fingerprint: fingerprintValue(item.fingerprint, `${contract}.fingerprint`),
  };
}

function presentationBoundary(
  value: unknown,
  contract: string,
): DemoFactoryView["boundary"] {
  const item = record(value, contract);
  const environments = new Set(["DEVELOPMENT", "TEST", "BENCHMARK"] as const);
  if (
    item.data_plane !== "SIMULATION" ||
    item.simulation_only !== true ||
    item.production_authority !== false ||
    item.publishable !== false
  ) {
    reject(contract);
  }
  return {
    data_plane: "SIMULATION",
    environment: enumValue(
      item.environment,
      environments,
      `${contract}.environment`,
    ),
    simulation_only: true,
    production_authority: false,
    publishable: false,
  };
}

function parseScheduleReference(
  value: unknown,
  contract: string,
): ScheduleVersionReference | null {
  const item = nullableRecord(value, contract);
  if (item === null) return null;
  return {
    schedule_version_id: text(item.schedule_version_id, `${contract}.id`),
    state: enumValue(item.state, scheduleStates, `${contract}.state`),
    content_fingerprint: text(
      item.content_fingerprint,
      `${contract}.fingerprint`,
    ),
  };
}

function parsePublication(value: unknown): PublicationReference | null {
  const item = nullableRecord(value, "bootstrap.current_publication");
  if (item === null) return null;
  return {
    schedule_version_id: text(
      item.schedule_version_id,
      "bootstrap.current_publication.schedule_version_id",
    ),
    content_fingerprint: text(
      item.content_fingerprint,
      "bootstrap.current_publication.content_fingerprint",
    ),
    publication_id: text(item.publication_id, "publication.id"),
    reference_revision: integer(item.reference_revision, "publication.revision"),
  };
}

function parseActiveJob(value: unknown): ActiveJobSummary | string | null {
  if (value === null) return null;
  if (typeof value === "string") return text(value, "bootstrap.active_job");
  const item = record(value, "bootstrap.active_job");
  return {
    job_id: text(item.job_id, "active_job.job_id"),
    job_kind: text(item.job_kind, "active_job.job_kind"),
    status: enumValue(item.status, jobStatuses, "active_job.status"),
    stage: nullableText(item.stage, "active_job.stage"),
  };
}

function parseManifest(value: unknown): ScenarioManifest | null {
  const item = nullableRecord(value, "bootstrap.scenario_manifest");
  if (item === null) return null;
  const source = record(item.source_counts, "manifest.source_counts");
  const problem = record(item.problem_counts, "manifest.problem_counts");
  const profile = enumValue(
    item.profile_name,
    new Set(["smoke", "showcase", "upper"] as const),
    "manifest.profile_name",
  );
  return {
    manifest_version: literal(
      item.manifest_version,
      "cnc-demo-scenario-manifest.v1",
      "manifest.version",
    ),
    run_id: text(item.run_id, "manifest.run_id"),
    scenario_id: text(item.scenario_id, "manifest.scenario_id"),
    scenario_version: text(item.scenario_version, "manifest.scenario_version"),
    profile_name: profile,
    seed: integer(item.seed, "manifest.seed"),
    assets_digest: text(item.assets_digest, "manifest.assets_digest"),
    dataset_hash: text(item.dataset_hash, "manifest.dataset_hash"),
    snapshot_id: text(item.snapshot_id, "manifest.snapshot_id"),
    snapshot_hash: text(item.snapshot_hash, "manifest.snapshot_hash"),
    problem_hash: text(item.problem_hash, "manifest.problem_hash"),
    horizon_start_utc: text(item.horizon_start_utc, "manifest.horizon_start"),
    horizon_end_utc: text(item.horizon_end_utc, "manifest.horizon_end"),
    initial_solve_seconds: numberValue(
      item.initial_solve_seconds,
      "manifest.initial_solve_seconds",
    ),
    replan_solve_seconds: numberValue(
      item.replan_solve_seconds,
      "manifest.replan_solve_seconds",
    ),
    source_counts: {
      demand_orders: integer(source.demand_orders, "source_counts.demand_orders"),
      routing_operations: integer(
        source.routing_operations,
        "source_counts.routing_operations",
      ),
      resources: integer(source.resources, "source_counts.resources"),
      workshops: integer(source.workshops, "source_counts.workshops"),
      execution_facts: integer(
        source.execution_facts,
        "source_counts.execution_facts",
      ),
      operation_locks: integer(
        source.operation_locks,
        "source_counts.operation_locks",
      ),
    },
    problem_counts: {
      orders: integer(problem.orders, "problem_counts.orders"),
      active_operations: integer(
        problem.active_operations,
        "problem_counts.active_operations",
      ),
      resources: integer(problem.resources, "problem_counts.resources"),
      running_operations: integer(
        problem.running_operations,
        "problem_counts.running_operations",
      ),
      hard_locks: integer(problem.hard_locks, "problem_counts.hard_locks"),
      soft_locks: integer(problem.soft_locks, "problem_counts.soft_locks"),
      unavailable_intervals: integer(
        problem.unavailable_intervals,
        "problem_counts.unavailable_intervals",
      ),
    },
  };
}

function parseComparisonReference(value: unknown): ComparisonReference | null {
  const item = nullableRecord(value, "bootstrap.comparison_reference");
  if (item === null) return null;
  return {
    request_id: text(item.request_id, "comparison_reference.request_id"),
    before_schedule_version_id: text(
      item.before_schedule_version_id,
      "comparison_reference.before_schedule_version_id",
    ),
    after_schedule_version_id: text(
      item.after_schedule_version_id,
      "comparison_reference.after_schedule_version_id",
    ),
    change_report_id: text(
      item.change_report_id,
      "comparison_reference.change_report_id",
    ),
    demand_order_id: text(
      item.demand_order_id,
      "comparison_reference.demand_order_id",
    ),
  };
}

function parseConfiguration(
  value: unknown,
): DemoBootstrap["configuration"] {
  const item = record(value, "bootstrap.configuration");
  const routes = arrayValue(
    item.route_templates,
    "bootstrap.configuration.route_templates",
  ).map((route, index) => {
    const parsed = record(route, `configuration.routes.${index}`);
    const operationNames = stringArray(
      parsed.operation_names_zh,
      `configuration.routes.${index}.operation_names_zh`,
    );
    const operationCount = positiveInteger(
      parsed.operation_count,
      `configuration.routes.${index}.operation_count`,
    );
    if (operationNames.length !== operationCount) {
      reject(`configuration.routes.${index}.operation_count`);
    }
    return {
      template_id: text(
        parsed.template_id,
        `configuration.routes.${index}.template_id`,
      ),
      product_family_zh: text(
        parsed.product_family_zh,
        `configuration.routes.${index}.product_family_zh`,
      ),
      operation_count: operationCount,
      operation_names_zh: operationNames,
    };
  });
  const priorities = arrayValue(
    item.priority_classes,
    "bootstrap.configuration.priority_classes",
  ).map((priority, index) => {
    const parsed = record(priority, `configuration.priorities.${index}`);
    return {
      class_id: enumValue(
        parsed.class_id,
        new Set(["NORMAL", "KEY", "URGENT"] as const),
        `configuration.priorities.${index}.class_id`,
      ),
      label_zh: text(
        parsed.label_zh,
        `configuration.priorities.${index}.label_zh`,
      ),
      priority_weight: positiveInteger(
        parsed.priority_weight,
        `configuration.priorities.${index}.priority_weight`,
      ),
    };
  });
  const routeIds = routes.map((route) => route.template_id);
  const classIds = priorities.map((priority) => priority.class_id);
  if (
    routes.length !== 4 ||
    new Set(routeIds).size !== routes.length ||
    routes.some((route) => route.operation_count < 3 || route.operation_count > 6) ||
    priorities.length !== 3 ||
    new Set(classIds).size !== priorities.length
  ) {
    reject("bootstrap.configuration.catalog");
  }
  return {
    configuration_version: literal(
      item.configuration_version,
      "cnc-demo-presentation-configuration.v1",
      "configuration.version",
    ),
    factory_timezone: text(
      item.factory_timezone,
      "configuration.factory_timezone",
    ),
    route_template_version: text(
      item.route_template_version,
      "configuration.route_template_version",
    ),
    route_templates: routes,
    priority_policy_version: text(
      item.priority_policy_version,
      "configuration.priority_policy_version",
    ),
    priority_classes: priorities,
  };
}

export function parseBootstrap(value: unknown): DemoBootstrap {
  const item = record(value, "bootstrap");
  const storyState = enumValue(
    item.story_state,
    new Set(storyStates),
    "bootstrap.story_state",
  );
  const runValue = nullableRecord(item.run, "bootstrap.run");
  const run =
    runValue === null
      ? null
      : {
          run_id: text(runValue.run_id, "run.run_id"),
          scenario_id: text(runValue.scenario_id, "run.scenario_id"),
          seed: integer(runValue.seed, "run.seed"),
          status: text(runValue.status, "run.status"),
          created_at_utc: text(runValue.created_at_utc, "run.created_at_utc"),
        };
  if (item.simulation_only !== true || item.production_authority !== false) {
    reject("bootstrap.authority");
  }
  const scheduleVersion = parseScheduleReference(
    item.schedule_version,
    "bootstrap.schedule_version",
  );
  const publication = parsePublication(item.current_publication);
  const comparisonReference = parseComparisonReference(
    item.comparison_reference,
  );
  if (
    storyState === "DRAFT_COMPARISON_READY" &&
    (comparisonReference === null ||
      scheduleVersion === null ||
      publication === null ||
      scheduleVersion.schedule_version_id !==
        comparisonReference.after_schedule_version_id ||
      scheduleVersion.state !== "DRAFT" ||
      publication.schedule_version_id !==
        comparisonReference.before_schedule_version_id)
  ) {
    reject("bootstrap.comparison_lineage");
  }
  if (
    comparisonReference !== null &&
    storyState !== "DRAFT_COMPARISON_READY"
  ) {
    reject("bootstrap.comparison_state");
  }
  return {
    bootstrap_version: literal(
      item.bootstrap_version,
      "cnc-demo-bootstrap.v1",
      "bootstrap.version",
    ),
    story_state: storyState,
    run,
    active_job: parseActiveJob(item.active_job),
    schedule_version: scheduleVersion,
    current_publication: publication,
    scenario_manifest: parseManifest(item.scenario_manifest),
    comparison_reference: comparisonReference,
    configuration: parseConfiguration(item.configuration),
    simulation_only: true,
    production_authority: false,
    correlation_id: text(item.correlation_id, "bootstrap.correlation_id"),
    active_run_id:
      item.active_run_id === null
        ? null
        : text(item.active_run_id, "bootstrap.active_run_id"),
  };
}

function parseJobStage(value: unknown): DemoJobStage {
  const item = record(value, "job.stage");
  return {
    attempt: integer(item.attempt, "job.stage.attempt"),
    sequence: integer(item.sequence, "job.stage.sequence"),
    stage: text(item.stage, "job.stage.stage"),
    status: text(item.status, "job.stage.status"),
    started_at_utc: text(item.started_at_utc, "job.stage.started_at"),
    finished_at_utc: nullableText(
      item.finished_at_utc,
      "job.stage.finished_at",
    ),
    elapsed_seconds:
      item.elapsed_seconds === null
        ? null
        : numberValue(item.elapsed_seconds, "job.stage.elapsed_seconds"),
    evidence_ref: nullableText(item.evidence_ref, "job.stage.evidence_ref"),
  };
}

export function parseJob(value: unknown): DemoJob {
  const item = record(value, "job");
  if (!Array.isArray(item.stages)) reject("job.stages");
  const jobKinds = new Set(["RESET", "INITIAL_PLAN", "URGENT_REPLAN"] as const);
  const jobKind = enumValue(item.job_kind, jobKinds, "job.job_kind");
  const resultRecord = nullableRecord(item.result, "job.result");
  const result =
    jobKind === "URGENT_REPLAN" && resultRecord !== null
      ? parseUrgentReplanResult(resultRecord)
      : resultRecord;
  return {
    job_version: literal(
      item.job_version,
      "cnc-demo-job.v1",
      "job.version",
    ),
    job_id: text(item.job_id, "job.job_id"),
    job_kind: jobKind,
    run_id: nullableText(item.run_id, "job.run_id"),
    status: enumValue(item.status, jobStatuses, "job.status"),
    stage: nullableText(item.stage, "job.stage"),
    attempt: integer(item.attempt, "job.attempt"),
    result,
    error_code: nullableText(item.error_code, "job.error_code"),
    created_at_utc: text(item.created_at_utc, "job.created_at"),
    updated_at_utc: text(item.updated_at_utc, "job.updated_at"),
    stages: item.stages.map(parseJobStage),
    correlation_id: text(item.correlation_id, "job.correlation_id"),
    active_run_id:
      item.active_run_id === null
        ? null
        : text(item.active_run_id, "job.active_run_id"),
  };
}

export function parseJobAccepted(value: unknown): JobAccepted {
  const item = record(value, "job_accepted");
  const jobKinds = new Set(["RESET", "INITIAL_PLAN", "URGENT_REPLAN"] as const);
  return {
    job_accepted_version: literal(
      item.job_accepted_version,
      "cnc-demo-job-accepted.v1",
      "job_accepted.version",
    ),
    job_id: text(item.job_id, "job_accepted.job_id"),
    job_kind: enumValue(item.job_kind, jobKinds, "job_accepted.job_kind"),
    run_id: nullableText(item.run_id, "job_accepted.run_id"),
    status: enumValue(item.status, jobStatuses, "job_accepted.status"),
    replayed: booleanValue(item.replayed, "job_accepted.replayed"),
  };
}

export function parseScheduleSummary(value: unknown): DemoScheduleSummary {
  const item = record(value, "schedule");
  const version = record(item.version, "schedule.version");
  const createdAt = record(version.created_at, "schedule.version.created_at");
  const solver = record(item.solver, "schedule.solver");
  const validation = record(item.validation, "schedule.validation");
  const kpis = record(item.kpis, "schedule.kpis");
  const delivery = record(kpis.delivery, "schedule.kpis.delivery");
  const planning = record(kpis.planning, "schedule.kpis.planning");
  const boundary = record(item.boundary, "schedule.boundary");
  const contractVersions = new Set([
    "schedule-version.v1",
    "schedule-version.v2",
  ] as const);
  const solverStatuses = new Set(["OPTIMAL", "FEASIBLE"] as const);
  if (
    boundary.data_plane !== "SIMULATION" ||
    boundary.simulation_only !== true ||
    boundary.production_authority !== false ||
    boundary.publishable !== false
  ) {
    reject("schedule.boundary");
  }
  const ratio = delivery.on_time_order_ratio;
  if (ratio !== null) numberValue(ratio, "schedule.kpis.delivery.ratio");
  return {
    view_version: literal(
      item.view_version,
      "cnc-demo-schedule-view.v1",
      "schedule.view_version",
    ),
    run_id: text(item.run_id, "schedule.run_id"),
    scenario_id: text(item.scenario_id, "schedule.scenario_id"),
    timezone: text(item.timezone, "schedule.timezone"),
    version: {
      schedule_version_id: text(
        version.schedule_version_id,
        "schedule.version.id",
      ),
      contract_version: enumValue(
        version.contract_version,
        contractVersions,
        "schedule.version.contract",
      ),
      revision: integer(version.revision, "schedule.version.revision"),
      state: enumValue(version.state, scheduleStates, "schedule.version.state"),
      content_fingerprint: text(
        version.content_fingerprint,
        "schedule.version.fingerprint",
      ),
      created_at: {
        utc: text(createdAt.utc, "schedule.version.created_at.utc"),
        local: text(createdAt.local, "schedule.version.created_at.local"),
      },
    },
    solver: {
      solver_status: enumValue(
        solver.solver_status,
        solverStatuses,
        "schedule.solver.status",
      ),
      limit_seconds: numberValue(
        solver.limit_seconds,
        "schedule.solver.limit_seconds",
      ),
      solve_seconds: numberValue(
        solver.solve_seconds,
        "schedule.solver.solve_seconds",
      ),
      total_seconds: numberValue(
        solver.total_seconds,
        "schedule.solver.total_seconds",
      ),
      optimality_claim: booleanValue(
        solver.optimality_claim,
        "schedule.solver.optimality_claim",
      ),
    },
    validation: {
      status: literal(validation.status, "PASS", "schedule.validation.status"),
      hard_violation_count: literal(
        validation.hard_violation_count,
        0,
        "schedule.validation.hard_violations",
      ),
      fingerprint: text(
        validation.fingerprint,
        "schedule.validation.fingerprint",
      ),
    },
    kpis: {
      fingerprint: text(kpis.fingerprint, "schedule.kpis.fingerprint"),
      delivery: {
        order_count: integer(delivery.order_count, "delivery.order_count"),
        on_time_order_count: integer(
          delivery.on_time_order_count,
          "delivery.on_time_order_count",
        ),
        on_time_order_ratio: ratio as number | null,
        late_order_count: integer(
          delivery.late_order_count,
          "delivery.late_order_count",
        ),
        total_tardiness_seconds: integer(
          delivery.total_tardiness_seconds,
          "delivery.total_tardiness_seconds",
        ),
      },
      planning: {
        makespan_seconds: integer(
          planning.makespan_seconds,
          "planning.makespan_seconds",
        ),
        scheduled_operation_count: integer(
          planning.scheduled_operation_count,
          "planning.scheduled_operation_count",
        ),
        unscheduled_operation_count: integer(
          planning.unscheduled_operation_count,
          "planning.unscheduled_operation_count",
        ),
      },
    },
    boundary: {
      data_plane: "SIMULATION",
      simulation_only: true,
      production_authority: false,
      publishable: false,
    },
    view_fingerprint: text(item.view_fingerprint, "schedule.view_fingerprint"),
  };
}

function unavailableInterval(
  value: unknown,
  contract: string,
): FactoryUnavailableInterval {
  const item = record(value, contract);
  const start = timePair(item.start, `${contract}.start`);
  const end = timePair(item.end, `${contract}.end`);
  assertTimeRange(start, end, `${contract}.range`);
  return {
    interval_id: text(item.interval_id, `${contract}.interval_id`),
    kind: enumValue(
      item.kind,
      new Set(["SHIFT", "MAINTENANCE"] as const),
      `${contract}.kind`,
    ),
    reason: text(item.reason, `${contract}.reason`),
    start,
    end,
  };
}

function factoryResource(value: unknown, contract: string): FactoryResource {
  const item = record(value, contract);
  const capabilities = stringArray(item.capabilities, `${contract}.capabilities`);
  assertSortedUnique(capabilities, `${contract}.capabilities`);
  const intervals = arrayValue(
    item.unavailable_intervals,
    `${contract}.unavailable_intervals`,
  ).map((interval, index) =>
    unavailableInterval(interval, `${contract}.unavailable_intervals.${index}`),
  );
  return {
    resource_id: text(item.resource_id, `${contract}.resource_id`),
    source_resource_id: text(
      item.source_resource_id,
      `${contract}.source_resource_id`,
    ),
    resource_code: text(item.resource_code, `${contract}.resource_code`),
    resource_name: text(item.resource_name, `${contract}.resource_name`),
    family: text(item.family, `${contract}.family`),
    status: literal(item.status, "ACTIVE", `${contract}.status`),
    capabilities,
    calendar_id: text(item.calendar_id, `${contract}.calendar_id`),
    unavailable_intervals: intervals,
  };
}

function maintenanceEvent(value: unknown, contract: string): MaintenanceEvent {
  const item = record(value, contract);
  const start = timePair(item.start, `${contract}.start`);
  const end = timePair(item.end, `${contract}.end`);
  assertTimeRange(start, end, `${contract}.range`);
  return {
    event_id: text(item.event_id, `${contract}.event_id`),
    resource_id: text(item.resource_id, `${contract}.resource_id`),
    source_resource_id: text(
      item.source_resource_id,
      `${contract}.source_resource_id`,
    ),
    resource_code: text(item.resource_code, `${contract}.resource_code`),
    reason: text(item.reason, `${contract}.reason`),
    start,
    end,
  };
}

export function parseFactoryView(value: unknown): DemoFactoryView {
  const item = record(value, "factory");
  const node = record(item.factory, "factory.factory");
  const workshopValues = arrayValue(node.workshops, "factory.workshops");
  let productionLineCount = 0;
  let resourceGroupCount = 0;
  const resourceIds = new Set<string>();
  let unavailableIntervalCount = 0;

  const workshops = workshopValues.map((workshopValue, workshopIndex) => {
    const contract = `factory.workshops.${workshopIndex}`;
    const workshop = record(workshopValue, contract);
    const line = record(workshop.production_line, `${contract}.production_line`);
    productionLineCount += 1;
    const groups = arrayValue(
      line.resource_groups,
      `${contract}.production_line.resource_groups`,
    ).map((groupValue, groupIndex) => {
      resourceGroupCount += 1;
      const groupContract = `${contract}.resource_groups.${groupIndex}`;
      const group = record(groupValue, groupContract);
      const resources = arrayValue(
        group.resources,
        `${groupContract}.resources`,
      ).map((resourceValue, resourceIndex) => {
        const parsed = factoryResource(
          resourceValue,
          `${groupContract}.resources.${resourceIndex}`,
        );
        if (resourceIds.has(parsed.resource_id)) reject("factory.resource_ids");
        resourceIds.add(parsed.resource_id);
        unavailableIntervalCount += parsed.unavailable_intervals.length;
        return parsed;
      });
      return {
        resource_group_id: text(
          group.resource_group_id,
          `${groupContract}.resource_group_id`,
        ),
        source_resource_group_id: text(
          group.source_resource_group_id,
          `${groupContract}.source_resource_group_id`,
        ),
        resource_group_code: text(
          group.resource_group_code,
          `${groupContract}.resource_group_code`,
        ),
        resources,
      };
    });
    return {
      workshop_id: text(workshop.workshop_id, `${contract}.workshop_id`),
      source_workshop_id: text(
        workshop.source_workshop_id,
        `${contract}.source_workshop_id`,
      ),
      workshop_code: text(
        workshop.workshop_code,
        `${contract}.workshop_code`,
      ),
      workshop_name: text(
        workshop.workshop_name,
        `${contract}.workshop_name`,
      ),
      production_line: {
        production_line_id: text(
          line.production_line_id,
          `${contract}.production_line.production_line_id`,
        ),
        source_production_line_id: text(
          line.source_production_line_id,
          `${contract}.production_line.source_production_line_id`,
        ),
        production_line_code: text(
          line.production_line_code,
          `${contract}.production_line.production_line_code`,
        ),
        resource_groups: groups,
      },
    };
  });
  const horizonStart = timePair(item.horizon_start, "factory.horizon_start");
  const horizonEnd = timePair(item.horizon_end, "factory.horizon_end");
  assertTimeRange(horizonStart, horizonEnd, "factory.horizon");
  const maintenanceEvents = arrayValue(
    item.maintenance_events,
    "factory.maintenance_events",
  ).map((event, index) =>
    maintenanceEvent(event, `factory.maintenance_events.${index}`),
  );
  const counts = record(item.counts, "factory.counts");
  const parsedCounts = {
    workshops: positiveInteger(counts.workshops, "factory.counts.workshops"),
    production_lines: positiveInteger(
      counts.production_lines,
      "factory.counts.production_lines",
    ),
    resource_groups: positiveInteger(
      counts.resource_groups,
      "factory.counts.resource_groups",
    ),
    resources: positiveInteger(counts.resources, "factory.counts.resources"),
    maintenance_events: nonNegativeInteger(
      counts.maintenance_events,
      "factory.counts.maintenance_events",
    ),
    unavailable_intervals: nonNegativeInteger(
      counts.unavailable_intervals,
      "factory.counts.unavailable_intervals",
    ),
  };
  if (
    parsedCounts.workshops !== workshops.length ||
    parsedCounts.production_lines !== productionLineCount ||
    parsedCounts.resource_groups !== resourceGroupCount ||
    parsedCounts.resources !== resourceIds.size ||
    parsedCounts.maintenance_events !== maintenanceEvents.length ||
    parsedCounts.unavailable_intervals !== unavailableIntervalCount
  ) {
    reject("factory.counts.consistency");
  }
  if (maintenanceEvents.some((event) => !resourceIds.has(event.resource_id))) {
    reject("factory.maintenance_events.resource_id");
  }
  const provenance = record(item.provenance, "factory.provenance");
  return {
    view_version: literal(
      item.view_version,
      "cnc-demo-factory-view.v1",
      "factory.view_version",
    ),
    run_id: text(item.run_id, "factory.run_id"),
    scenario_id: text(item.scenario_id, "factory.scenario_id"),
    profile_name: enumValue(
      item.profile_name,
      new Set(["smoke", "showcase", "upper"] as const),
      "factory.profile_name",
    ),
    seed: nonNegativeInteger(item.seed, "factory.seed"),
    horizon_start: horizonStart,
    horizon_end: horizonEnd,
    factory: {
      factory_id: text(node.factory_id, "factory.factory_id"),
      source_factory_id: text(
        node.source_factory_id,
        "factory.source_factory_id",
      ),
      factory_code: text(node.factory_code, "factory.factory_code"),
      factory_name: text(node.factory_name, "factory.factory_name"),
      timezone: text(node.timezone, "factory.timezone"),
      workshops,
    },
    maintenance_events: maintenanceEvents,
    counts: parsedCounts,
    provenance: {
      asset_pack_version: text(
        provenance.asset_pack_version,
        "factory.provenance.asset_pack_version",
      ),
      asset_pack_fingerprint: fingerprintValue(
        provenance.asset_pack_fingerprint,
        "factory.provenance.asset_pack_fingerprint",
      ),
      snapshot: artifactReference(
        provenance.snapshot,
        "factory.provenance.snapshot",
      ),
    },
    boundary: presentationBoundary(item.boundary, "factory.boundary"),
    view_fingerprint: fingerprintValue(
      item.view_fingerprint,
      "factory.view_fingerprint",
    ),
  };
}

function scheduleQuery(value: unknown): SchedulePresentationQuery {
  const item = record(value, "schedule.query");
  const resourceIds = stringArray(item.resource_ids, "schedule.query.resource_ids");
  const workshopIds = stringArray(item.workshop_ids, "schedule.query.workshop_ids");
  const demandOrderIds = stringArray(
    item.demand_order_ids,
    "schedule.query.demand_order_ids",
  );
  const states = arrayValue(item.states, "schedule.query.states").map(
    (state, index) =>
      enumValue(
        state,
        new Set(["NOT_STARTED", "RUNNING"] as const),
        `schedule.query.states.${index}`,
      ),
  );
  assertSortedUnique(resourceIds, "schedule.query.resource_ids");
  assertSortedUnique(workshopIds, "schedule.query.workshop_ids");
  assertSortedUnique(demandOrderIds, "schedule.query.demand_order_ids");
  assertSortedUnique(states, "schedule.query.states");
  const startAt =
    item.start_at_utc === null
      ? null
      : utcInstant(item.start_at_utc, "schedule.query.start_at_utc");
  const endAt =
    item.end_at_utc === null
      ? null
      : utcInstant(item.end_at_utc, "schedule.query.end_at_utc");
  if (startAt !== null && endAt !== null && Date.parse(endAt) <= Date.parse(startAt)) {
    reject("schedule.query.range");
  }
  const limit = positiveInteger(item.limit, "schedule.query.limit");
  if (limit > 500) reject("schedule.query.limit");
  return {
    resource_ids: resourceIds,
    workshop_ids: workshopIds,
    demand_order_ids: demandOrderIds,
    states: states as readonly OperationState[],
    start_at_utc: startAt,
    end_at_utc: endAt,
    sort: enumValue(
      item.sort,
      new Set(["START_ASC", "RESOURCE_START_ASC", "ORDER_START_ASC"] as const),
      "schedule.query.sort",
    ) as ScheduleSort,
    offset: nonNegativeInteger(item.offset, "schedule.query.offset"),
    limit,
  };
}

function scheduleOrder(value: unknown, contract: string): ScheduleOrder {
  const item = record(value, contract);
  const operationCount = positiveInteger(
    item.operation_count,
    `${contract}.operation_count`,
  );
  const scheduledCount = nonNegativeInteger(
    item.scheduled_operation_count,
    `${contract}.scheduled_operation_count`,
  );
  const completedCount = nonNegativeInteger(
    item.completed_operation_count,
    `${contract}.completed_operation_count`,
  );
  const runningCount = nonNegativeInteger(
    item.running_operation_count,
    `${contract}.running_operation_count`,
  );
  if (scheduledCount + completedCount > operationCount || runningCount > scheduledCount) {
    reject(`${contract}.operation_counts`);
  }
  const quantity = numberValue(item.quantity, `${contract}.quantity`);
  if (quantity <= 0) reject(`${contract}.quantity`);
  return {
    demand_order_id: text(item.demand_order_id, `${contract}.demand_order_id`),
    order_code: text(item.order_code, `${contract}.order_code`),
    product_code: text(item.product_code, `${contract}.product_code`),
    quantity,
    quantity_unit: text(item.quantity_unit, `${contract}.quantity_unit`),
    priority_class: enumValue(
      item.priority_class,
      new Set(["NORMAL", "KEY", "URGENT"] as const),
      `${contract}.priority_class`,
    ),
    priority_weight: positiveInteger(
      item.priority_weight,
      `${contract}.priority_weight`,
    ),
    release_at: timePair(item.release_at, `${contract}.release_at`),
    material_ready_at: timePair(
      item.material_ready_at,
      `${contract}.material_ready_at`,
    ),
    due_at: timePair(item.due_at, `${contract}.due_at`),
    completion_at: timePair(item.completion_at, `${contract}.completion_at`),
    tardiness_seconds: nonNegativeInteger(
      item.tardiness_seconds,
      `${contract}.tardiness_seconds`,
    ),
    on_time: booleanValue(item.on_time, `${contract}.on_time`),
    operation_count: operationCount,
    scheduled_operation_count: scheduledCount,
    completed_operation_count: completedCount,
    running_operation_count: runningCount,
  };
}

function scheduleAssignment(
  value: unknown,
  contract: string,
): ScheduleAssignment {
  const item = record(value, contract);
  const start = timePair(item.start, `${contract}.start`);
  const end = timePair(item.end, `${contract}.end`);
  assertTimeRange(start, end, `${contract}.range`);
  const candidateCount = positiveInteger(
    item.candidate_resource_count,
    `${contract}.candidate_resource_count`,
  );
  if (candidateCount > 3) reject(`${contract}.candidate_resource_count`);
  const lockIds = stringArray(item.lock_ids, `${contract}.lock_ids`);
  const factIds = stringArray(
    item.execution_fact_ids,
    `${contract}.execution_fact_ids`,
  );
  assertSortedUnique(lockIds, `${contract}.lock_ids`);
  assertSortedUnique(factIds, `${contract}.execution_fact_ids`);
  return {
    operation_id: text(item.operation_id, `${contract}.operation_id`),
    operation_code: text(item.operation_code, `${contract}.operation_code`),
    operation_name: text(item.operation_name, `${contract}.operation_name`),
    operation_sequence: positiveInteger(
      item.operation_sequence,
      `${contract}.operation_sequence`,
    ),
    demand_order_id: text(item.demand_order_id, `${contract}.demand_order_id`),
    order_code: text(item.order_code, `${contract}.order_code`),
    product_code: text(item.product_code, `${contract}.product_code`),
    resource_id: text(item.resource_id, `${contract}.resource_id`),
    source_resource_id: text(
      item.source_resource_id,
      `${contract}.source_resource_id`,
    ),
    resource_code: text(item.resource_code, `${contract}.resource_code`),
    resource_name: text(item.resource_name, `${contract}.resource_name`),
    workshop_id: text(item.workshop_id, `${contract}.workshop_id`),
    source_workshop_id: text(
      item.source_workshop_id,
      `${contract}.source_workshop_id`,
    ),
    workshop_code: text(item.workshop_code, `${contract}.workshop_code`),
    workshop_name: text(item.workshop_name, `${contract}.workshop_name`),
    start,
    end,
    duration_seconds: positiveInteger(
      item.duration_seconds,
      `${contract}.duration_seconds`,
    ),
    operation_state: enumValue(
      item.operation_state,
      new Set(["NOT_STARTED", "RUNNING"] as const),
      `${contract}.operation_state`,
    ),
    candidate_resource_count: candidateCount,
    lock_ids: lockIds,
    execution_fact_ids: factIds,
    protection: enumValue(
      item.protection,
      new Set(["FREE", "RUNNING", "HARD_LOCK", "SOFT_LOCK"] as const),
      `${contract}.protection`,
    ),
  };
}

function executionSegment(value: unknown, contract: string): ExecutionSegment {
  const item = record(value, contract);
  const status = enumValue(
    item.status,
    new Set(["COMPLETED", "RUNNING"] as const),
    `${contract}.status`,
  );
  const actualStart = timePair(item.actual_start, `${contract}.actual_start`);
  const actualEnd =
    item.actual_end === null
      ? null
      : timePair(item.actual_end, `${contract}.actual_end`);
  const remaining = nullableNonNegativeInteger(
    item.remaining_seconds,
    `${contract}.remaining_seconds`,
  );
  if (actualEnd !== null) assertTimeRange(actualStart, actualEnd, `${contract}.range`);
  if (
    (status === "COMPLETED" && (actualEnd === null || remaining !== null)) ||
    (status === "RUNNING" && (actualEnd !== null || remaining === null))
  ) {
    reject(`${contract}.status_fields`);
  }
  return {
    execution_fact_id: text(
      item.execution_fact_id,
      `${contract}.execution_fact_id`,
    ),
    operation_id: text(item.operation_id, `${contract}.operation_id`),
    demand_order_id: text(item.demand_order_id, `${contract}.demand_order_id`),
    resource_id: text(item.resource_id, `${contract}.resource_id`),
    resource_code: text(item.resource_code, `${contract}.resource_code`),
    status,
    actual_start: actualStart,
    actual_end: actualEnd,
    remaining_seconds: remaining,
  };
}

function resourceLoad(value: unknown, contract: string): ResourceLoad {
  const item = record(value, contract);
  const utilization = nullableNumber(item.utilization, `${contract}.utilization`);
  if (utilization !== null && (utilization < 0 || utilization > 1)) {
    reject(`${contract}.utilization`);
  }
  return {
    resource_id: text(item.resource_id, `${contract}.resource_id`),
    source_resource_id: text(
      item.source_resource_id,
      `${contract}.source_resource_id`,
    ),
    resource_code: text(item.resource_code, `${contract}.resource_code`),
    resource_name: text(item.resource_name, `${contract}.resource_name`),
    workshop_id: text(item.workshop_id, `${contract}.workshop_id`),
    workshop_code: text(item.workshop_code, `${contract}.workshop_code`),
    available_seconds: nonNegativeInteger(
      item.available_seconds,
      `${contract}.available_seconds`,
    ),
    planned_busy_seconds: nonNegativeInteger(
      item.planned_busy_seconds,
      `${contract}.planned_busy_seconds`,
    ),
    utilization,
    formula: literal(
      item.formula,
      "planned_busy_seconds / available_seconds",
      `${contract}.formula`,
    ),
    evidence: artifactReference(item.evidence, `${contract}.evidence`),
  };
}

export function parseScheduleView(value: unknown): DemoScheduleView {
  const summary = parseScheduleSummary(value);
  const item = record(value, "schedule");
  const version = record(item.version, "schedule.version");
  const solver = record(item.solver, "schedule.solver");
  const validation = record(item.validation, "schedule.validation");
  const kpis = record(item.kpis, "schedule.kpis");
  const delivery = record(kpis.delivery, "schedule.kpis.delivery");
  const stability = record(kpis.stability, "schedule.kpis.stability");
  const orders = arrayValue(item.orders, "schedule.orders").map((order, index) =>
    scheduleOrder(order, `schedule.orders.${index}`),
  );
  const resources = arrayValue(item.resources, "schedule.resources").map(
    (resource, index) => resourceLoad(resource, `schedule.resources.${index}`),
  );
  const executionSegments = arrayValue(
    item.execution_segments,
    "schedule.execution_segments",
  ).map((segment, index) =>
    executionSegment(segment, `schedule.execution_segments.${index}`),
  );
  const assignments = arrayValue(item.assignments, "schedule.assignments").map(
    (assignment, index) =>
      scheduleAssignment(assignment, `schedule.assignments.${index}`),
  );
  const query = scheduleQuery(item.query);
  const pageValue = record(item.page, "schedule.page");
  const page = {
    offset: nonNegativeInteger(pageValue.offset, "schedule.page.offset"),
    limit: positiveInteger(pageValue.limit, "schedule.page.limit"),
    returned: nonNegativeInteger(pageValue.returned, "schedule.page.returned"),
    filtered_total: nonNegativeInteger(
      pageValue.filtered_total,
      "schedule.page.filtered_total",
    ),
    unfiltered_total: nonNegativeInteger(
      pageValue.unfiltered_total,
      "schedule.page.unfiltered_total",
    ),
    has_more: booleanValue(pageValue.has_more, "schedule.page.has_more"),
  };
  if (
    page.limit > 500 ||
    page.returned !== assignments.length ||
    page.returned > page.limit ||
    page.filtered_total > page.unfiltered_total ||
    page.offset !== query.offset ||
    page.limit !== query.limit ||
    page.has_more !== page.offset + page.returned < page.filtered_total ||
    page.unfiltered_total !== summary.kpis.planning.scheduled_operation_count
  ) {
    reject("schedule.page.consistency");
  }
  const orderIds = new Set(orders.map((order) => order.demand_order_id));
  const resourceIds = new Set(resources.map((resource) => resource.resource_id));
  const operationIds = new Set<string>();
  if (
    orderIds.size !== orders.length ||
    resourceIds.size !== resources.length ||
    orders.length !== summary.kpis.delivery.order_count
  ) {
    reject("schedule.collections.consistency");
  }
  for (const assignment of assignments) {
    if (
      operationIds.has(assignment.operation_id) ||
      !orderIds.has(assignment.demand_order_id) ||
      !resourceIds.has(assignment.resource_id)
    ) {
      reject("schedule.assignments.lineage");
    }
    operationIds.add(assignment.operation_id);
  }
  for (const segment of executionSegments) {
    if (
      !orderIds.has(segment.demand_order_id) ||
      !resourceIds.has(segment.resource_id)
    ) {
      reject("schedule.execution_segments.lineage");
    }
  }
  const provenance = record(item.provenance, "schedule.provenance");
  const artifacts = arrayValue(
    provenance.artifacts,
    "schedule.provenance.artifacts",
  ).map((artifact, index) =>
    artifactReference(artifact, `schedule.provenance.artifacts.${index}`),
  );
  const scheduleFingerprint = fingerprintValue(
    provenance.schedule_content_fingerprint,
    "schedule.provenance.schedule_content_fingerprint",
  );
  if (scheduleFingerprint !== summary.version.content_fingerprint) {
    reject("schedule.provenance.schedule_content_fingerprint");
  }
  const weightedTardiness = nonNegativeInteger(
    delivery.priority_weighted_tardiness_seconds,
    "schedule.kpis.delivery.priority_weighted_tardiness_seconds",
  );
  const stabilityRatio = nullableNumber(
    stability.schedule_stability_ratio,
    "schedule.kpis.stability.schedule_stability_ratio",
  );
  if (stabilityRatio !== null && (stabilityRatio < 0 || stabilityRatio > 1)) {
    reject("schedule.kpis.stability.schedule_stability_ratio");
  }
  return {
    ...summary,
    version: {
      ...summary.version,
      created_at: timePair(version.created_at, "schedule.version.created_at"),
      source_kind: text(version.source_kind, "schedule.version.source_kind"),
      parent_schedule_version_id: nullableText(
        version.parent_schedule_version_id,
        "schedule.version.parent_schedule_version_id",
      ),
    },
    solver: {
      ...summary.solver,
      solver_report_version: enumValue(
        solver.solver_report_version,
        new Set(["solver-report.v1", "solver-report.v2"] as const),
        "schedule.solver.solver_report_version",
      ),
      report_id: text(solver.report_id, "schedule.solver.report_id"),
      evidence_kind: literal(
        solver.evidence_kind,
        "SOLVER_RUN",
        "schedule.solver.evidence_kind",
      ),
      objective_value: nullableNumber(
        solver.objective_value,
        "schedule.solver.objective_value",
      ),
      best_bound: nullableNumber(solver.best_bound, "schedule.solver.best_bound"),
      relative_gap: (() => {
        const value = nullableNumber(
          solver.relative_gap,
          "schedule.solver.relative_gap",
        );
        if (value !== null && value < 0) reject("schedule.solver.relative_gap");
        return value;
      })(),
    },
    validation: {
      ...summary.validation,
      validation_report_version: literal(
        validation.validation_report_version,
        "validation-report.v2",
        "schedule.validation.validation_report_version",
      ),
    },
    kpis: {
      ...summary.kpis,
      kpi_id: text(kpis.kpi_id, "schedule.kpis.kpi_id"),
      kpi_version: literal(kpis.kpi_version, "kpi.v2", "schedule.kpis.kpi_version"),
      delivery: {
        ...summary.kpis.delivery,
        priority_weighted_tardiness_seconds: weightedTardiness,
      },
      stability: {
        status: text(stability.status, "schedule.kpis.stability.status"),
        changed_operation_count: nullableNonNegativeInteger(
          stability.changed_operation_count,
          "schedule.kpis.stability.changed_operation_count",
        ),
        resource_changed_count: nullableNonNegativeInteger(
          stability.resource_changed_count,
          "schedule.kpis.stability.resource_changed_count",
        ),
        start_shift_seconds: nullableNonNegativeInteger(
          stability.start_shift_seconds,
          "schedule.kpis.stability.start_shift_seconds",
        ),
        schedule_stability_ratio: stabilityRatio,
      },
    },
    orders,
    resources,
    execution_segments: executionSegments,
    assignments,
    query,
    page,
    provenance: {
      planning_run_id: text(
        provenance.planning_run_id,
        "schedule.provenance.planning_run_id",
      ),
      schedule_content_fingerprint: scheduleFingerprint,
      artifacts,
    },
    boundary: presentationBoundary(item.boundary, "schedule.boundary"),
    view_fingerprint: fingerprintValue(
      item.view_fingerprint,
      "schedule.view_fingerprint",
    ),
  };
}

export function parseUrgentReplanResult(value: unknown): UrgentReplanResult {
  const item = record(value, "urgent_replan_result");
  const changes = record(
    item.operation_changes,
    "urgent_replan_result.operation_changes",
  );
  return {
    result_version: literal(
      item.result_version,
      "cnc-demo-urgent-replan-result.v1",
      "urgent_replan_result.version",
    ),
    run_id: text(item.run_id, "urgent_replan_result.run_id"),
    demand_order_id: text(
      item.demand_order_id,
      "urgent_replan_result.demand_order_id",
    ),
    event_id: text(item.event_id, "urgent_replan_result.event_id"),
    snapshot_id: text(item.snapshot_id, "urgent_replan_result.snapshot_id"),
    problem_hash: fingerprintValue(
      item.problem_hash,
      "urgent_replan_result.problem_hash",
    ),
    request_id: text(item.request_id, "urgent_replan_result.request_id"),
    attempt_id: text(item.attempt_id, "urgent_replan_result.attempt_id"),
    schedule_version_id: text(
      item.schedule_version_id,
      "urgent_replan_result.schedule_version_id",
    ),
    schedule_state: literal(
      item.schedule_state,
      "DRAFT",
      "urgent_replan_result.schedule_state",
    ),
    solver_status: enumValue(
      item.solver_status,
      new Set(["OPTIMAL", "FEASIBLE"] as const),
      "urgent_replan_result.solver_status",
    ),
    validation_status: literal(
      item.validation_status,
      "PASS",
      "urgent_replan_result.validation_status",
    ),
    change_report_id: text(
      item.change_report_id,
      "urgent_replan_result.change_report_id",
    ),
    operation_changes: {
      ADDED: nonNegativeInteger(changes.ADDED, "urgent_replan_result.ADDED"),
      CHANGED: nonNegativeInteger(
        changes.CHANGED,
        "urgent_replan_result.CHANGED",
      ),
      UNCHANGED: nonNegativeInteger(
        changes.UNCHANGED,
        "urgent_replan_result.UNCHANGED",
      ),
    },
    current_published_version_id: text(
      item.current_published_version_id,
      "urgent_replan_result.current_published_version_id",
    ),
    exact_replay: booleanValue(
      item.exact_replay,
      "urgent_replan_result.exact_replay",
    ),
  };
}

function comparisonVersion(
  value: unknown,
  contract: string,
): ComparisonVersionSummary {
  const item = record(value, contract);
  return {
    schedule_version_id: text(
      item.schedule_version_id,
      `${contract}.schedule_version_id`,
    ),
    contract_version: enumValue(
      item.contract_version,
      new Set(["schedule-version.v1", "schedule-version.v2"] as const),
      `${contract}.contract_version`,
    ),
    revision: positiveInteger(item.revision, `${contract}.revision`),
    state: enumValue(item.state, scheduleStates, `${contract}.state`),
    source_kind: text(item.source_kind, `${contract}.source_kind`),
    parent_schedule_version_id: nullableText(
      item.parent_schedule_version_id,
      `${contract}.parent_schedule_version_id`,
    ),
    content_fingerprint: fingerprintValue(
      item.content_fingerprint,
      `${contract}.content_fingerprint`,
    ),
    created_at: timePair(item.created_at, `${contract}.created_at`),
  };
}

function comparisonKpis(
  value: unknown,
  contract: string,
): ComparisonKpiSummary {
  const item = record(value, contract);
  const delivery = record(item.delivery, `${contract}.delivery`);
  const planning = record(item.planning, `${contract}.planning`);
  const stability = record(item.stability, `${contract}.stability`);
  const ratio = nullableNumber(
    delivery.on_time_order_ratio,
    `${contract}.delivery.on_time_order_ratio`,
  );
  const stabilityRatio = nullableNumber(
    stability.schedule_stability_ratio,
    `${contract}.stability.schedule_stability_ratio`,
  );
  if (
    (ratio !== null && (ratio < 0 || ratio > 1)) ||
    (stabilityRatio !== null && (stabilityRatio < 0 || stabilityRatio > 1))
  ) {
    reject(`${contract}.ratio`);
  }
  const orderCount = nonNegativeInteger(
    delivery.order_count,
    `${contract}.delivery.order_count`,
  );
  const onTime = nonNegativeInteger(
    delivery.on_time_order_count,
    `${contract}.delivery.on_time_order_count`,
  );
  const late = nonNegativeInteger(
    delivery.late_order_count,
    `${contract}.delivery.late_order_count`,
  );
  if (onTime + late !== orderCount) reject(`${contract}.delivery.counts`);
  return {
    kpi_id: text(item.kpi_id, `${contract}.kpi_id`),
    kpi_version: literal(item.kpi_version, "kpi.v2", `${contract}.kpi_version`),
    fingerprint: fingerprintValue(item.fingerprint, `${contract}.fingerprint`),
    delivery: {
      order_count: orderCount,
      on_time_order_count: onTime,
      on_time_order_ratio: ratio,
      late_order_count: late,
      total_tardiness_seconds: nonNegativeInteger(
        delivery.total_tardiness_seconds,
        `${contract}.delivery.total_tardiness_seconds`,
      ),
      priority_weighted_tardiness_seconds: nonNegativeInteger(
        delivery.priority_weighted_tardiness_seconds,
        `${contract}.delivery.priority_weighted_tardiness_seconds`,
      ),
    },
    planning: {
      makespan_seconds: nonNegativeInteger(
        planning.makespan_seconds,
        `${contract}.planning.makespan_seconds`,
      ),
      scheduled_operation_count: nonNegativeInteger(
        planning.scheduled_operation_count,
        `${contract}.planning.scheduled_operation_count`,
      ),
      unscheduled_operation_count: nonNegativeInteger(
        planning.unscheduled_operation_count,
        `${contract}.planning.unscheduled_operation_count`,
      ),
    },
    stability: {
      status: text(stability.status, `${contract}.stability.status`),
      changed_operation_count: nullableNonNegativeInteger(
        stability.changed_operation_count,
        `${contract}.stability.changed_operation_count`,
      ),
      resource_changed_count: nullableNonNegativeInteger(
        stability.resource_changed_count,
        `${contract}.stability.resource_changed_count`,
      ),
      start_shift_seconds: nullableNonNegativeInteger(
        stability.start_shift_seconds,
        `${contract}.stability.start_shift_seconds`,
      ),
      schedule_stability_ratio: stabilityRatio,
    },
  };
}

function comparisonAssignment(
  value: unknown,
  contract: string,
): ComparisonAssignment | null {
  const item = nullableRecord(value, contract);
  if (item === null) return null;
  const start = timePair(item.start, `${contract}.start`);
  const end = timePair(item.end, `${contract}.end`);
  assertTimeRange(start, end, `${contract}.range`);
  return {
    resource_id: text(item.resource_id, `${contract}.resource_id`),
    source_resource_id: text(
      item.source_resource_id,
      `${contract}.source_resource_id`,
    ),
    resource_code: text(item.resource_code, `${contract}.resource_code`),
    workshop_id: text(item.workshop_id, `${contract}.workshop_id`),
    workshop_code: text(item.workshop_code, `${contract}.workshop_code`),
    start,
    end,
    duration_seconds: positiveInteger(
      item.duration_seconds,
      `${contract}.duration_seconds`,
    ),
  };
}

function comparisonQuery(value: unknown): ComparisonPresentationQuery {
  const item = record(value, "comparison.query");
  const classifications = stringArray(
    item.classifications,
    "comparison.query.classifications",
  ) as readonly ChangeClassification[];
  const allowed = new Set<ChangeClassification>([
    "UNCHANGED",
    "CHANGED",
    "ADDED",
    "REMOVED_BY_FACT",
  ]);
  if (classifications.some((value) => !allowed.has(value))) {
    reject("comparison.query.classifications");
  }
  const resourceIds = stringArray(
    item.resource_ids,
    "comparison.query.resource_ids",
  );
  const workshopIds = stringArray(
    item.workshop_ids,
    "comparison.query.workshop_ids",
  );
  const orderIds = stringArray(
    item.demand_order_ids,
    "comparison.query.demand_order_ids",
  );
  for (const [values, contract] of [
    [classifications, "comparison.query.classifications"],
    [resourceIds, "comparison.query.resource_ids"],
    [workshopIds, "comparison.query.workshop_ids"],
    [orderIds, "comparison.query.demand_order_ids"],
  ] as const) {
    assertSortedUnique(values, contract);
  }
  const start =
    item.start_at_utc === null
      ? null
      : utcInstant(item.start_at_utc, "comparison.query.start_at_utc");
  const end =
    item.end_at_utc === null
      ? null
      : utcInstant(item.end_at_utc, "comparison.query.end_at_utc");
  if (start !== null && end !== null && Date.parse(end) <= Date.parse(start)) {
    reject("comparison.query.range");
  }
  const offset = nonNegativeInteger(item.offset, "comparison.query.offset");
  const limit = positiveInteger(item.limit, "comparison.query.limit");
  if (limit > 200) reject("comparison.query.limit");
  return {
    classifications,
    resource_ids: resourceIds,
    workshop_ids: workshopIds,
    demand_order_ids: orderIds,
    start_at_utc: start,
    end_at_utc: end,
    sort: enumValue(
      item.sort,
      new Set(["OPERATION_ASC", "SHIFT_DESC", "START_ASC"] as const),
      "comparison.query.sort",
    ),
    offset,
    limit,
  };
}

function approximatelyEqual(left: number | null, right: number | null): boolean {
  if (left === null || right === null) return left === right;
  return Math.abs(left - right) <= 1e-10;
}

export function parseComparisonView(value: unknown): DemoComparisonView {
  const item = record(value, "comparison");
  const before = comparisonVersion(item.before, "comparison.before");
  const after = comparisonVersion(item.after, "comparison.after");
  const beforeKpis = comparisonKpis(
    item.before_kpis,
    "comparison.before_kpis",
  );
  const afterKpis = comparisonKpis(item.after_kpis, "comparison.after_kpis");
  if (
    before.state !== "PUBLISHED" ||
    after.state !== "DRAFT" ||
    after.contract_version !== "schedule-version.v2" ||
    after.parent_schedule_version_id !== before.schedule_version_id
  ) {
    reject("comparison.version_lineage");
  }

  const deltaValue = record(item.delivery_delta, "comparison.delivery_delta");
  const deliveryDelta = {
    order_count: integer(deltaValue.order_count, "comparison.delta.order_count"),
    on_time_order_count: integer(
      deltaValue.on_time_order_count,
      "comparison.delta.on_time_order_count",
    ),
    on_time_order_ratio: nullableNumber(
      deltaValue.on_time_order_ratio,
      "comparison.delta.on_time_order_ratio",
    ),
    late_order_count: integer(
      deltaValue.late_order_count,
      "comparison.delta.late_order_count",
    ),
    total_tardiness_seconds: integer(
      deltaValue.total_tardiness_seconds,
      "comparison.delta.total_tardiness_seconds",
    ),
    priority_weighted_tardiness_seconds: integer(
      deltaValue.priority_weighted_tardiness_seconds,
      "comparison.delta.priority_weighted_tardiness_seconds",
    ),
    makespan_seconds: integer(
      deltaValue.makespan_seconds,
      "comparison.delta.makespan_seconds",
    ),
    formula: literal(
      deltaValue.formula,
      "after - before",
      "comparison.delta.formula",
    ),
  } as const;
  if (
    deliveryDelta.order_count !==
      afterKpis.delivery.order_count - beforeKpis.delivery.order_count ||
    deliveryDelta.on_time_order_count !==
      afterKpis.delivery.on_time_order_count -
        beforeKpis.delivery.on_time_order_count ||
    !approximatelyEqual(
      deliveryDelta.on_time_order_ratio,
      beforeKpis.delivery.on_time_order_ratio === null ||
        afterKpis.delivery.on_time_order_ratio === null
        ? null
        : afterKpis.delivery.on_time_order_ratio -
            beforeKpis.delivery.on_time_order_ratio,
    ) ||
    deliveryDelta.late_order_count !==
      afterKpis.delivery.late_order_count - beforeKpis.delivery.late_order_count ||
    deliveryDelta.total_tardiness_seconds !==
      afterKpis.delivery.total_tardiness_seconds -
        beforeKpis.delivery.total_tardiness_seconds ||
    deliveryDelta.priority_weighted_tardiness_seconds !==
      afterKpis.delivery.priority_weighted_tardiness_seconds -
        beforeKpis.delivery.priority_weighted_tardiness_seconds ||
    deliveryDelta.makespan_seconds !==
      afterKpis.planning.makespan_seconds - beforeKpis.planning.makespan_seconds
  ) {
    reject("comparison.delivery_delta.consistency");
  }

  const countsValue = record(item.change_counts, "comparison.change_counts");
  const changeCounts = {
    unchanged: nonNegativeInteger(
      countsValue.unchanged,
      "comparison.change_counts.unchanged",
    ),
    changed: nonNegativeInteger(
      countsValue.changed,
      "comparison.change_counts.changed",
    ),
    added: nonNegativeInteger(
      countsValue.added,
      "comparison.change_counts.added",
    ),
    removed_by_fact: nonNegativeInteger(
      countsValue.removed_by_fact,
      "comparison.change_counts.removed_by_fact",
    ),
  };
  const universe = nonNegativeInteger(
    item.operation_universe_count,
    "comparison.operation_universe_count",
  );
  if (
    changeCounts.unchanged +
      changeCounts.changed +
      changeCounts.added +
      changeCounts.removed_by_fact !==
    universe
  ) {
    reject("comparison.change_counts.consistency");
  }

  const operations = arrayValue(item.operations, "comparison.operations").map(
    (operation, index) => {
      const contract = `comparison.operations.${index}`;
      const parsed = record(operation, contract);
      const classification = enumValue(
        parsed.classification,
        new Set([
          "UNCHANGED",
          "CHANGED",
          "ADDED",
          "REMOVED_BY_FACT",
        ] as const),
        `${contract}.classification`,
      );
      const base = comparisonAssignment(
        parsed.base_assignment,
        `${contract}.base_assignment`,
      );
      const next = comparisonAssignment(
        parsed.new_assignment,
        `${contract}.new_assignment`,
      );
      if (
        ((classification === "ADDED") && (base !== null || next === null)) ||
        ((classification === "REMOVED_BY_FACT") &&
          (base === null || next !== null)) ||
        ((classification === "CHANGED" || classification === "UNCHANGED") &&
          (base === null || next === null))
      ) {
        reject(`${contract}.assignment_shape`);
      }
      const deltas = record(parsed.deltas, `${contract}.deltas`);
      const startShift = integer(
        deltas.start_shift_seconds,
        `${contract}.deltas.start_shift_seconds`,
      );
      const absoluteShift = nonNegativeInteger(
        deltas.absolute_start_shift_seconds,
        `${contract}.deltas.absolute_start_shift_seconds`,
      );
      const resourceChanged = booleanValue(
        deltas.resource_changed,
        `${contract}.deltas.resource_changed`,
      );
      if (
        absoluteShift !== Math.abs(startShift) ||
        (base !== null &&
          next !== null &&
          resourceChanged !== (base.resource_id !== next.resource_id))
      ) {
        reject(`${contract}.deltas.consistency`);
      }
      return {
        operation_id: text(parsed.operation_id, `${contract}.operation_id`),
        operation_code: text(
          parsed.operation_code,
          `${contract}.operation_code`,
        ),
        operation_name: text(
          parsed.operation_name,
          `${contract}.operation_name`,
        ),
        demand_order_id: text(
          parsed.demand_order_id,
          `${contract}.demand_order_id`,
        ),
        order_code: text(parsed.order_code, `${contract}.order_code`),
        classification,
        base_assignment: base,
        new_assignment: next,
        deltas: {
          resource_changed: resourceChanged,
          start_shift_seconds: startShift,
          absolute_start_shift_seconds: absoluteShift,
          end_shift_seconds: integer(
            deltas.end_shift_seconds,
            `${contract}.deltas.end_shift_seconds`,
          ),
          duration_delta_seconds: integer(
            deltas.duration_delta_seconds,
            `${contract}.deltas.duration_delta_seconds`,
          ),
        },
        reason_codes: stringArray(
          parsed.reason_codes,
          `${contract}.reason_codes`,
        ),
      };
    },
  );
  if (new Set(operations.map((item) => item.operation_id)).size !== operations.length) {
    reject("comparison.operations.operation_id");
  }

  const query = comparisonQuery(item.query);
  if (operations.some((operation) => !query.classifications.includes(operation.classification))) {
    reject("comparison.operations.query");
  }
  const pageValue = record(item.page, "comparison.page");
  const page = {
    offset: nonNegativeInteger(pageValue.offset, "comparison.page.offset"),
    limit: positiveInteger(pageValue.limit, "comparison.page.limit"),
    returned: nonNegativeInteger(pageValue.returned, "comparison.page.returned"),
    filtered_total: nonNegativeInteger(
      pageValue.filtered_total,
      "comparison.page.filtered_total",
    ),
    unfiltered_total: nonNegativeInteger(
      pageValue.unfiltered_total,
      "comparison.page.unfiltered_total",
    ),
    has_more: booleanValue(pageValue.has_more, "comparison.page.has_more"),
  };
  if (
    page.limit > 200 ||
    page.offset !== query.offset ||
    page.limit !== query.limit ||
    page.returned !== operations.length ||
    page.returned > page.limit ||
    page.filtered_total > page.unfiltered_total ||
    page.unfiltered_total !== universe ||
    page.has_more !== page.offset + page.returned < page.filtered_total
  ) {
    reject("comparison.page.consistency");
  }

  const stabilityValue = record(item.stability, "comparison.stability");
  const stability = {
    soft_lock_violations: nonNegativeInteger(
      stabilityValue.soft_lock_violations,
      "comparison.stability.soft_lock_violations",
    ),
    changed_existing_operations: nonNegativeInteger(
      stabilityValue.changed_existing_operations,
      "comparison.stability.changed_existing_operations",
    ),
    resource_changes: nonNegativeInteger(
      stabilityValue.resource_changes,
      "comparison.stability.resource_changes",
    ),
    absolute_start_shift_seconds: nonNegativeInteger(
      stabilityValue.absolute_start_shift_seconds,
      "comparison.stability.absolute_start_shift_seconds",
    ),
    unchanged_existing: nonNegativeInteger(
      stabilityValue.unchanged_existing,
      "comparison.stability.unchanged_existing",
    ),
    comparable_existing: nonNegativeInteger(
      stabilityValue.comparable_existing,
      "comparison.stability.comparable_existing",
    ),
    unchanged_ratio: nullableNumber(
      stabilityValue.unchanged_ratio,
      "comparison.stability.unchanged_ratio",
    ),
  };
  if (
    stability.changed_existing_operations !== changeCounts.changed ||
    stability.unchanged_existing !== changeCounts.unchanged ||
    stability.comparable_existing !== changeCounts.changed + changeCounts.unchanged ||
    !approximatelyEqual(
      stability.unchanged_ratio,
      stability.comparable_existing === 0
        ? null
        : stability.unchanged_existing / stability.comparable_existing,
    )
  ) {
    reject("comparison.stability.consistency");
  }

  const affectedOrders = arrayValue(
    item.affected_orders,
    "comparison.affected_orders",
  ).map((order, index) => {
    const parsed = record(order, `comparison.affected_orders.${index}`);
    return {
      demand_order_id: text(
        parsed.demand_order_id,
        `comparison.affected_orders.${index}.demand_order_id`,
      ),
      order_code: text(
        parsed.order_code,
        `comparison.affected_orders.${index}.order_code`,
      ),
      change_count: positiveInteger(
        parsed.change_count,
        `comparison.affected_orders.${index}.change_count`,
      ),
    };
  });
  if (
    new Set(affectedOrders.map((order) => order.demand_order_id)).size !==
    affectedOrders.length
  ) {
    reject("comparison.affected_orders.demand_order_id");
  }

  const provenanceValue = record(item.provenance, "comparison.provenance");
  const requestId = text(item.request_id, "comparison.request_id");
  return {
    view_version: literal(
      item.view_version,
      "cnc-demo-comparison-view.v1",
      "comparison.view_version",
    ),
    run_id: text(item.run_id, "comparison.run_id"),
    scenario_id: text(item.scenario_id, "comparison.scenario_id"),
    request_id: requestId,
    timezone: text(item.timezone, "comparison.timezone"),
    before,
    after,
    before_kpis: beforeKpis,
    after_kpis: afterKpis,
    delivery_delta: deliveryDelta,
    operation_universe_count: universe,
    change_counts: changeCounts,
    stability,
    affected_orders: affectedOrders,
    operations,
    query,
    page,
    provenance: {
      attempt_id: text(
        provenanceValue.attempt_id,
        "comparison.provenance.attempt_id",
      ),
      result_id: text(
        provenanceValue.result_id,
        "comparison.provenance.result_id",
      ),
      result_fingerprint: fingerprintValue(
        provenanceValue.result_fingerprint,
        "comparison.provenance.result_fingerprint",
      ),
      change_report: artifactReference(
        provenanceValue.change_report,
        "comparison.provenance.change_report",
      ),
      before_kpi: artifactReference(
        provenanceValue.before_kpi,
        "comparison.provenance.before_kpi",
      ),
      after_kpi: artifactReference(
        provenanceValue.after_kpi,
        "comparison.provenance.after_kpi",
      ),
      validation_status: literal(
        provenanceValue.validation_status,
        "PASS",
        "comparison.provenance.validation_status",
      ),
    },
    boundary: presentationBoundary(item.boundary, "comparison.boundary"),
    view_fingerprint: fingerprintValue(
      item.view_fingerprint,
      "comparison.view_fingerprint",
    ),
  };
}

export function parseActivationResult(value: unknown): BaselineActivationResult {
  const item = record(value, "activation");
  return {
    result_version: literal(
      item.result_version,
      "cnc-demo-baseline-activation-result.v1",
      "activation.version",
    ),
    run_id: text(item.run_id, "activation.run_id"),
    schedule_version_id: text(
      item.schedule_version_id,
      "activation.schedule_version_id",
    ),
    content_fingerprint: text(
      item.content_fingerprint,
      "activation.content_fingerprint",
    ),
    state: literal(item.state, "PUBLISHED", "activation.state"),
    state_revision: integer(item.state_revision, "activation.state_revision"),
    publication_id: text(item.publication_id, "activation.publication_id"),
    current_reference_revision: integer(
      item.current_reference_revision,
      "activation.current_reference_revision",
    ),
    replayed: booleanValue(item.replayed, "activation.replayed"),
  };
}

export function parseSession(value: unknown): void {
  const item = record(value, "session");
  literal(item.session_version, "cnc-demo-local-session.v1", "session.version");
  literal(item.status, "ESTABLISHED", "session.status");
  if (item.simulation_only !== true) reject("session.authority");
}
