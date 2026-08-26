import { Alert, Button, Card, Descriptions, Input, Space, Typography } from "antd";
import { useState } from "react";

import { WorkspaceClientError } from "../../api/client";
import {
  buildExportJobCommand,
  buildScheduleVersionCommand,
} from "../../api/commands";
import type {
  ExportJob,
  ScheduleVersion,
  WorkspaceActionResult,
} from "../../api/types";
import { useAppServices } from "../../app/context";
import { ActionFeedback } from "../schedule-actions/ScheduleActionsPanel";
import {
  serverAllows,
  useHumanControlAction,
} from "../schedule-actions/useHumanControlAction";

const { Paragraph, Text } = Typography;

interface ExportPanelProps {
  version: ScheduleVersion;
  refreshAuthority(): Promise<void>;
}

function visibleError(error: unknown): string {
  if (error instanceof WorkspaceClientError) {
    return `${error.message} (correlation ${error.correlationId ?? "unavailable"})`;
  }
  return "Export authority failed its published contract.";
}

export function ExportPanel({ version, refreshAuthority }: ExportPanelProps) {
  const { client, runtime } = useAppServices();
  const [reason, setReason] = useState("");
  const [job, setJob] = useState<ExportJob | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [jobPending, setJobPending] = useState(false);
  const [downloadPending, setDownloadPending] = useState(false);
  const [downloadEvidence, setDownloadEvidence] = useState<string | null>(null);

  async function acceptActionResult(result: WorkspaceActionResult) {
    if (result.exportJob === null) {
      throw new TypeError("Export command returned no authoritative ExportJob");
    }
    setJob(result.exportJob);
    setJobError(null);
    setDownloadEvidence(null);
  }

  async function refreshCurrentAuthority() {
    if (job === null) {
      await refreshAuthority();
      return;
    }
    const refreshed = await client.getExportJob(job.export_job_id);
    if (
      refreshed.export_job_id !== job.export_job_id ||
      refreshed.schedule_version.schedule_version_id !== version.schedule_version_id ||
      refreshed.data_plane !== version.data_plane
    ) {
      throw new TypeError("Refreshed ExportJob authority is not bound to this Version");
    }
    setJob(refreshed);
  }

  const action = useHumanControlAction({
    refreshAuthority: refreshCurrentAuthority,
    onSuccess: acceptActionResult,
  });
  const simulationControl =
    runtime.dataPlane === "SIMULATION" &&
    runtime.environment !== "PRODUCTION" &&
    runtime.synthetic &&
    version.synthetic;
  const canRequest =
    simulationControl &&
    version.state === "PUBLISHED" &&
    serverAllows(version, "export") &&
    job === null;
  const canRetry =
    simulationControl && job?.state === "EXPORT_FAILED" && !action.pending;
  const canDownload =
    simulationControl &&
    job?.state === "EXPORTED" &&
    job.artifact_manifest !== null;

  async function requestExport() {
    const command = await buildScheduleVersionCommand(
      runtime,
      version,
      "REQUEST_EXPORT",
      { package_profile: "p3-standard-export.v1" },
      reason,
    );
    await action.execute(command);
  }

  async function retryExport() {
    if (job === null) return;
    const command = await buildExportJobCommand(
      runtime,
      job,
      "RETRY_EXPORT",
      { expected_attempt: job.attempt },
      reason,
    );
    await action.execute(command);
  }

  async function refreshJob() {
    if (job === null || jobPending) return;
    setJobPending(true);
    setJobError(null);
    try {
      await refreshCurrentAuthority();
    } catch (error) {
      setJobError(visibleError(error));
    } finally {
      setJobPending(false);
    }
  }

  async function download() {
    if (job === null || job.artifact_manifest === null || downloadPending) return;
    setDownloadPending(true);
    setJobError(null);
    setDownloadEvidence(null);
    try {
      const downloaded = await client.downloadExportPackage(job.export_job_id);
      if (
        downloaded.packageId !== job.artifact_manifest.package_id ||
        downloaded.manifestFingerprint !==
          job.artifact_manifest.manifest_fingerprint
      ) {
        throw new TypeError(
          "Downloaded package evidence differs from the authoritative ExportJob",
        );
      }
      const objectUrl = URL.createObjectURL(downloaded.blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = downloaded.filename;
      anchor.rel = "noopener";
      anchor.click();
      globalThis.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
      setDownloadEvidence(
        `Verified ${downloaded.packageId}; archive ${downloaded.archiveFingerprint}; correlation ${downloaded.correlationId}`,
      );
    } catch (error) {
      setJobError(visibleError(error));
    } finally {
      setDownloadPending(false);
    }
  }

  return (
    <Card title="Internal Simulation export" className="control-card">
      <Alert
        type="info"
        showIcon
        title="Export is separate from publication."
        description="Only a verified EXPORTED package can be downloaded; no MES or external storage target is available."
      />
      {version.state !== "PUBLISHED" && (
        <Paragraph type="secondary">
          Export creation is available only from a PUBLISHED Version.
        </Paragraph>
      )}
      <label className="control-field">
        Export or retry reason
        <Input.TextArea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          rows={2}
          maxLength={512}
          disabled={!simulationControl || action.pending}
        />
      </label>
      <Space wrap>
        <Button
          type="primary"
          disabled={!canRequest || reason.trim().length < 3 || action.pending}
          loading={action.pending && job === null}
          onClick={() => void requestExport()}
        >
          Request export
        </Button>
        {job !== null && (
          <Button loading={jobPending} onClick={() => void refreshJob()}>
            Refresh export job
          </Button>
        )}
        {job?.state === "EXPORT_FAILED" && (
          <Button
            danger
            disabled={!canRetry || reason.trim().length < 3}
            onClick={() => void retryExport()}
          >
            Retry failed export
          </Button>
        )}
        {job?.state === "EXPORTED" && (
          <Button
            type="primary"
            disabled={!canDownload || downloadPending}
            loading={downloadPending}
            onClick={() => void download()}
          >
            Download verified package
          </Button>
        )}
      </Space>
      <ActionFeedback
        feedback={action.feedback}
        pending={action.pending}
        onRefresh={() => void action.refreshForRetry()}
        onRetry={() => void action.retry()}
      />
      {jobError !== null && <Alert type="error" showIcon title={jobError} />}
      {downloadEvidence !== null && (
        <Alert type="success" showIcon title="Verified package downloaded" description={downloadEvidence} />
      )}
      {job !== null && (
        <Descriptions bordered size="small" column={1} title="Authoritative ExportJob">
          <Descriptions.Item label="Job ID">{job.export_job_id}</Descriptions.Item>
          <Descriptions.Item label="State">
            <Text strong>{job.state}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="Attempt">{job.attempt}</Descriptions.Item>
          <Descriptions.Item label="Latest audit event">
            {job.latest_audit_event_id}
          </Descriptions.Item>
          <Descriptions.Item label="Package">
            {job.artifact_manifest?.package_id ?? "Not formed"}
          </Descriptions.Item>
        </Descriptions>
      )}
    </Card>
  );
}
