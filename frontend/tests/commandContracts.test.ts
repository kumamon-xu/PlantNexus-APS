import {
  buildExportJobCommand,
  buildScheduleVersionCommand,
  createCommandIdentity,
} from "../src/api/commands";
import { workspaceCommandFingerprint } from "../src/api/canonical";
import type { RuntimeConfig } from "../src/api/runtime";
import type { ExportJob } from "../src/api/types";
import {
  syntheticDraftVersion,
  syntheticProvenance,
  testScheduleVersion,
} from "./fixtures";

const simulationRuntime: RuntimeConfig = {
  apiBaseUrl: "/api/v1",
  dataPlane: "SIMULATION",
  environment: "TEST",
  synthetic: true,
};

function failedJob(): ExportJob {
  return {
    export_job_version: "export-job.v2",
    schema_set_version: "2.7.0",
    canonicalization_version: "canonical-json.v1",
    export_job_id: `export-job-${"1".repeat(64)}`,
    state: "EXPORT_FAILED",
    schedule_version: {
      schedule_version_id: syntheticDraftVersion.schedule_version_id,
      state: "PUBLISHED",
      content_fingerprint: syntheticDraftVersion.content_fingerprint,
    },
    data_plane: "SIMULATION",
    environment: "TEST",
    synthetic: true,
    synthetic_provenance: syntheticProvenance,
    target: "SIMULATION_INTERNAL",
    package_profile: "p3-standard-export.v1",
    attempt: 2,
    artifact_manifest: null,
    latest_audit_event_id: "audit-export-failed-001",
    job_fingerprint: `sha256:${"9".repeat(64)}`,
  };
}

describe("workspace-command.v1 browser producer", () => {
  it("derives capability, target, CAS, scope and canonical fingerprint", async () => {
    const identity = createCommandIdentity();
    const command = await buildScheduleVersionCommand(
      simulationRuntime,
      syntheticDraftVersion,
      "MOVE_OPERATION",
      {
        operation_id: "operation-test-1",
        resource_id: "resource-test-2",
        start_at_utc: "2026-08-25T01:30:00Z",
        end_at_utc: "2026-08-25T02:30:00Z",
      },
      "Move for synthetic dispatch review",
      identity,
    );
    expect(command).toMatchObject({
      command_type: "MOVE_OPERATION",
      required_capability: "edit",
      target: "WORKSPACE_INTERNAL",
      source_id: syntheticDraftVersion.schedule_version_id,
      expected_state: "DRAFT",
      expected_content_fingerprint: syntheticDraftVersion.content_fingerprint,
      idempotency_key: identity.idempotencyKey,
      synthetic_provenance: syntheticProvenance,
    });
    expect(command.idempotency_scope).toBe(
      `SIMULATION/MOVE_OPERATION/${syntheticDraftVersion.schedule_version_id}/WORKSPACE_INTERNAL`,
    );
    expect(await workspaceCommandFingerprint(command)).toBe(
      command.request_fingerprint,
    );
  });

  it("builds retry against the exact ExportJob attempt", async () => {
    const job = failedJob();
    const command = await buildExportJobCommand(
      simulationRuntime,
      job,
      "RETRY_EXPORT",
      { expected_attempt: job.attempt },
      "Retry after visible synthetic failure",
    );
    expect(command).toMatchObject({
      command_type: "RETRY_EXPORT",
      required_capability: "export",
      expected_state: "EXPORT_FAILED",
      target: "SIMULATION_INTERNAL",
      payload: { expected_attempt: 2 },
    });
  });

  it("fails closed for Production, missing provenance and credential-like reasons", async () => {
    await expect(
      buildScheduleVersionCommand(
        {
          apiBaseUrl: "/api/v1",
          dataPlane: "PRODUCTION",
          environment: "PRODUCTION",
          synthetic: false,
        },
        testScheduleVersion,
        "SUBMIT_FOR_REVIEW",
        {},
        "Submit reviewed draft",
      ),
    ).rejects.toThrow(/restricted to the isolated synthetic Simulation/u);
    await expect(
      buildScheduleVersionCommand(
        simulationRuntime,
        { ...syntheticDraftVersion, synthetic_provenance: null },
        "SUBMIT_FOR_REVIEW",
        {},
        "Submit reviewed draft",
      ),
    ).rejects.toThrow(/restricted/u);
    await expect(
      buildScheduleVersionCommand(
        simulationRuntime,
        syntheticDraftVersion,
        "SUBMIT_FOR_REVIEW",
        {},
        "token = should-not-enter-audit",
      ),
    ).rejects.toThrow(/credential-safe/u);
  });
});
