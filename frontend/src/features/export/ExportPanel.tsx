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
import { labelBusinessValue } from "../../i18n/business-labels";
import { translate, useLocale } from "../../i18n/locale";
import type { AppLocale } from "../../i18n/types";

const { Paragraph, Text } = Typography;

interface ExportPanelProps {
  version: ScheduleVersion;
  refreshAuthority(): Promise<void>;
}

function visibleError(error: unknown, locale: AppLocale): string {
  if (error instanceof WorkspaceClientError) {
    return `${error.message} (${translate(locale, "common.correlation", { value: error.correlationId ?? translate(locale, "common.unavailable") })})`;
  }
  return translate(locale, "export.authorityFailed");
}

export function ExportPanel({ version, refreshAuthority }: ExportPanelProps) {
  const { client, runtime } = useAppServices();
  const { locale, t } = useLocale();
  const [reason, setReason] = useState("");
  const [job, setJob] = useState<ExportJob | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [jobPending, setJobPending] = useState(false);
  const [downloadPending, setDownloadPending] = useState(false);
  const [downloadEvidence, setDownloadEvidence] = useState<string | null>(null);

  async function acceptActionResult(result: WorkspaceActionResult) {
    if (result.exportJob === null) {
      throw new TypeError(t("export.commandNoJob"));
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
      throw new TypeError(t("export.refreshMismatch"));
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
      setJobError(visibleError(error, locale));
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
          t("export.downloadMismatch"),
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
        t("export.verifiedDetail", { package: downloaded.packageId, archive: downloaded.archiveFingerprint, correlation: downloaded.correlationId }),
      );
    } catch (error) {
      setJobError(visibleError(error, locale));
    } finally {
      setDownloadPending(false);
    }
  }

  return (
    <Card title={t("export.title")} className="control-card">
      <Alert
        type="info"
        showIcon
        title={t("export.separate")}
        description={t("export.boundary")}
      />
      {version.state !== "PUBLISHED" && (
        <Paragraph type="secondary">
          {t("export.publishedOnly")}
        </Paragraph>
      )}
      <label className="control-field">
        {t("export.reason")}
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
          {t("export.request")}
        </Button>
        {job !== null && (
          <Button loading={jobPending} onClick={() => void refreshJob()}>
            {t("export.refresh")}
          </Button>
        )}
        {job?.state === "EXPORT_FAILED" && (
          <Button
            danger
            disabled={!canRetry || reason.trim().length < 3}
            onClick={() => void retryExport()}
          >
            {t("export.retry")}
          </Button>
        )}
        {job?.state === "EXPORTED" && (
          <Button
            type="primary"
            disabled={!canDownload || downloadPending}
            loading={downloadPending}
            onClick={() => void download()}
          >
            {t("export.download")}
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
        <Alert type="success" showIcon title={t("export.verified")} description={downloadEvidence} />
      )}
      {job !== null && (
        <Descriptions bordered size="small" column={1} title={t("export.jobTitle")}>
          <Descriptions.Item label={t("export.jobId")}>{job.export_job_id}</Descriptions.Item>
          <Descriptions.Item label={t("version.state")}>
            <Text strong>{labelBusinessValue("exportJobState", job.state, locale).label}</Text>{" "}<Text code>{job.state}</Text>
          </Descriptions.Item>
          <Descriptions.Item label={t("export.attempt")}>{job.attempt}</Descriptions.Item>
          <Descriptions.Item label={t("export.latestAudit")}>
            {job.latest_audit_event_id}
          </Descriptions.Item>
          <Descriptions.Item label={t("export.package")}>
            {job.artifact_manifest?.package_id ?? t("export.notFormed")}
          </Descriptions.Item>
        </Descriptions>
      )}
    </Card>
  );
}
