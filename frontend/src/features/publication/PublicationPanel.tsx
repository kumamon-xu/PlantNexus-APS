import { Alert, Button, Card, Checkbox, Input, Modal, Typography } from "antd";
import { useState } from "react";

import { buildScheduleVersionCommand } from "../../api/commands";
import type { ScheduleVersion, WorkspaceActionResult } from "../../api/types";
import { useAppServices } from "../../app/context";
import { ActionFeedback } from "../schedule-actions/ScheduleActionsPanel";
import {
  serverAllows,
  useHumanControlAction,
} from "../schedule-actions/useHumanControlAction";
import { useLocale } from "../../i18n/locale";

const { Paragraph } = Typography;

interface PublicationPanelProps {
  version: ScheduleVersion;
  refreshAuthority(): Promise<void>;
  onActionResult(result: WorkspaceActionResult): Promise<void> | void;
}

export function PublicationPanel({
  version,
  refreshAuthority,
  onActionResult,
}: PublicationPanelProps) {
  const { runtime, client } = useAppServices();
  const { locale, t } = useLocale();
  const [previousId, setPreviousId] = useState("");
  const [preconditionError, setPreconditionError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const action = useHumanControlAction({
    refreshAuthority,
    onSuccess: onActionResult,
  });
  const publishable =
    runtime.dataPlane === "SIMULATION" &&
    runtime.environment !== "PRODUCTION" &&
    runtime.synthetic &&
    version.synthetic &&
    version.state === "APPROVED" &&
    serverAllows(version, "publish");

  async function publish() {
    setPreconditionError(null);
    let previous = null;
    try {
      if (previousId.trim()) {
        const current = await client.getScheduleVersion(previousId.trim());
        if (current.state !== "PUBLISHED") throw new Error("Previous current version must be PUBLISHED");
        previous = { schedule_version_id: current.schedule_version_id, state: current.state, content_fingerprint: current.content_fingerprint };
      }
    } catch (error) {
      setPreconditionError(error instanceof Error ? error.message : "CONTRACT_REJECTED");
      return;
    }
    const command = await buildScheduleVersionCommand(
      runtime,
      version,
      "PUBLISH",
      { previous_current_version: previous },
      reason,
    );
    await action.execute(command);
    setDialogOpen(false);
  }

  return (
    <Card title={t("publication.title")} className="control-card">
      <Alert
        type="info"
        showIcon
        title={t("publication.boundary")}
      />
      {version.state !== "APPROVED" && (
        <Paragraph type="secondary">
          {t("publication.approvedOnly")}
        </Paragraph>
      )}
      <Button
        type="primary"
        disabled={!publishable || action.pending}
        onClick={() => setDialogOpen(true)}
      >
        {t("publication.review")}
      </Button>
      <Modal
        title={t("publication.confirmTitle")}
        open={dialogOpen}
        onCancel={() => setDialogOpen(false)}
        onOk={() => void publish()}
        okText={t("publication.publish")}
        confirmLoading={action.pending}
        okButtonProps={{
          disabled:
            !confirmed || reason.trim().length < 3 || action.pending,
        }}
      >
        <Alert
          type="warning"
          showIcon
          title={t("publication.version", { version: version.schedule_version_id })}
          description={t("publication.description")}
        />
        <label className="control-field">
          {locale === "zh-CN" ? "当前已发布版本 ID（首次发布留空）" : "Current published version ID (empty for first publication)"}
          <Input aria-label="Current published version ID" value={previousId} disabled={action.pending} onChange={(event) => { setPreviousId(event.target.value); setConfirmed(false); }} />
        </label>
        {preconditionError && <Alert type="error" title={preconditionError} />}
        <label className="control-field">
          {t("publication.reason")}
          <Input.TextArea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            rows={2}
            maxLength={512}
            disabled={action.pending}
          />
        </label>
        <Checkbox
          checked={confirmed}
          onChange={(event) => setConfirmed(event.target.checked)}
          disabled={action.pending}
        >
          {t("publication.checkbox")}
        </Checkbox>
      </Modal>
      <ActionFeedback
        feedback={action.feedback}
        pending={action.pending}
        onRefresh={() => void action.refreshForRetry()}
        onRetry={() => void action.retry()}
      />
    </Card>
  );
}
