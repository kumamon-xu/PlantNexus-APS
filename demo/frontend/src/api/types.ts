export const storyStates = [
  "EMPTY",
  "INITIALIZED",
  "INITIAL_PLAN_RUNNING",
  "READY_FOR_REVIEW",
  "BASELINE_PUBLISHED",
  "REPLAN_RUNNING",
  "DRAFT_COMPARISON_READY",
] as const;

export type StoryState = (typeof storyStates)[number];

export type JobStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "INTERRUPTED"
  | "CANCELLING"
  | "CANCELLED";

export type ScheduleState =
  | "DRAFT"
  | "READY_FOR_REVIEW"
  | "APPROVED"
  | "PUBLISHED"
  | "SUPERSEDED"
  | "REJECTED";

export interface DemoRun {
  readonly run_id: string;
  readonly scenario_id: string;
  readonly seed: number;
  readonly status: string;
  readonly created_at_utc: string;
}

export interface ActiveJobSummary {
  readonly job_id: string;
  readonly job_kind: string;
  readonly status: JobStatus;
  readonly stage: string | null;
}

export interface ScheduleVersionReference {
  readonly schedule_version_id: string;
  readonly state: ScheduleState;
  readonly content_fingerprint: string;
}

export interface PublicationReference {
  readonly schedule_version_id: string;
  readonly content_fingerprint: string;
  readonly publication_id: string;
  readonly reference_revision: number;
}

export interface ScenarioCounts {
  readonly orders: number;
  readonly active_operations: number;
  readonly resources: number;
  readonly running_operations: number;
  readonly hard_locks: number;
  readonly soft_locks: number;
  readonly unavailable_intervals: number;
}

export interface SourceCounts {
  readonly demand_orders: number;
  readonly routing_operations: number;
  readonly resources: number;
  readonly workshops: number;
  readonly execution_facts: number;
  readonly operation_locks: number;
}

export interface ScenarioManifest {
  readonly manifest_version: "cnc-demo-scenario-manifest.v1";
  readonly run_id: string;
  readonly scenario_id: string;
  readonly scenario_version: string;
  readonly profile_name: "smoke" | "showcase" | "upper";
  readonly seed: number;
  readonly assets_digest: string;
  readonly dataset_hash: string;
  readonly snapshot_id: string;
  readonly snapshot_hash: string;
  readonly problem_hash: string;
  readonly horizon_start_utc: string;
  readonly horizon_end_utc: string;
  readonly initial_solve_seconds: number;
  readonly replan_solve_seconds: number;
  readonly source_counts: SourceCounts;
  readonly problem_counts: ScenarioCounts;
}

export type PriorityClass = "NORMAL" | "KEY" | "URGENT";

export interface DemoRouteTemplate {
  readonly template_id: string;
  readonly product_family_zh: string;
  readonly operation_count: number;
  readonly operation_names_zh: readonly string[];
}

export interface DemoPriorityClass {
  readonly class_id: PriorityClass;
  readonly label_zh: string;
  readonly priority_weight: number;
}

export interface DemoPresentationConfiguration {
  readonly configuration_version: "cnc-demo-presentation-configuration.v1";
  readonly factory_timezone: string;
  readonly route_template_version: string;
  readonly route_templates: readonly DemoRouteTemplate[];
  readonly priority_policy_version: string;
  readonly priority_classes: readonly DemoPriorityClass[];
}

export interface ComparisonReference {
  readonly request_id: string;
  readonly before_schedule_version_id: string;
  readonly after_schedule_version_id: string;
  readonly change_report_id: string;
  readonly demand_order_id: string;
}

export interface DemoBootstrap {
  readonly bootstrap_version: "cnc-demo-bootstrap.v1";
  readonly story_state: StoryState;
  readonly run: DemoRun | null;
  readonly active_job: ActiveJobSummary | string | null;
  readonly schedule_version: ScheduleVersionReference | null;
  readonly current_publication: PublicationReference | null;
  readonly scenario_manifest: ScenarioManifest | null;
  readonly comparison_reference: ComparisonReference | null;
  readonly configuration: DemoPresentationConfiguration;
  readonly simulation_only: true;
  readonly production_authority: false;
  readonly correlation_id: string;
  readonly active_run_id: string | null;
}

export interface DemoJobStage {
  readonly attempt: number;
  readonly sequence: number;
  readonly stage: string;
  readonly status: string;
  readonly started_at_utc: string;
  readonly finished_at_utc: string | null;
  readonly elapsed_seconds: number | null;
  readonly evidence_ref: string | null;
}

export interface DemoJob {
  readonly job_version: "cnc-demo-job.v1";
  readonly job_id: string;
  readonly job_kind: "RESET" | "INITIAL_PLAN" | "URGENT_REPLAN";
  readonly run_id: string | null;
  readonly status: JobStatus;
  readonly stage: string | null;
  readonly attempt: number;
  readonly result:
    | Readonly<Record<string, unknown>>
    | UrgentReplanResult
    | null;
  readonly error_code: string | null;
  readonly created_at_utc: string;
  readonly updated_at_utc: string;
  readonly stages: readonly DemoJobStage[];
  readonly correlation_id: string;
  readonly active_run_id: string | null;
}

export interface JobAccepted {
  readonly job_accepted_version: "cnc-demo-job-accepted.v1";
  readonly job_id: string;
  readonly job_kind: "RESET" | "INITIAL_PLAN" | "URGENT_REPLAN";
  readonly run_id: string | null;
  readonly status: JobStatus;
  readonly replayed: boolean;
}

export interface TimePair {
  readonly utc: string;
  readonly local: string;
}

export type PresentationEnvironment = "DEVELOPMENT" | "TEST" | "BENCHMARK";

export interface PresentationBoundary {
  readonly data_plane: "SIMULATION";
  readonly environment: PresentationEnvironment;
  readonly simulation_only: true;
  readonly production_authority: false;
  readonly publishable: false;
}

export interface ArtifactReference {
  readonly document_version: string;
  readonly artifact_id: string;
  readonly fingerprint: string;
}

export interface PageInfo {
  readonly offset: number;
  readonly limit: number;
  readonly returned: number;
  readonly filtered_total: number;
  readonly unfiltered_total: number;
  readonly has_more: boolean;
}

export interface FactoryUnavailableInterval {
  readonly interval_id: string;
  readonly kind: "SHIFT" | "MAINTENANCE";
  readonly reason: string;
  readonly start: TimePair;
  readonly end: TimePair;
}

export interface FactoryResource {
  readonly resource_id: string;
  readonly source_resource_id: string;
  readonly resource_code: string;
  readonly resource_name: string;
  readonly family: string;
  readonly status: "ACTIVE";
  readonly capabilities: readonly string[];
  readonly calendar_id: string;
  readonly unavailable_intervals: readonly FactoryUnavailableInterval[];
}

export interface FactoryResourceGroup {
  readonly resource_group_id: string;
  readonly source_resource_group_id: string;
  readonly resource_group_code: string;
  readonly resources: readonly FactoryResource[];
}

export interface FactoryProductionLine {
  readonly production_line_id: string;
  readonly source_production_line_id: string;
  readonly production_line_code: string;
  readonly resource_groups: readonly FactoryResourceGroup[];
}

export interface FactoryWorkshop {
  readonly workshop_id: string;
  readonly source_workshop_id: string;
  readonly workshop_code: string;
  readonly workshop_name: string;
  readonly production_line: FactoryProductionLine;
}

export interface FactoryNode {
  readonly factory_id: string;
  readonly source_factory_id: string;
  readonly factory_code: string;
  readonly factory_name: string;
  readonly timezone: string;
  readonly workshops: readonly FactoryWorkshop[];
}

export interface MaintenanceEvent {
  readonly event_id: string;
  readonly resource_id: string;
  readonly source_resource_id: string;
  readonly resource_code: string;
  readonly reason: string;
  readonly start: TimePair;
  readonly end: TimePair;
}

export interface DemoFactoryView {
  readonly view_version: "cnc-demo-factory-view.v1";
  readonly run_id: string;
  readonly scenario_id: string;
  readonly profile_name: "smoke" | "showcase" | "upper";
  readonly seed: number;
  readonly horizon_start: TimePair;
  readonly horizon_end: TimePair;
  readonly factory: FactoryNode;
  readonly maintenance_events: readonly MaintenanceEvent[];
  readonly counts: {
    readonly workshops: number;
    readonly production_lines: number;
    readonly resource_groups: number;
    readonly resources: number;
    readonly maintenance_events: number;
    readonly unavailable_intervals: number;
  };
  readonly provenance: {
    readonly asset_pack_version: string;
    readonly asset_pack_fingerprint: string;
    readonly snapshot: ArtifactReference;
  };
  readonly boundary: PresentationBoundary;
  readonly view_fingerprint: string;
}

export type OperationState = "NOT_STARTED" | "RUNNING";
export type ScheduleSort =
  | "START_ASC"
  | "RESOURCE_START_ASC"
  | "ORDER_START_ASC";

export interface SchedulePresentationQuery {
  readonly resource_ids: readonly string[];
  readonly workshop_ids: readonly string[];
  readonly demand_order_ids: readonly string[];
  readonly states: readonly OperationState[];
  readonly start_at_utc: string | null;
  readonly end_at_utc: string | null;
  readonly sort: ScheduleSort;
  readonly offset: number;
  readonly limit: number;
}

export interface ScheduleQueryInput {
  readonly resource_ids?: readonly string[];
  readonly workshop_ids?: readonly string[];
  readonly demand_order_ids?: readonly string[];
  readonly states?: readonly OperationState[];
  readonly start_at_utc?: string | null;
  readonly end_at_utc?: string | null;
  readonly sort?: ScheduleSort;
  readonly offset?: number;
  readonly limit?: number;
}

export interface ScheduleOrder {
  readonly demand_order_id: string;
  readonly order_code: string;
  readonly product_code: string;
  readonly quantity: number;
  readonly quantity_unit: string;
  readonly priority_class: "NORMAL" | "KEY" | "URGENT";
  readonly priority_weight: number;
  readonly release_at: TimePair;
  readonly material_ready_at: TimePair;
  readonly due_at: TimePair;
  readonly completion_at: TimePair;
  readonly tardiness_seconds: number;
  readonly on_time: boolean;
  readonly operation_count: number;
  readonly scheduled_operation_count: number;
  readonly completed_operation_count: number;
  readonly running_operation_count: number;
}

export type AssignmentProtection =
  | "FREE"
  | "RUNNING"
  | "HARD_LOCK"
  | "SOFT_LOCK";

export interface ScheduleAssignment {
  readonly operation_id: string;
  readonly operation_code: string;
  readonly operation_name: string;
  readonly operation_sequence: number;
  readonly demand_order_id: string;
  readonly order_code: string;
  readonly product_code: string;
  readonly resource_id: string;
  readonly source_resource_id: string;
  readonly resource_code: string;
  readonly resource_name: string;
  readonly workshop_id: string;
  readonly source_workshop_id: string;
  readonly workshop_code: string;
  readonly workshop_name: string;
  readonly start: TimePair;
  readonly end: TimePair;
  readonly duration_seconds: number;
  readonly operation_state: OperationState;
  readonly candidate_resource_count: number;
  readonly lock_ids: readonly string[];
  readonly execution_fact_ids: readonly string[];
  readonly protection: AssignmentProtection;
}

export interface ExecutionSegment {
  readonly execution_fact_id: string;
  readonly operation_id: string;
  readonly demand_order_id: string;
  readonly resource_id: string;
  readonly resource_code: string;
  readonly status: "COMPLETED" | "RUNNING";
  readonly actual_start: TimePair;
  readonly actual_end: TimePair | null;
  readonly remaining_seconds: number | null;
}

export interface ResourceLoad {
  readonly resource_id: string;
  readonly source_resource_id: string;
  readonly resource_code: string;
  readonly resource_name: string;
  readonly workshop_id: string;
  readonly workshop_code: string;
  readonly available_seconds: number;
  readonly planned_busy_seconds: number;
  readonly utilization: number | null;
  readonly formula: "planned_busy_seconds / available_seconds";
  readonly evidence: ArtifactReference;
}

export interface DemoScheduleView {
  readonly view_version: "cnc-demo-schedule-view.v1";
  readonly run_id: string;
  readonly scenario_id: string;
  readonly timezone: string;
  readonly version: DemoScheduleSummary["version"] & {
    readonly source_kind: string;
    readonly parent_schedule_version_id: string | null;
  };
  readonly solver: DemoScheduleSummary["solver"] & {
    readonly solver_report_version: "solver-report.v1" | "solver-report.v2";
    readonly report_id: string;
    readonly evidence_kind: "SOLVER_RUN";
    readonly objective_value: number | null;
    readonly best_bound: number | null;
    readonly relative_gap: number | null;
  };
  readonly validation: DemoScheduleSummary["validation"] & {
    readonly validation_report_version: "validation-report.v2";
  };
  readonly kpis: DemoScheduleSummary["kpis"] & {
    readonly kpi_id: string;
    readonly kpi_version: "kpi.v2";
    readonly delivery: DemoScheduleSummary["kpis"]["delivery"] & {
      readonly priority_weighted_tardiness_seconds: number;
    };
    readonly stability: {
      readonly status: string;
      readonly changed_operation_count: number | null;
      readonly resource_changed_count: number | null;
      readonly start_shift_seconds: number | null;
      readonly schedule_stability_ratio: number | null;
    };
  };
  readonly orders: readonly ScheduleOrder[];
  readonly resources: readonly ResourceLoad[];
  readonly execution_segments: readonly ExecutionSegment[];
  readonly assignments: readonly ScheduleAssignment[];
  readonly query: SchedulePresentationQuery;
  readonly page: PageInfo;
  readonly provenance: {
    readonly planning_run_id: string;
    readonly schedule_content_fingerprint: string;
    readonly artifacts: readonly ArtifactReference[];
  };
  readonly boundary: PresentationBoundary;
  readonly view_fingerprint: string;
}

export interface DemoScheduleSummary {
  readonly view_version: "cnc-demo-schedule-view.v1";
  readonly run_id: string;
  readonly scenario_id: string;
  readonly timezone: string;
  readonly version: {
    readonly schedule_version_id: string;
    readonly contract_version: "schedule-version.v1" | "schedule-version.v2";
    readonly revision: number;
    readonly state: ScheduleState;
    readonly content_fingerprint: string;
    readonly created_at: TimePair;
  };
  readonly solver: {
    readonly solver_status: "OPTIMAL" | "FEASIBLE";
    readonly limit_seconds: number;
    readonly solve_seconds: number;
    readonly total_seconds: number;
    readonly optimality_claim: boolean;
  };
  readonly validation: {
    readonly status: "PASS";
    readonly hard_violation_count: 0;
    readonly fingerprint: string;
  };
  readonly kpis: {
    readonly fingerprint: string;
    readonly delivery: {
      readonly order_count: number;
      readonly on_time_order_count: number;
      readonly on_time_order_ratio: number | null;
      readonly late_order_count: number;
      readonly total_tardiness_seconds: number;
    };
    readonly planning: {
      readonly makespan_seconds: number;
      readonly scheduled_operation_count: number;
      readonly unscheduled_operation_count: number;
    };
  };
  readonly boundary: {
    readonly data_plane: "SIMULATION";
    readonly simulation_only: true;
    readonly production_authority: false;
    readonly publishable: false;
  };
  readonly view_fingerprint: string;
}

export interface UrgentOrderCommand {
  readonly command_version: "cnc-demo-urgent-order-command.v1";
  readonly expected_run_id: string;
  readonly expected_base_version_id: string;
  readonly route_template_id: string;
  readonly quantity: number;
  readonly due_at_local: string;
  readonly priority_class: PriorityClass;
  readonly note: string | null;
}

export interface UrgentOrderInput {
  readonly route_template_id: string;
  readonly quantity: number;
  readonly due_at_local: string;
  readonly priority_class: PriorityClass;
  readonly note: string | null;
}

export interface UrgentReplanResult {
  readonly result_version: "cnc-demo-urgent-replan-result.v1";
  readonly run_id: string;
  readonly demand_order_id: string;
  readonly event_id: string;
  readonly snapshot_id: string;
  readonly problem_hash: string;
  readonly request_id: string;
  readonly attempt_id: string;
  readonly schedule_version_id: string;
  readonly schedule_state: "DRAFT";
  readonly solver_status: "OPTIMAL" | "FEASIBLE";
  readonly validation_status: "PASS";
  readonly change_report_id: string;
  readonly operation_changes: {
    readonly ADDED: number;
    readonly CHANGED: number;
    readonly UNCHANGED: number;
  };
  readonly current_published_version_id: string;
  readonly exact_replay: boolean;
}

export type ChangeClassification =
  | "UNCHANGED"
  | "CHANGED"
  | "ADDED"
  | "REMOVED_BY_FACT";

export type ComparisonSort = "OPERATION_ASC" | "SHIFT_DESC" | "START_ASC";

export interface ComparisonPresentationQuery {
  readonly classifications: readonly ChangeClassification[];
  readonly resource_ids: readonly string[];
  readonly workshop_ids: readonly string[];
  readonly demand_order_ids: readonly string[];
  readonly start_at_utc: string | null;
  readonly end_at_utc: string | null;
  readonly sort: ComparisonSort;
  readonly offset: number;
  readonly limit: number;
}

export interface ComparisonQueryInput {
  readonly classifications?: readonly ChangeClassification[];
  readonly resource_ids?: readonly string[];
  readonly workshop_ids?: readonly string[];
  readonly demand_order_ids?: readonly string[];
  readonly start_at_utc?: string | null;
  readonly end_at_utc?: string | null;
  readonly sort?: ComparisonSort;
  readonly offset?: number;
  readonly limit?: number;
}

export interface ComparisonVersionSummary {
  readonly schedule_version_id: string;
  readonly contract_version: "schedule-version.v1" | "schedule-version.v2";
  readonly revision: number;
  readonly state: ScheduleState;
  readonly source_kind: string;
  readonly parent_schedule_version_id: string | null;
  readonly content_fingerprint: string;
  readonly created_at: TimePair;
}

export interface ComparisonKpiSummary {
  readonly kpi_id: string;
  readonly kpi_version: "kpi.v2";
  readonly fingerprint: string;
  readonly delivery: {
    readonly order_count: number;
    readonly on_time_order_count: number;
    readonly on_time_order_ratio: number | null;
    readonly late_order_count: number;
    readonly total_tardiness_seconds: number;
    readonly priority_weighted_tardiness_seconds: number;
  };
  readonly planning: {
    readonly makespan_seconds: number;
    readonly scheduled_operation_count: number;
    readonly unscheduled_operation_count: number;
  };
  readonly stability: {
    readonly status: string;
    readonly changed_operation_count: number | null;
    readonly resource_changed_count: number | null;
    readonly start_shift_seconds: number | null;
    readonly schedule_stability_ratio: number | null;
  };
}

export interface ComparisonAssignment {
  readonly resource_id: string;
  readonly source_resource_id: string;
  readonly resource_code: string;
  readonly workshop_id: string;
  readonly workshop_code: string;
  readonly start: TimePair;
  readonly end: TimePair;
  readonly duration_seconds: number;
}

export interface ComparisonOperation {
  readonly operation_id: string;
  readonly operation_code: string;
  readonly operation_name: string;
  readonly demand_order_id: string;
  readonly order_code: string;
  readonly classification: ChangeClassification;
  readonly base_assignment: ComparisonAssignment | null;
  readonly new_assignment: ComparisonAssignment | null;
  readonly deltas: {
    readonly resource_changed: boolean;
    readonly start_shift_seconds: number;
    readonly absolute_start_shift_seconds: number;
    readonly end_shift_seconds: number;
    readonly duration_delta_seconds: number;
  };
  readonly reason_codes: readonly string[];
}

export interface DemoComparisonView {
  readonly view_version: "cnc-demo-comparison-view.v1";
  readonly run_id: string;
  readonly scenario_id: string;
  readonly request_id: string;
  readonly timezone: string;
  readonly before: ComparisonVersionSummary;
  readonly after: ComparisonVersionSummary;
  readonly before_kpis: ComparisonKpiSummary;
  readonly after_kpis: ComparisonKpiSummary;
  readonly delivery_delta: {
    readonly order_count: number;
    readonly on_time_order_count: number;
    readonly on_time_order_ratio: number | null;
    readonly late_order_count: number;
    readonly total_tardiness_seconds: number;
    readonly priority_weighted_tardiness_seconds: number;
    readonly makespan_seconds: number;
    readonly formula: "after - before";
  };
  readonly operation_universe_count: number;
  readonly change_counts: {
    readonly unchanged: number;
    readonly changed: number;
    readonly added: number;
    readonly removed_by_fact: number;
  };
  readonly stability: {
    readonly soft_lock_violations: number;
    readonly changed_existing_operations: number;
    readonly resource_changes: number;
    readonly absolute_start_shift_seconds: number;
    readonly unchanged_existing: number;
    readonly comparable_existing: number;
    readonly unchanged_ratio: number | null;
  };
  readonly affected_orders: readonly {
    readonly demand_order_id: string;
    readonly order_code: string;
    readonly change_count: number;
  }[];
  readonly operations: readonly ComparisonOperation[];
  readonly query: ComparisonPresentationQuery;
  readonly page: PageInfo;
  readonly provenance: {
    readonly attempt_id: string;
    readonly result_id: string;
    readonly result_fingerprint: string;
    readonly change_report: ArtifactReference;
    readonly before_kpi: ArtifactReference;
    readonly after_kpi: ArtifactReference;
    readonly validation_status: "PASS";
  };
  readonly boundary: PresentationBoundary;
  readonly view_fingerprint: string;
}

export interface BaselineActivationRequest {
  readonly command_version: "cnc-demo-baseline-activation.v1";
  readonly expected_run_id: string;
  readonly schedule_version_id: string;
  readonly content_fingerprint: string;
  readonly expected_state_revision: number;
  readonly confirmation: "ACTIVATE_SIMULATION_BASELINE";
}

export interface BaselineActivationResult {
  readonly result_version: "cnc-demo-baseline-activation-result.v1";
  readonly run_id: string;
  readonly schedule_version_id: string;
  readonly content_fingerprint: string;
  readonly state: "PUBLISHED";
  readonly state_revision: number;
  readonly publication_id: string;
  readonly current_reference_revision: number;
  readonly replayed: boolean;
}

export interface DemoErrorDocument {
  readonly error_version: "cnc-demo-error.v1";
  readonly code: string;
  readonly field: string;
  readonly correlation_id: string;
}
