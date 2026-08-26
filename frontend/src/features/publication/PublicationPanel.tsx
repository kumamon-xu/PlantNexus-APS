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
  const { runtime } = useAppServices();
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
    const command = await buildScheduleVersionCommand(
      runtime,
      version,
      "PUBLISH",
      { previous_current_version: null },
      reason,
    );
    await action.execute(command);
    setDialogOpen(false);
  }

  return (
    <Card title="Internal Simulation publication" className="control-card">
      <Alert
        type="info"
        showIcon
        title="This control cannot publish to MES, ERP, or Production."
      />
      {version.state !== "APPROVED" && (
        <Paragraph type="secondary">
          Publication is available only for an APPROVED Version.
        </Paragraph>
      )}
      <Button
        type="primary"
        disabled={!publishable || action.pending}
        onClick={() => setDialogOpen(true)}
      >
        Review internal publication
      </Button>
      <Modal
        title="Confirm SIMULATION_INTERNAL publication"
        open={dialogOpen}
        onCancel={() => setDialogOpen(false)}
        onOk={() => void publish()}
        okText="Publish internally"
        confirmLoading={action.pending}
        okButtonProps={{
          disabled:
            !confirmed || reason.trim().length < 3 || action.pending,
        }}
      >
        <Alert
          type="warning"
          showIcon
          title={`Publish Version ${version.schedule_version_id}`}
          description="This may supersede the prior current Simulation Version. It does not publish to Production or MES."
        />
        <label className="control-field">
          Publication reason
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
          I understand this creates only a SIMULATION_INTERNAL publication.
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
