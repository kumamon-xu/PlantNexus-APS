import { workspaceCommandFingerprint } from "./canonical";
import type { RuntimeConfig } from "./runtime";
import type {
  ExportJob,
  JsonObject,
  ScheduleVersion,
  WorkspaceCommandDocument,
  WorkspaceCommandType,
  WorkspaceControlState,
} from "./types";

const capabilities: Record<WorkspaceCommandType, string> = {
  MOVE_OPERATION: "edit",
  ASSIGN_RESOURCE: "edit",
  SET_LOCK: "lock",
  REMOVE_LOCK: "lock",
  SUBMIT_FOR_REVIEW: "edit",
  APPROVE: "approve",
  REJECT: "reject",
  PUBLISH: "publish",
  REQUEST_EXPORT: "export",
  RETRY_EXPORT: "export",
  CANCEL_EXPORT: "export",
};

const simulationTarget = new Set<WorkspaceCommandType>([
  "PUBLISH",
  "REQUEST_EXPORT",
  "RETRY_EXPORT",
  "CANCEL_EXPORT",
]);

const credentialLike = /(?:bearer\s|password|passwd|secret|token\s*=|api[_-]?key)/iu;

function identity(prefix: string): string {
  return `${prefix}-${globalThis.crypto.randomUUID()}`;
}

function safeReason(value: string): string {
  const result = value.trim();
  if (
    result.length < 3 ||
    result.length > 512 ||
    /[\u0000-\u001f\u007f]/u.test(result) ||
    credentialLike.test(result)
  ) {
    throw new TypeError("Action reason must be non-empty and credential-safe");
  }
  return result;
}

interface CommandSource {
  sourceId: string;
  expectedState: WorkspaceControlState;
  contentFingerprint: string;
  synthetic: boolean;
  syntheticProvenance: JsonObject | null;
}

export interface CommandIdentity {
  idempotencyKey: string;
  commandId: string;
  correlationId: string;
}

export function createCommandIdentity(): CommandIdentity {
  return {
    idempotencyKey: identity("p3-human-control"),
    commandId: identity("command-ui"),
    correlationId: identity("correlation-ui"),
  };
}

function requireSimulationRuntime(config: RuntimeConfig, source: CommandSource): void {
  if (
    config.dataPlane !== "SIMULATION" ||
    config.environment === "PRODUCTION" ||
    !config.synthetic ||
    !source.synthetic ||
    source.syntheticProvenance === null
  ) {
    throw new TypeError(
      "P3 human controls are restricted to the isolated synthetic Simulation runtime",
    );
  }
}

async function buildCommand(
  config: RuntimeConfig,
  source: CommandSource,
  commandType: WorkspaceCommandType,
  payload: JsonObject,
  reason: string,
  commandIdentity: CommandIdentity,
): Promise<WorkspaceCommandDocument> {
  requireSimulationRuntime(config, source);
  const syntheticProvenance = source.syntheticProvenance;
  if (syntheticProvenance === null) {
    throw new TypeError("Synthetic command provenance is required");
  }
  const target = simulationTarget.has(commandType)
    ? "SIMULATION_INTERNAL"
    : "WORKSPACE_INTERNAL";
  const document: WorkspaceCommandDocument = {
    workspace_command_version: "workspace-command.v1",
    schema_set_version: "2.6.0",
    canonicalization_version: "canonical-json.v1",
    command_id: commandIdentity.commandId,
    command_type: commandType,
    required_capability: capabilities[commandType],
    idempotency_key: commandIdentity.idempotencyKey,
    idempotency_scope: `${config.dataPlane}/${commandType}/${source.sourceId}/${target}`,
    request_fingerprint: `sha256:${"0".repeat(64)}`,
    source_id: source.sourceId,
    expected_state: source.expectedState,
    expected_content_fingerprint: source.contentFingerprint,
    data_plane: config.dataPlane,
    environment: config.environment,
    synthetic: true,
    synthetic_provenance: syntheticProvenance,
    target,
    reason: safeReason(reason),
    correlation_id: commandIdentity.correlationId,
    payload,
  };
  document.request_fingerprint = await workspaceCommandFingerprint(document);
  return document;
}

export function buildScheduleVersionCommand(
  config: RuntimeConfig,
  version: ScheduleVersion,
  commandType: Exclude<WorkspaceCommandType, "RETRY_EXPORT" | "CANCEL_EXPORT">,
  payload: JsonObject,
  reason: string,
  commandIdentity: CommandIdentity = createCommandIdentity(),
): Promise<WorkspaceCommandDocument> {
  return buildCommand(
    config,
    {
      sourceId: version.schedule_version_id,
      expectedState: version.state,
      contentFingerprint: version.content_fingerprint,
      synthetic: version.synthetic,
      syntheticProvenance: version.synthetic_provenance,
    },
    commandType,
    payload,
    reason,
    commandIdentity,
  );
}

export function buildExportJobCommand(
  config: RuntimeConfig,
  job: ExportJob,
  commandType: "RETRY_EXPORT" | "CANCEL_EXPORT",
  payload: JsonObject,
  reason: string,
  commandIdentity: CommandIdentity = createCommandIdentity(),
): Promise<WorkspaceCommandDocument> {
  return buildCommand(
    config,
    {
      sourceId: job.export_job_id,
      expectedState: job.state,
      contentFingerprint: job.schedule_version.content_fingerprint,
      synthetic: job.synthetic,
      syntheticProvenance: job.synthetic_provenance,
    },
    commandType,
    payload,
    reason,
    commandIdentity,
  );
}
