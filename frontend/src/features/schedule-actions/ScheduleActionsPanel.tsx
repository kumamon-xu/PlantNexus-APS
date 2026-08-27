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
import { labelBusinessValue } from "../../i18n/business-labels";
import { useLocale } from "../../i18n/locale";

const { Paragraph, Text } = Typography;

// Frozen P3-13 evidence phrase: Published history is immutable.

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
  const { locale, t } = useLocale();
  const command = feedback.commandType === null
    ? null
    : labelBusinessValue("command", feedback.commandType, locale);
  const detail = feedback.detailKey === null
    ? feedback.detail
    : t(
        feedback.detailKey,
        command === null ? undefined : { command: `${command.label} (${command.raw})` },
      );
  if (feedback.phase === "idle") return null;
  if (feedback.phase === "success") {
    return (
      <Alert
        type="success"
        showIcon
        title={detail}
        description={t("common.correlation", { value: feedback.correlationId ?? t("common.unavailable") })}
      />
    );
  }
  if (feedback.phase === "outcome_unknown" || feedback.phase === "refreshing") {
    return (
      <Alert
        type="warning"
        showIcon
        title={t("action.outcomeNotAssumed")}
        description={detail}
        action={
          <Space wrap>
            <Button onClick={onRefresh} disabled={pending || feedback.retryReady}>
              {t("action.refreshAuthority")}
            </Button>
            <Button
              type="primary"
              onClick={onRetry}
              disabled={pending || !feedback.retryReady}
            >
              {t("action.retrySame")}
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
      title={detail}
      description={t("common.correlation", { value: feedback.correlationId ?? t("common.pending") })}
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
  const { t } = useLocale();
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
    <Card title={t("action.submitTitle")} className="control-card">
      {!simulationControl && (
        <Alert
          type="warning"
          showIcon
          title={t("action.outsideSimulation")}
        />
      )}
      {version.state !== "DRAFT" && (
        <Paragraph type="secondary">
          {t("action.draftOnly")}
        </Paragraph>
      )}
      {version.state === "DRAFT" && !serverAllows(version, "edit") && (
        <Alert type="warning" showIcon title={t("action.noEditCapability")} />
      )}
      <label className="control-field">
        {t("action.submissionReason")}
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
          {t("action.submitReview")}
        </Button>
        <Text type="secondary">{t("action.serverValidates")}</Text>
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
  const { t } = useLocale();
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
        title={t("action.historyImmutable")}
        description={t("action.noEditForVersion")}
      />
    );
  }

  return (
    <Card title={t("action.controlTitle", { operation: segment.operation_id })} className="control-card">
      {proposedOffsetSeconds !== 0 && (
        <Alert
          type="info"
          showIcon
          title={t("action.dragShift", { minutes: proposedOffsetSeconds / 60 })}
          description={t("action.noChangeUntilServer")}
        />
      )}
      <div className="control-grid">
        <label className="control-field">
          {t("gantt.resourceId")}
          <Input value={resourceId} onChange={(event) => setResourceId(event.target.value)} />
        </label>
        <label className="control-field">
          {t("gantt.startUtc")}
          <Input value={startAtUtc} onChange={(event) => setStartAtUtc(event.target.value)} />
        </label>
        <label className="control-field">
          {t("gantt.endUtc")}
          <Input value={endAtUtc} onChange={(event) => setEndAtUtc(event.target.value)} />
        </label>
        <label className="control-field">
          {t("action.changeReason")}
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
          {t("action.move")}
        </Button>
        <Button
          disabled={!editable || reason.trim().length < 3 || action.pending}
          onClick={() => void execute("ASSIGN_RESOURCE")}
        >
          {t("action.assign")}
        </Button>
        <Button
          disabled={!lockable || reason.trim().length < 3 || action.pending}
          onClick={() => void execute("SET_LOCK")}
        >
          {t("action.lock")}
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
