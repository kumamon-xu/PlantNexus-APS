import type { JsonObject } from "../api/types";

export const planningRunStates = [
  "CREATED",
  "INGESTING",
  "VALIDATING",
  "SNAPSHOTTED",
  "BUILDING",
  "SOLVING",
  "SOLVED",
  "VERIFYING",
  "COMPLETED",
  "DATA_REJECTED",
  "MODEL_INVALID",
  "INFEASIBLE",
  "NO_SOLUTION_WITHIN_LIMIT",
  "VALIDATION_FAILED",
  "CANCELLED",
  "FAILED",
] as const;

export type PlanningRunState = (typeof planningRunStates)[number];
export type PlanningRunAction = "READ" | "CANCEL";

export interface EffectiveScope {
  tenant_id: string;
  factory_id: string;
  planning_scope_id: string;
  data_plane: "SIMULATION" | "PRODUCTION";
  environment: "DEVELOPMENT" | "TEST" | "BENCHMARK" | "PRODUCTION";
  scope_fingerprint: string;
}

export interface ArtifactReference {
  document_version: string;
  artifact_id: string;
  fingerprint: string;
}

export interface ExtensionSetReference {
  extension_set_id: string;
  extension_set_fingerprint: string;
  configuration_fingerprint: string;
}

export interface RuntimeResolution {
  runtime_resolution_version: "runtime-resolution.v1";
  runtime_version: string;
  runtime_artifact_fingerprint: string;
  core_version: string;
  core_artifact_fingerprint: string;
  extension_sdk_version: string;
  registry_protocol_version: string;
  extension_set: ExtensionSetReference;
  developer_kit_version: string;
  developer_kit_fingerprint: string;
  solver_backend_id: string;
  solver_backend_version: string;
  validator_version: string;
  resolution_fingerprint: string;
}

export interface HeadlessError {
  error_version: "headless-error.v1";
  namespace: "HEADLESS_RUNTIME";
  registry_version: "headless-error-code-registry.v1";
  category: string;
  code: string;
  stage: string;
  message: string;
  pointer: string | null;
  entity_reference: string | null;
  expected_contract: string | null;
  correlation_id: string;
  retryability: string;
  action: string;
}

export interface PlanningRunAttempt {
  attempt_id: string;
  attempt_number: number;
  runtime_resolution_fingerprint: string;
  started_at_utc: string;
  finished_at_utc: string | null;
}

export interface PlanningRunArtifacts {
  import_quality_report: ArtifactReference | null;
  snapshot: ArtifactReference | null;
  problem: ArtifactReference | null;
  planning_solution: ArtifactReference | null;
  solver_report: ArtifactReference | null;
  validation_report: ArtifactReference | null;
  schedule_version: ArtifactReference | null;
}

export interface PlanningRun {
  planning_run_version: "planning-run.v1";
  schema_set_version: "2.10.0";
  canonicalization_version: "canonical-json.v1";
  transition_registry_version: "state-machines.v1";
  error_registry_version: "headless-error-code-registry.v1";
  planning_run_id: string;
  revision: number;
  state: PlanningRunState;
  terminal: boolean;
  allowed_actions: PlanningRunAction[];
  effective_scope: EffectiveScope;
  ingress: JsonObject;
  runtime_resolution: RuntimeResolution;
  inputs: JsonObject;
  attempt: PlanningRunAttempt | null;
  artifacts: PlanningRunArtifacts;
  cancellation: JsonObject | null;
  error: HeadlessError | null;
  last_transition: JsonObject;
  audit_references: ArtifactReference[];
  created_at_utc: string;
  updated_at_utc: string;
  run_fingerprint: string;
}

export interface CanonicalIngressRequestProjection {
  raw: string;
  document: JsonObject;
  requestId: string;
  correlationId: string;
  idempotencyKey: string;
  requestFingerprint: string;
  requestedScope: EffectiveScope;
}

export interface AcceptedPlanningRunReference {
  document_version: "planning-run.v1";
  planning_run_id: string;
  revision: number;
  state: "CREATED";
  run_fingerprint: string;
}

export interface AcceptedIngress {
  ingress_id: string;
  payload: ArtifactReference;
  runtime_resolution: RuntimeResolution;
  planning_run: AcceptedPlanningRunReference;
  audit: ArtifactReference;
}

export interface CanonicalIngressResult {
  canonical_ingress_result_version: "canonical-ingress-result.v1";
  schema_set_version: "2.10.0";
  canonicalization_version: "canonical-json.v1";
  result_id: string;
  request_id: string;
  correlation_id: string;
  request_fingerprint: string;
  disposition: "ACCEPTED" | "REJECTED";
  side_effects: "PLANNING_RUN_CREATED_OR_REPLAYED" | "NONE";
  idempotency: JsonObject;
  effective_scope: EffectiveScope;
  accepted: AcceptedIngress | null;
  rejection: HeadlessError | null;
  occurred_at_utc: string;
  result_fingerprint: string;
}

export interface PlanningRunCancelAction {
  action_version: "planning-run-cancel-action.v1";
  expected_revision: number;
  expected_state: PlanningRunState;
  expected_run_fingerprint: string;
  reason: string;
}

export interface PlanningRunRetryAction {
  action_version: "planning-run-retry-action.v1";
  expected_revision: number;
  expected_state: PlanningRunState;
  expected_run_fingerprint: string;
  failed_attempt_id: string;
  failed_attempt_number: number;
  reason: string;
}

export type HeadlessClientFailureKind =
  | "authentication_required"
  | "authorization_denied"
  | "contract_error"
  | "version_error"
  | "state_conflict"
  | "outcome_unknown"
  | "unavailable"
  | "server_error";
