import type { JsonObject } from "../api/types";
import {
  planningRunStates,
  type AcceptedIngress,
  type ArtifactReference,
  type CanonicalIngressRequestProjection,
  type CanonicalIngressResult,
  type EffectiveScope,
  type HeadlessError,
  type PlanningRun,
  type PlanningRunAction,
  type PlanningRunArtifacts,
  type PlanningRunAttempt,
  type PlanningRunState,
  type RuntimeResolution,
} from "./types";

const fingerprintPattern = /^sha256:[0-9a-f]{64}$/u;
const terminalStates = new Set<PlanningRunState>([
  "COMPLETED",
  "DATA_REJECTED",
  "MODEL_INVALID",
  "INFEASIBLE",
  "NO_SOLUTION_WITHIN_LIMIT",
  "VALIDATION_FAILED",
  "CANCELLED",
  "FAILED",
]);

export class HeadlessContractError extends Error {
  constructor(
    readonly code: "CONTRACT_VIOLATION" | "VERSION_MISMATCH",
    readonly pointer: string,
    message: string,
  ) {
    super(message);
    this.name = "HeadlessContractError";
  }
}

function object(value: unknown, pointer: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      pointer,
      `${pointer} must be an object`,
    );
  }
  return value as Record<string, unknown>;
}

function exact(
  value: Record<string, unknown>,
  fields: readonly string[],
  pointer: string,
): void {
  const actual = Object.keys(value).sort();
  const expected = [...fields].sort();
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      pointer,
      `${pointer} contains missing or unknown fields`,
    );
  }
}

function text(value: unknown, pointer: string): string {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    /[\u0000-\u001f\u007f]/u.test(value)
  ) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      pointer,
      `${pointer} must be a non-empty safe string`,
    );
  }
  return value;
}

function nullableText(value: unknown, pointer: string): string | null {
  return value === null ? null : text(value, pointer);
}

function integer(value: unknown, pointer: string, minimum = 0): number {
  if (!Number.isSafeInteger(value) || (value as number) < minimum) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      pointer,
      `${pointer} must be a safe integer >= ${minimum}`,
    );
  }
  return value as number;
}

function fingerprint(value: unknown, pointer: string): string {
  const result = text(value, pointer);
  if (!fingerprintPattern.test(result)) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      pointer,
      `${pointer} must be a SHA-256 fingerprint`,
    );
  }
  return result;
}

function constant<T extends string>(
  value: unknown,
  expected: T,
  pointer: string,
): T {
  if (value !== expected) {
    throw new HeadlessContractError(
      "VERSION_MISMATCH",
      pointer,
      `${pointer} must be ${expected}`,
    );
  }
  return expected;
}

function parseScope(value: unknown, pointer: string): EffectiveScope {
  const source = object(value, pointer);
  exact(
    source,
    [
      "tenant_id",
      "factory_id",
      "planning_scope_id",
      "data_plane",
      "environment",
      "scope_fingerprint",
    ],
    pointer,
  );
  const dataPlane = text(source.data_plane, `${pointer}/data_plane`);
  const environment = text(source.environment, `${pointer}/environment`);
  if (dataPlane !== "SIMULATION" && dataPlane !== "PRODUCTION") {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      `${pointer}/data_plane`,
      "unknown data plane",
    );
  }
  if (!(["DEVELOPMENT", "TEST", "BENCHMARK", "PRODUCTION"] as const).includes(
    environment as EffectiveScope["environment"],
  )) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      `${pointer}/environment`,
      "unknown Runtime environment",
    );
  }
  if (
    (dataPlane === "PRODUCTION") !== (environment === "PRODUCTION")
  ) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      pointer,
      "data plane and Runtime environment are inconsistent",
    );
  }
  return {
    tenant_id: text(source.tenant_id, `${pointer}/tenant_id`),
    factory_id: text(source.factory_id, `${pointer}/factory_id`),
    planning_scope_id: text(
      source.planning_scope_id,
      `${pointer}/planning_scope_id`,
    ),
    data_plane: dataPlane,
    environment: environment as EffectiveScope["environment"],
    scope_fingerprint: fingerprint(
      source.scope_fingerprint,
      `${pointer}/scope_fingerprint`,
    ),
  };
}

function parseRequestedScope(value: unknown, pointer: string): EffectiveScope {
  const source = object(value, pointer);
  exact(
    source,
    ["tenant_id", "factory_id", "planning_scope_id", "data_plane", "environment"],
    pointer,
  );
  const withFingerprint = {
    ...source,
    scope_fingerprint: `sha256:${"0".repeat(64)}`,
  };
  return parseScope(withFingerprint, pointer);
}

function parseArtifact(value: unknown, pointer: string): ArtifactReference {
  const source = object(value, pointer);
  exact(source, ["document_version", "artifact_id", "fingerprint"], pointer);
  return {
    document_version: text(source.document_version, `${pointer}/document_version`),
    artifact_id: text(source.artifact_id, `${pointer}/artifact_id`),
    fingerprint: fingerprint(source.fingerprint, `${pointer}/fingerprint`),
  };
}

function parseRuntime(value: unknown, pointer: string): RuntimeResolution {
  const source = object(value, pointer);
  exact(
    source,
    [
      "runtime_resolution_version",
      "runtime_version",
      "runtime_artifact_fingerprint",
      "core_version",
      "core_artifact_fingerprint",
      "extension_sdk_version",
      "registry_protocol_version",
      "extension_set",
      "developer_kit_version",
      "developer_kit_fingerprint",
      "solver_backend_id",
      "solver_backend_version",
      "validator_version",
      "resolution_fingerprint",
    ],
    pointer,
  );
  const extension = object(source.extension_set, `${pointer}/extension_set`);
  exact(
    extension,
    [
      "extension_set_id",
      "extension_set_fingerprint",
      "configuration_fingerprint",
    ],
    `${pointer}/extension_set`,
  );
  return {
    runtime_resolution_version: constant(
      source.runtime_resolution_version,
      "runtime-resolution.v1",
      `${pointer}/runtime_resolution_version`,
    ),
    runtime_version: text(source.runtime_version, `${pointer}/runtime_version`),
    runtime_artifact_fingerprint: fingerprint(
      source.runtime_artifact_fingerprint,
      `${pointer}/runtime_artifact_fingerprint`,
    ),
    core_version: text(source.core_version, `${pointer}/core_version`),
    core_artifact_fingerprint: fingerprint(
      source.core_artifact_fingerprint,
      `${pointer}/core_artifact_fingerprint`,
    ),
    extension_sdk_version: text(
      source.extension_sdk_version,
      `${pointer}/extension_sdk_version`,
    ),
    registry_protocol_version: text(
      source.registry_protocol_version,
      `${pointer}/registry_protocol_version`,
    ),
    extension_set: {
      extension_set_id: text(
        extension.extension_set_id,
        `${pointer}/extension_set/extension_set_id`,
      ),
      extension_set_fingerprint: fingerprint(
        extension.extension_set_fingerprint,
        `${pointer}/extension_set/extension_set_fingerprint`,
      ),
      configuration_fingerprint: fingerprint(
        extension.configuration_fingerprint,
        `${pointer}/extension_set/configuration_fingerprint`,
      ),
    },
    developer_kit_version: text(
      source.developer_kit_version,
      `${pointer}/developer_kit_version`,
    ),
    developer_kit_fingerprint: fingerprint(
      source.developer_kit_fingerprint,
      `${pointer}/developer_kit_fingerprint`,
    ),
    solver_backend_id: text(
      source.solver_backend_id,
      `${pointer}/solver_backend_id`,
    ),
    solver_backend_version: text(
      source.solver_backend_version,
      `${pointer}/solver_backend_version`,
    ),
    validator_version: text(
      source.validator_version,
      `${pointer}/validator_version`,
    ),
    resolution_fingerprint: fingerprint(
      source.resolution_fingerprint,
      `${pointer}/resolution_fingerprint`,
    ),
  };
}

export function parseHeadlessError(value: unknown, pointer = "/error"): HeadlessError {
  const source = object(value, pointer);
  exact(
    source,
    [
      "error_version",
      "namespace",
      "registry_version",
      "category",
      "code",
      "stage",
      "message",
      "pointer",
      "entity_reference",
      "expected_contract",
      "correlation_id",
      "retryability",
      "action",
    ],
    pointer,
  );
  return {
    error_version: constant(
      source.error_version,
      "headless-error.v1",
      `${pointer}/error_version`,
    ),
    namespace: constant(source.namespace, "HEADLESS_RUNTIME", `${pointer}/namespace`),
    registry_version: constant(
      source.registry_version,
      "headless-error-code-registry.v1",
      `${pointer}/registry_version`,
    ),
    category: text(source.category, `${pointer}/category`),
    code: text(source.code, `${pointer}/code`),
    stage: text(source.stage, `${pointer}/stage`),
    message: text(source.message, `${pointer}/message`),
    pointer: nullableText(source.pointer, `${pointer}/pointer`),
    entity_reference: nullableText(
      source.entity_reference,
      `${pointer}/entity_reference`,
    ),
    expected_contract: nullableText(
      source.expected_contract,
      `${pointer}/expected_contract`,
    ),
    correlation_id: text(source.correlation_id, `${pointer}/correlation_id`),
    retryability: text(source.retryability, `${pointer}/retryability`),
    action: text(source.action, `${pointer}/action`),
  };
}

export function parseCanonicalIngressRequestText(
  raw: string,
): CanonicalIngressRequestProjection {
  if (new TextEncoder().encode(raw).length > 8 * 1024 * 1024) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      "/",
      "canonical request exceeds the 8 MiB transport limit",
    );
  }
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      "/",
      "canonical request is not valid JSON",
    );
  }
  const source = object(value, "/");
  exact(
    source,
    [
      "canonical_ingress_request_version",
      "schema_set_version",
      "ingress_policy_version",
      "canonicalization_version",
      "operation",
      "request_id",
      "correlation_id",
      "idempotency_key",
      "request_fingerprint",
      "requested_scope",
      "source_authority",
      "planning_inputs",
      "payload_fingerprint",
      "payload",
    ],
    "/",
  );
  constant(
    source.canonical_ingress_request_version,
    "canonical-ingress-request.v1",
    "/canonical_ingress_request_version",
  );
  constant(source.schema_set_version, "2.10.0", "/schema_set_version");
  constant(
    source.ingress_policy_version,
    "canonical-ingress-policy.v1",
    "/ingress_policy_version",
  );
  constant(
    source.canonicalization_version,
    "canonical-json.v1",
    "/canonicalization_version",
  );
  constant(source.operation, "CREATE_PLANNING_RUN", "/operation");
  fingerprint(source.request_fingerprint, "/request_fingerprint");
  fingerprint(source.payload_fingerprint, "/payload_fingerprint");
  object(source.source_authority, "/source_authority");
  object(source.planning_inputs, "/planning_inputs");
  object(source.payload, "/payload");
  return {
    raw,
    document: source as JsonObject,
    requestId: text(source.request_id, "/request_id"),
    correlationId: text(source.correlation_id, "/correlation_id"),
    idempotencyKey: text(source.idempotency_key, "/idempotency_key"),
    requestFingerprint: fingerprint(
      source.request_fingerprint,
      "/request_fingerprint",
    ),
    requestedScope: parseRequestedScope(source.requested_scope, "/requested_scope"),
  };
}

function parseAccepted(value: unknown, pointer: string): AcceptedIngress {
  const source = object(value, pointer);
  exact(
    source,
    ["ingress_id", "payload", "runtime_resolution", "planning_run", "audit"],
    pointer,
  );
  const run = object(source.planning_run, `${pointer}/planning_run`);
  exact(
    run,
    ["document_version", "planning_run_id", "revision", "state", "run_fingerprint"],
    `${pointer}/planning_run`,
  );
  return {
    ingress_id: text(source.ingress_id, `${pointer}/ingress_id`),
    payload: parseArtifact(source.payload, `${pointer}/payload`),
    runtime_resolution: parseRuntime(
      source.runtime_resolution,
      `${pointer}/runtime_resolution`,
    ),
    planning_run: {
      document_version: constant(
        run.document_version,
        "planning-run.v1",
        `${pointer}/planning_run/document_version`,
      ),
      planning_run_id: text(
        run.planning_run_id,
        `${pointer}/planning_run/planning_run_id`,
      ),
      revision: integer(run.revision, `${pointer}/planning_run/revision`, 1),
      state: constant(run.state, "CREATED", `${pointer}/planning_run/state`),
      run_fingerprint: fingerprint(
        run.run_fingerprint,
        `${pointer}/planning_run/run_fingerprint`,
      ),
    },
    audit: parseArtifact(source.audit, `${pointer}/audit`),
  };
}

export function parseCanonicalIngressResult(
  value: unknown,
  request?: CanonicalIngressRequestProjection,
): CanonicalIngressResult {
  const source = object(value, "/result");
  exact(
    source,
    [
      "canonical_ingress_result_version",
      "schema_set_version",
      "canonicalization_version",
      "result_id",
      "request_id",
      "correlation_id",
      "request_fingerprint",
      "disposition",
      "side_effects",
      "idempotency",
      "effective_scope",
      "accepted",
      "rejection",
      "occurred_at_utc",
      "result_fingerprint",
    ],
    "/result",
  );
  const disposition = text(source.disposition, "/result/disposition");
  if (disposition !== "ACCEPTED" && disposition !== "REJECTED") {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      "/result/disposition",
      "unknown ingress disposition",
    );
  }
  const accepted = source.accepted === null ? null : parseAccepted(source.accepted, "/result/accepted");
  const rejection =
    source.rejection === null
      ? null
      : parseHeadlessError(source.rejection, "/result/rejection");
  if (
    (disposition === "ACCEPTED" && (accepted === null || rejection !== null)) ||
    (disposition === "REJECTED" && (accepted !== null || rejection === null))
  ) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      "/result",
      "ingress disposition and result branches disagree",
    );
  }
  const sideEffects = text(source.side_effects, "/result/side_effects");
  const expectedSideEffects =
    disposition === "ACCEPTED" ? "PLANNING_RUN_CREATED_OR_REPLAYED" : "NONE";
  if (sideEffects !== expectedSideEffects) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      "/result/side_effects",
      "ingress side effects disagree with disposition",
    );
  }
  const result: CanonicalIngressResult = {
    canonical_ingress_result_version: constant(
      source.canonical_ingress_result_version,
      "canonical-ingress-result.v1",
      "/result/canonical_ingress_result_version",
    ),
    schema_set_version: constant(
      source.schema_set_version,
      "2.10.0",
      "/result/schema_set_version",
    ),
    canonicalization_version: constant(
      source.canonicalization_version,
      "canonical-json.v1",
      "/result/canonicalization_version",
    ),
    result_id: text(source.result_id, "/result/result_id"),
    request_id: text(source.request_id, "/result/request_id"),
    correlation_id: text(source.correlation_id, "/result/correlation_id"),
    request_fingerprint: fingerprint(
      source.request_fingerprint,
      "/result/request_fingerprint",
    ),
    disposition,
    side_effects: expectedSideEffects,
    idempotency: object(source.idempotency, "/result/idempotency") as JsonObject,
    effective_scope: parseScope(source.effective_scope, "/result/effective_scope"),
    accepted,
    rejection,
    occurred_at_utc: text(source.occurred_at_utc, "/result/occurred_at_utc"),
    result_fingerprint: fingerprint(
      source.result_fingerprint,
      "/result/result_fingerprint",
    ),
  };
  if (
    request !== undefined &&
    (result.request_id !== request.requestId ||
      result.correlation_id !== request.correlationId ||
      result.request_fingerprint !== request.requestFingerprint)
  ) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      "/result",
      "ingress result is not bound to the submitted request",
    );
  }
  return result;
}

function parseAttempt(value: unknown, pointer: string): PlanningRunAttempt | null {
  if (value === null) return null;
  const source = object(value, pointer);
  exact(
    source,
    [
      "attempt_id",
      "attempt_number",
      "runtime_resolution_fingerprint",
      "started_at_utc",
      "finished_at_utc",
    ],
    pointer,
  );
  return {
    attempt_id: text(source.attempt_id, `${pointer}/attempt_id`),
    attempt_number: integer(source.attempt_number, `${pointer}/attempt_number`, 1),
    runtime_resolution_fingerprint: fingerprint(
      source.runtime_resolution_fingerprint,
      `${pointer}/runtime_resolution_fingerprint`,
    ),
    started_at_utc: text(source.started_at_utc, `${pointer}/started_at_utc`),
    finished_at_utc: nullableText(
      source.finished_at_utc,
      `${pointer}/finished_at_utc`,
    ),
  };
}

function parseArtifacts(value: unknown, pointer: string): PlanningRunArtifacts {
  const source = object(value, pointer);
  const fields = [
    "import_quality_report",
    "snapshot",
    "problem",
    "planning_solution",
    "solver_report",
    "validation_report",
    "schedule_version",
  ] as const;
  exact(source, fields, pointer);
  return Object.fromEntries(
    fields.map((field) => [
      field,
      source[field] === null
        ? null
        : parseArtifact(source[field], `${pointer}/${field}`),
    ]),
  ) as unknown as PlanningRunArtifacts;
}

export function parsePlanningRun(value: unknown): PlanningRun {
  const source = object(value, "/planning_run");
  exact(
    source,
    [
      "planning_run_version",
      "schema_set_version",
      "canonicalization_version",
      "transition_registry_version",
      "error_registry_version",
      "planning_run_id",
      "revision",
      "state",
      "terminal",
      "allowed_actions",
      "effective_scope",
      "ingress",
      "runtime_resolution",
      "inputs",
      "attempt",
      "artifacts",
      "cancellation",
      "error",
      "last_transition",
      "audit_references",
      "created_at_utc",
      "updated_at_utc",
      "run_fingerprint",
    ],
    "/planning_run",
  );
  const state = text(source.state, "/planning_run/state");
  if (!planningRunStates.includes(state as PlanningRunState)) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      "/planning_run/state",
      "unknown PlanningRun state",
    );
  }
  const typedState = state as PlanningRunState;
  const terminal = terminalStates.has(typedState);
  if (source.terminal !== terminal) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      "/planning_run/terminal",
      "PlanningRun terminal flag disagrees with state",
    );
  }
  const allowed = source.allowed_actions;
  const expectedAllowed: PlanningRunAction[] = terminal
    ? ["READ"]
    : ["READ", "CANCEL"];
  if (!Array.isArray(allowed) || JSON.stringify(allowed) !== JSON.stringify(expectedAllowed)) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      "/planning_run/allowed_actions",
      "PlanningRun allowed actions disagree with server state contract",
    );
  }
  const runtime = parseRuntime(source.runtime_resolution, "/planning_run/runtime_resolution");
  const attempt = parseAttempt(source.attempt, "/planning_run/attempt");
  if (
    attempt !== null &&
    attempt.runtime_resolution_fingerprint !== runtime.resolution_fingerprint
  ) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      "/planning_run/attempt/runtime_resolution_fingerprint",
      "attempt Runtime resolution does not match the PlanningRun",
    );
  }
  const transition = object(source.last_transition, "/planning_run/last_transition");
  if (transition.to_state !== typedState) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      "/planning_run/last_transition/to_state",
      "last transition does not match the PlanningRun state",
    );
  }
  if (!Array.isArray(source.audit_references) || source.audit_references.length === 0) {
    throw new HeadlessContractError(
      "CONTRACT_VIOLATION",
      "/planning_run/audit_references",
      "PlanningRun must retain audit references",
    );
  }
  return {
    planning_run_version: constant(
      source.planning_run_version,
      "planning-run.v1",
      "/planning_run/planning_run_version",
    ),
    schema_set_version: constant(
      source.schema_set_version,
      "2.10.0",
      "/planning_run/schema_set_version",
    ),
    canonicalization_version: constant(
      source.canonicalization_version,
      "canonical-json.v1",
      "/planning_run/canonicalization_version",
    ),
    transition_registry_version: constant(
      source.transition_registry_version,
      "state-machines.v1",
      "/planning_run/transition_registry_version",
    ),
    error_registry_version: constant(
      source.error_registry_version,
      "headless-error-code-registry.v1",
      "/planning_run/error_registry_version",
    ),
    planning_run_id: text(source.planning_run_id, "/planning_run/planning_run_id"),
    revision: integer(source.revision, "/planning_run/revision", 1),
    state: typedState,
    terminal,
    allowed_actions: expectedAllowed,
    effective_scope: parseScope(source.effective_scope, "/planning_run/effective_scope"),
    ingress: object(source.ingress, "/planning_run/ingress") as JsonObject,
    runtime_resolution: runtime,
    inputs: object(source.inputs, "/planning_run/inputs") as JsonObject,
    attempt,
    artifacts: parseArtifacts(source.artifacts, "/planning_run/artifacts"),
    cancellation:
      source.cancellation === null
        ? null
        : (object(source.cancellation, "/planning_run/cancellation") as JsonObject),
    error:
      source.error === null
        ? null
        : parseHeadlessError(source.error, "/planning_run/error"),
    last_transition: transition as JsonObject,
    audit_references: source.audit_references.map((item, index) =>
      parseArtifact(item, `/planning_run/audit_references/${index}`),
    ),
    created_at_utc: text(source.created_at_utc, "/planning_run/created_at_utc"),
    updated_at_utc: text(source.updated_at_utc, "/planning_run/updated_at_utc"),
    run_fingerprint: fingerprint(
      source.run_fingerprint,
      "/planning_run/run_fingerprint",
    ),
  };
}

export function sameScope(left: EffectiveScope, right: EffectiveScope): boolean {
  return (
    left.tenant_id === right.tenant_id &&
    left.factory_id === right.factory_id &&
    left.planning_scope_id === right.planning_scope_id &&
    left.data_plane === right.data_plane &&
    left.environment === right.environment
  );
}
