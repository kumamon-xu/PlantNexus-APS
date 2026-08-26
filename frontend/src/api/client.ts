import {
  canonicalJson,
  sha256BytesFingerprint,
  workspaceQueryFingerprint,
} from "./canonical";
import {
  ContractViolation,
  isJsonObject,
  parsePlanningRun,
  parseExportJob,
  parseScheduleVersion,
  parseVersionComparison,
  parseWorkspaceActionResult,
  parseWorkspaceResponse,
} from "./contracts";
import type { RuntimeConfig } from "./runtime";
import type { SessionProvider } from "./session";
import type {
  ClientFailureKind,
  ExportJob,
  ExportPackageDownload,
  JsonObject,
  ScheduleVersion,
  VersionReference,
  WorkspaceHttpResponse,
  WorkspaceActionResult,
  WorkspaceCommandDocument,
  WorkspaceQueryDocument,
  WorkspaceView,
} from "./types";

export class WorkspaceClientError extends Error {
  constructor(
    readonly kind: ClientFailureKind,
    message: string,
    readonly status: number | null,
    readonly correlationId: string | null,
  ) {
    super(message);
    this.name = "WorkspaceClientError";
  }
}

const maxExportArchiveBytes = 70 * 1024 * 1024;

export interface PlanningWorkspaceClient {
  getPlanningRun(planningRunId: string): Promise<JsonObject>;
  getScheduleVersion(scheduleVersionId: string): Promise<ScheduleVersion>;
  getExportJob(exportJobId: string): Promise<ExportJob>;
  executeCommand(command: WorkspaceCommandDocument): Promise<WorkspaceActionResult>;
  downloadExportPackage(exportJobId: string): Promise<ExportPackageDownload>;
  queryWorkspace(
    query: WorkspaceQueryDocument,
    expectedView: WorkspaceView,
  ): Promise<WorkspaceHttpResponse>;
  compareScheduleVersions(
    query: WorkspaceQueryDocument,
    comparedVersion: VersionReference,
  ): Promise<WorkspaceHttpResponse>;
}

function kindForStatus(status: number): ClientFailureKind {
  if (status === 401 || status === 403) return "authorization_denied";
  if (status === 409) return "stale";
  if (status === 404 || status === 422) return "contract_error";
  return "server_error";
}

function safeError(value: unknown, fallback: string): {
  message: string;
  correlationId: string | null;
} {
  if (!isJsonObject(value)) return { message: fallback, correlationId: null };
  return {
    message: typeof value.message === "string" ? value.message : fallback,
    correlationId:
      typeof value.correlation_id === "string" ? value.correlation_id : null,
  };
}

function identityValue(value: string): string {
  const trimmed = value.trim();
  if (trimmed.length === 0 || /[\s\u0000-\u001f\u007f]/u.test(trimmed)) {
    throw new WorkspaceClientError(
      "contract_error",
      "Resource identity is empty or contains a control character",
      null,
      null,
    );
  }
  return trimmed;
}

function pathSegment(value: string): string {
  return encodeURIComponent(identityValue(value));
}

function sameVersionReference(
  left: VersionReference | null,
  right: VersionReference | null,
): boolean {
  if (left === null || right === null) return left === right;
  return (
    left.schedule_version_id === right.schedule_version_id &&
    left.state === right.state &&
    left.content_fingerprint === right.content_fingerprint
  );
}

async function parseBoundWorkspaceResponse(
  value: unknown,
  query: WorkspaceQueryDocument,
  expectedView: WorkspaceView,
): Promise<WorkspaceHttpResponse> {
  if (query.direction !== "REQUEST" || query.view !== expectedView) {
    throw new ContractViolation(
      "request.view",
      "outbound read carrier and expected view must match",
    );
  }
  const response = await parseWorkspaceResponse(value, expectedView);
  if (response.document.query_fingerprint !== query.query_fingerprint) {
    throw new ContractViolation(
      "document.query_fingerprint",
      "response is not bound to the outbound read query",
    );
  }
  if (
    response.document.correlation_id !== query.correlation_id ||
    response.correlation_id !== query.correlation_id
  ) {
    throw new ContractViolation(
      "response.correlation_id",
      "response is not bound to the outbound correlation",
    );
  }
  if (
    !sameVersionReference(
      response.document.result?.authoritative_schedule_version ?? null,
      query.schedule_version_precondition,
    )
  ) {
    throw new ContractViolation(
      "document.result.authoritative_schedule_version",
      "response authority differs from the outbound Version precondition",
    );
  }
  return response;
}

async function requireOutboundQuery(
  query: WorkspaceQueryDocument,
  expectedView: WorkspaceView,
): Promise<void> {
  if (query.direction !== "REQUEST" || query.view !== expectedView) {
    throw new ContractViolation(
      "request.view",
      "outbound read carrier and expected view must match",
    );
  }
  if ((await workspaceQueryFingerprint(query)) !== query.query_fingerprint) {
    throw new ContractViolation(
      "request.query_fingerprint",
      "outbound read carrier fingerprint is invalid",
    );
  }
}

export function createPlanningWorkspaceClient(
  config: RuntimeConfig,
  session: SessionProvider,
  fetcher: typeof fetch = globalThis.fetch,
): PlanningWorkspaceClient {
  async function authorizedHeaders(accept: string): Promise<Headers> {
    const token = await session.getAccessToken();
    const headers = new Headers({ Accept: accept });
    if (token !== null) {
      if (
        token.length === 0 ||
        token.trim() !== token ||
        /[\u0000-\u001f\u007f]/u.test(token)
      ) {
        throw new WorkspaceClientError(
          "authorization_denied",
          "Session provider returned an invalid credential",
          null,
          null,
        );
      }
      headers.set("Authorization", `Bearer ${token}`);
    }
    return headers;
  }

  async function request(
    path: string,
    method: "GET" | "POST",
    body?: JsonObject,
    additionalHeaders?: Readonly<Record<string, string>>,
  ): Promise<unknown> {
    const headers = await authorizedHeaders("application/json");
    if (body !== undefined) headers.set("Content-Type", "application/json");
    for (const [name, value] of Object.entries(additionalHeaders ?? {})) {
      headers.set(name, identityValue(value));
    }
    let response: Response;
    try {
      response = await fetcher(`${config.apiBaseUrl}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : canonicalJson(body),
        cache: "no-store",
        credentials: "omit",
      });
    } catch {
      throw new WorkspaceClientError(
        "server_error",
        "Planning Workspace is unavailable",
        null,
        null,
      );
    }
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new WorkspaceClientError(
        response.ok ? "contract_error" : kindForStatus(response.status),
        "Server returned a non-JSON response",
        response.status,
        response.headers.get("X-Correlation-Id"),
      );
    }
    if (!response.ok) {
      const detail = safeError(payload, `Request failed with HTTP ${response.status}`);
      throw new WorkspaceClientError(
        kindForStatus(response.status),
        detail.message,
        response.status,
        detail.correlationId ?? response.headers.get("X-Correlation-Id"),
      );
    }
    return payload;
  }

  function get(path: string): Promise<unknown> {
    return request(path, "GET");
  }

  async function checked<T>(operation: () => Promise<T>): Promise<T> {
    try {
      return await operation();
    } catch (error) {
      if (error instanceof WorkspaceClientError) throw error;
      if (error instanceof ContractViolation || error instanceof TypeError) {
        throw new WorkspaceClientError("contract_error", error.message, 200, null);
      }
      throw new WorkspaceClientError(
        "contract_error",
        "Server response failed the Planning Workspace contract",
        200,
        null,
      );
    }
  }

  return {
    async getPlanningRun(planningRunId) {
      return checked(async () =>
        parsePlanningRun(await get(`/planning-runs/${pathSegment(planningRunId)}`)),
      );
    },
    async getScheduleVersion(scheduleVersionId) {
      return checked(async () =>
        parseScheduleVersion(
          await get(`/schedule-versions/${pathSegment(scheduleVersionId)}`),
        ),
      );
    },
    async getExportJob(exportJobId) {
      return checked(async () => {
        const expectedId = identityValue(exportJobId);
        const job = parseExportJob(
          await get(`/export-jobs/${pathSegment(expectedId)}`),
        );
        if (job.export_job_id !== expectedId) {
          throw new ContractViolation(
            "export_job.export_job_id",
            "response is not bound to the requested ExportJob",
          );
        }
        return job;
      });
    },
    async executeCommand(command) {
      return checked(async () => {
        const path = commandPath(command);
        const response = await request(path, "POST", command, {
          "Idempotency-Key": command.idempotency_key,
          "X-Correlation-Id": command.correlation_id,
        });
        return parseWorkspaceActionResult(response, command);
      });
    },
    async downloadExportPackage(exportJobId) {
      const correlationId = `correlation-download-${globalThis.crypto.randomUUID()}`;
      const headers = await authorizedHeaders("application/zip");
      headers.set("X-Correlation-Id", correlationId);
      let response: Response;
      try {
        response = await fetcher(
          `${config.apiBaseUrl}/export-jobs/${pathSegment(exportJobId)}/download`,
          {
            method: "GET",
            headers,
            cache: "no-store",
            credentials: "omit",
          },
        );
      } catch {
        throw new WorkspaceClientError(
          "server_error",
          "Export package download outcome is unknown",
          null,
          correlationId,
        );
      }
      if (!response.ok) {
        let payload: unknown = null;
        try {
          payload = await response.json();
        } catch {
          // A failed binary route may still be sanitized without a JSON body.
        }
        const detail = safeError(
          payload,
          `Download failed with HTTP ${response.status}`,
        );
        throw new WorkspaceClientError(
          kindForStatus(response.status),
          detail.message,
          response.status,
          detail.correlationId ?? response.headers.get("X-Correlation-Id"),
        );
      }
      const packageId = response.headers.get("X-PlantNexus-Package-Id");
      const manifestFingerprint = response.headers.get(
        "X-PlantNexus-Manifest-Fingerprint",
      );
      const archiveFingerprint = response.headers.get(
        "X-PlantNexus-Archive-Fingerprint",
      );
      const completionAuditEventId = response.headers.get(
        "X-PlantNexus-Completion-Audit-Event-Id",
      );
      const responseCorrelation = response.headers.get("X-Correlation-Id");
      const disposition = response.headers.get("Content-Disposition");
      const contentLength = response.headers.get("Content-Length");
      const filename = disposition?.match(
        /^attachment; filename="([A-Za-z0-9._-]{1,192}\.zip)"$/u,
      )?.[1];
      if (
        response.headers.get("Content-Type")?.split(";", 1)[0] !==
          "application/zip" ||
        packageId === null ||
        !/^export-package-[0-9a-f]{64}$/u.test(packageId) ||
        filename !== `${packageId}.zip` ||
        manifestFingerprint === null ||
        !/^sha256:[0-9a-f]{64}$/u.test(manifestFingerprint) ||
        archiveFingerprint === null ||
        !/^sha256:[0-9a-f]{64}$/u.test(archiveFingerprint) ||
        completionAuditEventId === null ||
        completionAuditEventId.length === 0 ||
        responseCorrelation !== correlationId ||
        (contentLength !== null &&
          (!/^[0-9]+$/u.test(contentLength) ||
            Number(contentLength) > maxExportArchiveBytes))
      ) {
        throw new WorkspaceClientError(
          "contract_error",
          "Download response headers failed the verified package contract",
          response.status,
          responseCorrelation,
        );
      }
      let bytes: ArrayBuffer;
      try {
        bytes = await response.arrayBuffer();
      } catch {
        throw new WorkspaceClientError(
          "contract_error",
          "Downloaded archive could not be read",
          response.status,
          responseCorrelation,
        );
      }
      if (
        bytes.byteLength === 0 ||
        bytes.byteLength > maxExportArchiveBytes ||
        (await sha256BytesFingerprint(bytes)) !== archiveFingerprint
      ) {
        throw new WorkspaceClientError(
          "contract_error",
          "Downloaded archive fingerprint does not match the server evidence",
          response.status,
          responseCorrelation,
        );
      }
      return {
        blob: new Blob([bytes], { type: "application/zip" }),
        filename,
        packageId,
        manifestFingerprint,
        archiveFingerprint,
        completionAuditEventId,
        correlationId,
      };
    },
    async queryWorkspace(query, expectedView) {
      return checked(async () => {
        await requireOutboundQuery(query, expectedView);
        const encoded = new URLSearchParams({ query: canonicalJson(query) });
        const path =
          query.resource.resource_type === "WORKSPACE"
            ? workspacePath(expectedView)
            : scheduleWorkspacePath(
                String(query.resource.resource_id),
                expectedView,
              );
        return parseBoundWorkspaceResponse(
          await get(`${path}?${encoded}`),
          query,
          expectedView,
        );
      });
    },
    async compareScheduleVersions(query, comparedVersion) {
      return checked(async () => {
        await requireOutboundQuery(query, "VERSION_COMPARISON");
        if (
          query.view !== "VERSION_COMPARISON" ||
          query.query_kind !== "SCHEDULE_VERSION_COMPARISON" ||
          query.schedule_version_precondition === null
        ) {
          throw new TypeError(
            "Version comparison requires its base Version read-query carrier",
          );
        }
        const response = await parseBoundWorkspaceResponse(
          await request(
            "/schedule-version-comparisons",
            "POST",
            query,
            {
              "X-Compared-Schedule-Version-Id": comparedVersion.schedule_version_id,
              "X-Compared-State": comparedVersion.state,
              "X-Compared-Content-Fingerprint": comparedVersion.content_fingerprint,
            },
          ),
          query,
          "VERSION_COMPARISON",
        );
        const comparison = parseVersionComparison(response);
        if (
          !sameVersionReference(
            comparison.base_version,
            query.schedule_version_precondition,
          ) ||
          !sameVersionReference(comparison.compared_version, comparedVersion)
        ) {
          throw new ContractViolation(
            "comparison.version_preconditions",
            "comparison payload differs from the requested Version pair",
          );
        }
        return response;
      });
    },
  };
}

function commandPath(command: WorkspaceCommandDocument): string {
  const source = pathSegment(command.source_id);
  switch (command.command_type) {
    case "MOVE_OPERATION":
    case "ASSIGN_RESOURCE":
    case "SET_LOCK":
    case "REMOVE_LOCK":
      return `/schedule-versions/${source}/commands`;
    case "SUBMIT_FOR_REVIEW":
      return `/schedule-versions/${source}/validate`;
    case "APPROVE":
      return `/schedule-versions/${source}/approve`;
    case "REJECT":
      return `/schedule-versions/${source}/reject`;
    case "PUBLISH":
      return `/schedule-versions/${source}/publish`;
    case "REQUEST_EXPORT":
      return `/schedule-versions/${source}/exports`;
    case "RETRY_EXPORT":
      return `/export-jobs/${source}/retry`;
    case "CANCEL_EXPORT":
      return `/export-jobs/${source}/cancel`;
  }
}

function workspacePath(view: WorkspaceView): string {
  const paths: Partial<Record<WorkspaceView, string>> = {
    DATA_HEALTH: "/workspace/data-health",
    IMPORT_RUNS: "/workspace/import-runs",
    PLANNING_RUNS: "/workspace/planning-runs",
  };
  const path = paths[view];
  if (path === undefined) {
    throw new WorkspaceClientError(
      "contract_error",
      `${view} requires a ScheduleVersion precondition`,
      null,
      null,
    );
  }
  return path;
}

function scheduleWorkspacePath(id: string, view: WorkspaceView): string {
  return `/schedule-versions/${pathSegment(id)}/workspace/${encodeURIComponent(view)}`;
}
