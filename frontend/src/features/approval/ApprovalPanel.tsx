import { Alert, Button, Card, Input, Space, Typography } from "antd";
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

interface ApprovalPanelProps {
  version: ScheduleVersion;
  refreshAuthority(): Promise<void>;
  onActionResult(result: WorkspaceActionResult): Promise<void> | void;
}

export function ApprovalPanel({
  version,
  refreshAuthority,
  onActionResult,
}: ApprovalPanelProps) {
  const { runtime } = useAppServices();
  const [reason, setReason] = useState("");
  const action = useHumanControlAction({
    refreshAuthority,
    onSuccess: onActionResult,
  });
  const reviewable =
    runtime.dataPlane === "SIMULATION" &&
    runtime.synthetic &&
    version.synthetic &&
    version.state === "READY_FOR_REVIEW";

  async function decide(commandType: "APPROVE" | "REJECT") {
    const command = await buildScheduleVersionCommand(
      runtime,
      version,
      commandType,
      {},
      reason,
    );
    await action.execute(command);
  }

  return (
    <Card title="Human approval decision" className="control-card">
      {version.state !== "READY_FOR_REVIEW" && (
        <Paragraph type="secondary">
          Approve and reject are mounted only for READY_FOR_REVIEW authority.
        </Paragraph>
      )}
      {reviewable &&
        !serverAllows(version, "approve") &&
        !serverAllows(version, "reject") && (
          <Alert
            type="warning"
            showIcon
            title="Server did not grant an approval capability."
          />
        )}
      <label className="control-field">
        Decision reason
        <Input.TextArea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          rows={2}
          maxLength={512}
          disabled={!reviewable || action.pending}
        />
      </label>
      <Space wrap>
        <Button
          type="primary"
          disabled={
            !reviewable ||
            !serverAllows(version, "approve") ||
            reason.trim().length < 3 ||
            action.pending
          }
          onClick={() => void decide("APPROVE")}
        >
          Approve Version
        </Button>
        <Button
          danger
          disabled={
            !reviewable ||
            !serverAllows(version, "reject") ||
            reason.trim().length < 3 ||
            action.pending
          }
          onClick={() => void decide("REJECT")}
        >
          Reject Version
        </Button>
      </Space>
      <ActionFeedback
        feedback={action.feedback}
        pending={action.pending}
        onRefresh={() => void action.refreshForRetry()}
        onRetry={() => void action.retry()}
      />
    </Card>
  );
}
