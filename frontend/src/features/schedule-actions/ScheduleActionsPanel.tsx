import { Alert, Button, Card, Input, Space, Typography } from "antd";
import { useState } from "react";

import { buildScheduleVersionCommand } from "../../api/commands";
import type {
  GanttSegment,
  ScheduleVersion,
  WorkspaceActionResult,
  WorkspaceCommandType,
} from "../../api/types";
import { useAppServices } from "../../app/context";
import {
  serverAllows,
  useHumanControlAction,
  type HumanControlFeedback,
} from "./useHumanControlAction";

const { Paragraph, Text } = Typography;

interface ActionFeedbackProps {
  feedback: HumanControlFeedback;
  pending: boolean;
  onRefresh(): void;
  onRetry(): void;
}

export function ActionFeedback({
  feedback,
  pending,
  onRefresh,
  onRetry,
}: ActionFeedbackProps) {
  if (feedback.phase === "idle") return null;
  if (feedback.phase === "success") {
    return (
      <Alert
        type="success"
        showIcon
        title={feedback.detail}
        description={`Correlation ${feedback.correlationId ?? "unavailable"}`}
      />
    );
  }
  if (feedback.phase === "outcome_unknown" || feedback.phase === "refreshing") {
    return (
      <Alert
        type="warning"
        showIcon
        title="Server outcome not assumed"
        description={feedback.detail}
        action={
          <Space wrap>
            <Button onClick={onRefresh} disabled={pending || feedback.retryReady}>
              Refresh authority
            </Button>
            <Button
              type="primary"
              onClick={onRetry}
              disabled={pending || !feedback.retryReady}
            >
              Retry same request
            </Button>
          </Space>
        }
      />
    );
  }
  return (
    <Alert
      type={feedback.phase === "error" ? "error" : "info"}
      showIcon
      title={feedback.detail}
      description={`Correlation ${feedback.correlationId ?? "pending"}`}
    />
  );
}

interface ScheduleActionsPanelProps {
  version: ScheduleVersion;
  refreshAuthority(): Promise<void>;
  onActionResult(result: WorkspaceActionResult): Promise<void> | void;
}

export function ScheduleActionsPanel({
  version,
  refreshAuthority,
  onActionResult,
}: ScheduleActionsPanelProps) {
  const { runtime } = useAppServices();
  const [reason, setReason] = useState("");
  const action = useHumanControlAction({
    refreshAuthority,
    onSuccess: onActionResult,
  });
  const simulationControl =
    runtime.dataPlane === "SIMULATION" &&
    runtime.environment !== "PRODUCTION" &&
    runtime.synthetic &&
    version.synthetic;
  const canSubmit =
    simulationControl &&
    version.state === "DRAFT" &&
    serverAllows(version, "edit");

  async function submit() {
    const command = await buildScheduleVersionCommand(
      runtime,
      version,
      "SUBMIT_FOR_REVIEW",
      {},
      reason,
    );
    await action.execute(command);
  }

  return (
    <Card title="Validate and submit Draft" className="control-card">
      {!simulationControl && (
        <Alert
          type="warning"
          showIcon
          title="Human controls are unavailable outside isolated Simulation tests."
        />
      )}
      {version.state !== "DRAFT" && (
        <Paragraph type="secondary">
          Submission is available only for a server-authorized DRAFT.
        </Paragraph>
      )}
      {version.state === "DRAFT" && !serverAllows(version, "edit") && (
        <Alert type="warning" showIcon title="Server did not grant edit capability." />
      )}
      <label className="control-field">
        Submission reason
        <Input.TextArea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          rows={2}
          maxLength={512}
          disabled={!canSubmit || action.pending}
        />
      </label>
      <Space wrap>
        <Button
          type="primary"
          onClick={() => void submit()}
          disabled={!canSubmit || reason.trim().length < 3 || action.pending}
          loading={action.pending}
        >
          Submit for review
        </Button>
        <Text type="secondary">A second fresh formal validation runs on the server.</Text>
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

interface GanttEditControlsProps extends ScheduleActionsPanelProps {
  segment: GanttSegment;
  proposedOffsetSeconds?: number;
}

export function GanttEditControls({
  version,
  segment,
  proposedOffsetSeconds = 0,
  refreshAuthority,
  onActionResult,
}: GanttEditControlsProps) {
  const { runtime } = useAppServices();
  const shiftedStart = new Date(
    Date.parse(segment.start_at_utc) + proposedOffsetSeconds * 1000,
  )
    .toISOString()
    .replace(".000Z", "Z");
  const shiftedEnd = new Date(
    Date.parse(segment.end_at_utc) + proposedOffsetSeconds * 1000,
  )
    .toISOString()
    .replace(".000Z", "Z");
  const [resourceId, setResourceId] = useState(segment.resource_id);
  const [startAtUtc, setStartAtUtc] = useState(shiftedStart);
  const [endAtUtc, setEndAtUtc] = useState(shiftedEnd);
  const [reason, setReason] = useState("");
  const action = useHumanControlAction({
    refreshAuthority,
    onSuccess: onActionResult,
  });

  const simulationControl =
    runtime.dataPlane === "SIMULATION" && runtime.synthetic && version.synthetic;
  const editable =
    simulationControl && version.state === "DRAFT" && serverAllows(version, "edit");
  const lockable =
    simulationControl && version.state === "DRAFT" && serverAllows(version, "lock");

  async function execute(commandType: WorkspaceCommandType) {
    let payload: Record<string, import("../../api/types").JsonValue>;
    if (commandType === "MOVE_OPERATION") {
      payload = {
        operation_id: segment.operation_id,
        resource_id: resourceId.trim(),
        start_at_utc: startAtUtc.trim(),
        end_at_utc: endAtUtc.trim(),
      };
    } else if (commandType === "ASSIGN_RESOURCE") {
      payload = {
        operation_id: segment.operation_id,
        resource_id: resourceId.trim(),
      };
    } else {
      payload = {
        lock: {
          lock_id: `lock-ui-${globalThis.crypto.randomUUID()}`,
          operation_id: segment.operation_id,
          lock_type: "HARD",
          resource_id: resourceId.trim(),
          start_at_utc: startAtUtc.trim(),
          end_at_utc: endAtUtc.trim(),
        },
      };
    }
    const command = await buildScheduleVersionCommand(
      runtime,
      version,
      commandType as "MOVE_OPERATION" | "ASSIGN_RESOURCE" | "SET_LOCK",
      payload,
      reason,
    );
    await action.execute(command);
  }

  if (version.state === "PUBLISHED" || version.state === "SUPERSEDED") {
    return (
      <Alert
        type="info"
        showIcon
        title="Published history is immutable"
        description="No edit or lock command is mounted for this Version."
      />
    );
  }

  return (
    <Card title={`Human control · ${segment.operation_id}`} className="control-card">
      {proposedOffsetSeconds !== 0 && (
        <Alert
          type="info"
          showIcon
          title={`Drag proposed a ${proposedOffsetSeconds / 60}-minute shift`}
          description="Nothing changes until a server command succeeds and the new Version is fetched."
        />
      )}
      <div className="control-grid">
        <label className="control-field">
          Resource ID
          <Input value={resourceId} onChange={(event) => setResourceId(event.target.value)} />
        </label>
        <label className="control-field">
          Start UTC
          <Input value={startAtUtc} onChange={(event) => setStartAtUtc(event.target.value)} />
        </label>
        <label className="control-field">
          End UTC
          <Input value={endAtUtc} onChange={(event) => setEndAtUtc(event.target.value)} />
        </label>
        <label className="control-field">
          Change reason
          <Input.TextArea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            rows={2}
            maxLength={512}
          />
        </label>
      </div>
      <Space wrap>
        <Button
          type="primary"
          disabled={!editable || reason.trim().length < 3 || action.pending}
          onClick={() => void execute("MOVE_OPERATION")}
        >
          Move selected operation
        </Button>
        <Button
          disabled={!editable || reason.trim().length < 3 || action.pending}
          onClick={() => void execute("ASSIGN_RESOURCE")}
        >
          Assign resource only
        </Button>
        <Button
          disabled={!lockable || reason.trim().length < 3 || action.pending}
          onClick={() => void execute("SET_LOCK")}
        >
          Set hard lock
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
