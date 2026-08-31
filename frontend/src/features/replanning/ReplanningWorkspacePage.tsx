import {
  Alert,
  Button,
  Card,
  Checkbox,
  Descriptions,
  Input,
  Space,
  Tag,
  Typography,
} from "antd";
import { useState, type FormEvent, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { WorkspaceStatePanel } from "../../components/WorkspaceStatePanel";
import { useAppServices } from "../../app/context";
import {
  labelBusinessValue,
  type BusinessLabelNamespace,
} from "../../i18n/business-labels";
import { formatSeconds, formatUtc } from "../../i18n/formatters";
import type { TranslationKey } from "../../i18n/dictionaries/en-US";
import { useLocale } from "../../i18n/locale";
import { ReplanningClientError } from "./client";
import type {
  ChangeReportOperation,
  ReplanAttemptAction,
  ReplanningWorkspaceIdentity,
} from "./types";
import { useReplanningWorkspace } from "./useReplanningWorkspace";

const { Paragraph, Text, Title } = Typography;

interface IdentityDraft {
  planning_scope_id: string;
  authority_id: string;
  stream_id: string;
  stream_version: string;
  from_position: string;
  through_position: string;
  request_id: string;
  request_fingerprint: string;
  attempt_id: string;
}

const identityFields = [
  "planning_scope_id",
  "authority_id",
  "stream_id",
  "stream_version",
  "from_position",
  "through_position",
  "request_id",
  "request_fingerprint",
  "attempt_id",
] as const;

const identityFieldLabels: Record<(typeof identityFields)[number], TranslationKey> = {
  planning_scope_id: "replanning.identity.planning_scope_id",
  authority_id: "replanning.identity.authority_id",
  stream_id: "replanning.identity.stream_id",
  stream_version: "replanning.identity.stream_version",
  from_position: "replanning.identity.from_position",
  through_position: "replanning.identity.through_position",
  request_id: "replanning.identity.request_id",
  request_fingerprint: "replanning.identity.request_fingerprint",
  attempt_id: "replanning.identity.attempt_id",
};

const feedbackLabels: Record<
  Exclude<ReturnType<typeof useReplanningWorkspace>["feedback"]["phase"], "idle">,
  TranslationKey
> = {
  submitting: "replanning.feedback.submitting",
  confirmed: "replanning.feedback.confirmed",
  outcome_unknown: "replanning.feedback.outcome_unknown",
  refreshing: "replanning.feedback.refreshing",
  retry_ready: "replanning.feedback.retry_ready",
  resolved_by_refresh: "replanning.feedback.resolved_by_refresh",
  failed: "replanning.feedback.failed",
};

function readDraft(parameters: URLSearchParams): IdentityDraft {
  return Object.fromEntries(
    identityFields.map((field) => [field, parameters.get(field) ?? ""]),
  ) as unknown as IdentityDraft;
}

function parseIdentity(draft: IdentityDraft): ReplanningWorkspaceIdentity | null {
  if (identityFields.some((field) => draft[field].length === 0)) return null;
  const fromPosition = Number(draft.from_position);
  const throughPosition = Number(draft.through_position);
  if (
    !Number.isInteger(fromPosition) ||
    !Number.isInteger(throughPosition) ||
    fromPosition < 1 ||
    throughPosition < fromPosition
  ) {
    return null;
  }
  return {
    planningScopeId: draft.planning_scope_id,
    authorityId: draft.authority_id,
    streamId: draft.stream_id,
    streamVersion: draft.stream_version,
    fromPosition,
    throughPosition,
    requestId: draft.request_id,
    requestFingerprint: draft.request_fingerprint,
    attemptId: draft.attempt_id,
  };
}

function RawValue({ children }: { children: ReactNode }) {
  return <span className="localized-raw">{children}</span>;
}

function MachineValue({
  namespace,
  raw,
}: {
  namespace: BusinessLabelNamespace;
  raw: string;
}) {
  const { locale } = useLocale();
  const value = labelBusinessValue(namespace, raw, locale);
  return (
    <span>
      {value.label}
      <RawValue>{raw}</RawValue>
    </span>
  );
}

function RawUtc({ value }: { value: string }) {
  const { locale } = useLocale();
  const formatted = formatUtc(value, locale);
  return (
    <span>
      {formatted.display}
      <RawValue>{formatted.raw}</RawValue>
    </span>
  );
}

function RawSeconds({ value }: { value: number }) {
  const { locale } = useLocale();
  const formatted = formatSeconds(value, locale);
  return (
    <span>
      {formatted.display}
      <RawValue>{formatted.raw}</RawValue>
    </span>
  );
}

function assignmentSummary(value: ChangeReportOperation["base_assignment"]): string {
  if (value === null) return "—";
  const resource = String(value.resource_id ?? "?");
  const start = String(value.start_at_utc ?? "?");
  const end = String(value.end_at_utc ?? "?");
  return `${resource} · ${start} → ${end}`;
}

export function ReplanningWorkspacePage() {
  const [parameters, setParameters] = useSearchParams();
  const [draft, setDraft] = useState<IdentityDraft>(() => readDraft(parameters));
  const [identity, setIdentity] = useState<ReplanningWorkspaceIdentity | null>(() =>
    parseIdentity(readDraft(parameters)),
  );
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const { runtime } = useAppServices();
  const { t } = useLocale();
  const replanning = useReplanningWorkspace(identity);

  const submitIdentity = (event: FormEvent) => {
    event.preventDefault();
    const parsed = parseIdentity(draft);
    if (parsed === null) {
      setIdentity(null);
      return;
    }
    setParameters(Object.entries(draft));
    setIdentity(parsed);
  };

  const execute = (action: ReplanAttemptAction) => {
    void replanning.execute(action, reason);
  };

  const data = replanning.query.data;
  const attempt = data?.request.attempt;
  const feedback = replanning.feedback;
  const actionDisabled =
    feedback.phase === "submitting" ||
    feedback.phase === "refreshing" ||
    !confirmed ||
    reason.trim().length === 0;

  return (
    <main className="workspace-page replanning-page">
      <Title level={2}>{t("replanning.title")}</Title>
      <Paragraph>{t("replanning.description")}</Paragraph>
      <Alert
        showIcon
        type="warning"
        title={t("replanning.simulationBoundaryTitle")}
        description={t("replanning.simulationBoundaryDescription")}
      />

      <Card title={t("replanning.identityTitle")} className="replanning-section">
        <Paragraph>{t("replanning.identityDescription")}</Paragraph>
        <form className="replanning-identity-grid" onSubmit={submitIdentity}>
          {identityFields.map((field) => (
            <label key={field}>
              <span>{t(identityFieldLabels[field])}</span>
              <Input
                aria-label={t(identityFieldLabels[field])}
                value={draft[field]}
                autoComplete="off"
                spellCheck={false}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, [field]: event.target.value }))
                }
              />
            </label>
          ))}
          <Button type="primary" htmlType="submit">
            {t("replanning.load")}
          </Button>
        </form>
      </Card>

      {runtime.dataPlane !== "SIMULATION" || runtime.environment === "PRODUCTION" ? (
        <div className="replanning-section">
          <WorkspaceStatePanel
            state="authorization_denied"
            detail={t("replanning.productionDenied")}
          />
        </div>
      ) : !replanning.configured ? (
        <div className="replanning-section">
          <WorkspaceStatePanel
            state="contract_error"
            detail={t("replanning.clientUnavailable")}
          />
        </div>
      ) : identity === null ? (
        <Alert
          className="replanning-section"
          showIcon
          type="info"
          title={t("replanning.identityRequired")}
          description={t("replanning.identityRequiredDescription")}
        />
      ) : replanning.query.isPending ? (
        <div className="replanning-section">
          <WorkspaceStatePanel state="loading" />
        </div>
      ) : replanning.query.error !== null ? (
        <div className="replanning-section">
          <WorkspaceStatePanel
            state={
              replanning.query.error instanceof ReplanningClientError
                ? replanning.query.error.kind
                : "contract_error"
            }
            detail={
              replanning.query.error instanceof Error
                ? `${replanning.query.error.message}${
                    replanning.query.error instanceof ReplanningClientError &&
                    replanning.query.error.correlationId !== null
                      ? ` · ${t("common.correlation", {
                          value: replanning.query.error.correlationId,
                        })}`
                      : ""
                  }`
                : t("replanning.contractFailed")
            }
          />
        </div>
      ) : data === undefined ? null : (
        <div className="replanning-results">
          <section aria-labelledby="replanning-events-title">
            <Title level={3} id="replanning-events-title">
              {t("replanning.eventsTitle")}
            </Title>
            <Paragraph>{t("replanning.eventsDescription")}</Paragraph>
            <ol className="event-timeline">
              {data.timeline.events.map((event) => (
                <li key={event.event_id}>
                  <Card
                    size="small"
                    title={
                      <Space wrap>
                        <Tag color="blue">#{event.source_position}</Tag>
                        <MachineValue namespace="executionEvent" raw={event.event_type} />
                      </Space>
                    }
                  >
                    <Descriptions size="small" column={{ xs: 1, md: 2 }}>
                      <Descriptions.Item label={t("replanning.eventId")}>
                        <span className="fingerprint-wrap">{event.event_id}</span>
                      </Descriptions.Item>
                      <Descriptions.Item label={t("replanning.occurredUtc")}>
                        <RawUtc value={event.occurred_at_utc} />
                      </Descriptions.Item>
                      <Descriptions.Item label={t("replanning.receivedUtc")}>
                        <RawUtc value={event.received_at_utc} />
                      </Descriptions.Item>
                      <Descriptions.Item label={t("replanning.eventFingerprint")}>
                        <span className="fingerprint-wrap">{event.event_fingerprint}</span>
                      </Descriptions.Item>
                    </Descriptions>
                    <pre className="payload-cell" aria-label={t("replanning.eventPayload")}>
                      {JSON.stringify(
                        { entity_refs: event.entity_refs, payload: event.payload },
                        null,
                        2,
                      )}
                    </pre>
                  </Card>
                </li>
              ))}
            </ol>
          </section>

          <section aria-labelledby="replanning-request-title">
            <Title level={3} id="replanning-request-title">
              {t("replanning.requestTitle")}
            </Title>
            <Descriptions bordered size="small" column={{ xs: 1, lg: 2 }}>
              <Descriptions.Item label={t("replanning.requestId")}>
                <span className="fingerprint-wrap">{data.request.request.request_id}</span>
              </Descriptions.Item>
              <Descriptions.Item label={t("replanning.requestFingerprint")}>
                <span className="fingerprint-wrap">
                  {data.request.request.request_fingerprint}
                </span>
              </Descriptions.Item>
              <Descriptions.Item label={t("replanning.triggerReason")}>
                <MachineValue
                  namespace="replanTrigger"
                  raw={data.request.request.trigger_reason}
                />
              </Descriptions.Item>
              <Descriptions.Item label={t("replanning.requestedUtc")}>
                <RawUtc value={data.request.request.requested_at_utc} />
              </Descriptions.Item>
              <Descriptions.Item label={t("replanning.baseVersion")}>
                <span className="fingerprint-wrap">
                  {String(data.request.request.base_schedule_version.schedule_version_id)}
                </span>
                <RawValue>
                  {String(data.request.request.base_schedule_version.content_fingerprint)}
                </RawValue>
              </Descriptions.Item>
              <Descriptions.Item label={t("replanning.planningRunState")}>
                <MachineValue namespace="planningRunState" raw={attempt!.state} />
              </Descriptions.Item>
              <Descriptions.Item label={t("replanning.attempt")}>
                {attempt!.attempt_number} · {attempt!.attempt_id}
              </Descriptions.Item>
              <Descriptions.Item label={t("replanning.allowedActions")}>
                {attempt!.allowed_actions.length === 0
                  ? t("common.none")
                  : attempt!.allowed_actions.map((action) => (
                      <Tag key={action}>
                        <MachineValue namespace="replanAction" raw={action} />
                      </Tag>
                    ))}
              </Descriptions.Item>
            </Descriptions>
          </section>

          <section aria-labelledby="replanning-freeze-title">
            <Title level={3} id="replanning-freeze-title">
              {t("replanning.freezeTitle")}
            </Title>
            <Alert
              type="info"
              showIcon
              title={t("replanning.halfOpen")}
              description={t("replanning.freezeServerProvided")}
            />
            <Descriptions bordered size="small" column={{ xs: 1, lg: 2 }}>
              <Descriptions.Item label={t("replanning.freezePolicy")}>
                {data.request.request.freeze_resolution.freeze_policy_id}
                <RawValue>
                  {data.request.request.freeze_resolution.freeze_policy_fingerprint}
                </RawValue>
              </Descriptions.Item>
              <Descriptions.Item label={t("replanning.freezeWindow")}>
                <RawSeconds value={data.request.request.freeze_resolution.window_seconds} />
              </Descriptions.Item>
              <Descriptions.Item label={t("replanning.effectiveFrom")}>
                <RawUtc value={data.request.request.freeze_resolution.effective_from_utc} />
              </Descriptions.Item>
              <Descriptions.Item label={t("replanning.effectiveUntil")}>
                <RawUtc value={data.request.request.freeze_resolution.effective_until_utc} />
              </Descriptions.Item>
              <Descriptions.Item label={t("replanning.effectiveLocks")} span={2}>
                {data.request.request.freeze_resolution.effective_lock_ids.length === 0
                  ? t("common.none")
                  : data.request.request.freeze_resolution.effective_lock_ids.join(", ")}
              </Descriptions.Item>
            </Descriptions>
          </section>

          <section aria-labelledby="replanning-result-title">
            <Title level={3} id="replanning-result-title">
              {t("replanning.resultTitle")}
            </Title>
            <Descriptions bordered size="small" column={{ xs: 1, lg: 2 }}>
              <Descriptions.Item label={t("replanning.planningRunState")}>
                <MachineValue
                  namespace="planningRunState"
                  raw={data.result.planning_run_state}
                />
              </Descriptions.Item>
              <Descriptions.Item label={t("replanning.failureReason")}>
                {data.result.failure_reason ?? t("common.none")}
              </Descriptions.Item>
              <Descriptions.Item label={t("replanning.newDraft")}>
                {data.result.new_schedule_version === null ? (
                  t("common.notProvided")
                ) : (
                  <span className="fingerprint-wrap">
                    {data.result.new_schedule_version.schedule_version_id}
                    <RawValue>
                      {data.result.new_schedule_version.content_fingerprint}
                    </RawValue>
                  </span>
                )}
              </Descriptions.Item>
              <Descriptions.Item label={t("replanning.resultCorrelation")}>
                {data.result.correlation_id}
              </Descriptions.Item>
            </Descriptions>
          </section>

          <section aria-labelledby="replanning-actions-title">
            <Title level={3} id="replanning-actions-title">
              {t("replanning.actionsTitle")}
            </Title>
            <Alert type="warning" showIcon title={t("replanning.actionsBoundary")} />
            <label className="control-field">
              <span>{t("replanning.actionReason")}</span>
              <Input.TextArea
                aria-label={t("replanning.actionReason")}
                value={reason}
                maxLength={512}
                onChange={(event) => setReason(event.target.value)}
              />
            </label>
            <Checkbox checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)}>
              {t("replanning.actionConfirm")}
            </Checkbox>
            <Space wrap>
              {attempt!.allowed_actions.includes("CANCEL") ? (
                <Button danger disabled={actionDisabled} onClick={() => execute("CANCEL")}>
                  {t("replanning.cancel")}
                </Button>
              ) : null}
              {attempt!.allowed_actions.includes("RETRY") ? (
                <Button type="primary" disabled={actionDisabled} onClick={() => execute("RETRY")}>
                  {t("replanning.retry")}
                </Button>
              ) : null}
              {attempt!.allowed_actions.length === 0 ? (
                <Text type="secondary">{t("replanning.noActions")}</Text>
              ) : null}
            </Space>
            {feedback.phase !== "idle" ? (
              <Alert
                className="action-feedback"
                showIcon
                type={
                  feedback.phase === "confirmed" ||
                  feedback.phase === "resolved_by_refresh" ||
                  feedback.phase === "retry_ready"
                    ? "success"
                    : feedback.phase === "failed"
                      ? "error"
                      : "warning"
                }
                title={t(feedbackLabels[feedback.phase])}
                description={
                  <Space orientation="vertical">
                    {feedback.message === null ? null : <span>{feedback.message}</span>}
                    {feedback.correlationId === null ? null : (
                      <span>{t("common.correlation", { value: feedback.correlationId })}</span>
                    )}
                    {feedback.phase === "outcome_unknown" ? (
                      <Button onClick={() => void replanning.refreshAuthority()}>
                        {t("action.refreshAuthority")}
                      </Button>
                    ) : null}
                    {feedback.phase === "retry_ready" ? (
                      <Button onClick={() => void replanning.retrySameRequest()}>
                        {t("action.retrySame")}
                      </Button>
                    ) : null}
                  </Space>
                }
              />
            ) : null}
          </section>

          <section aria-labelledby="replanning-report-title">
            <Title level={3} id="replanning-report-title">
              {t("replanning.reportTitle")}
            </Title>
            {data.report === null ? (
              <Alert type="info" showIcon title={t("replanning.reportNotFormed")} />
            ) : (
              <>
                <Alert
                  type="info"
                  showIcon
                  title={t("replanning.reportReadOnly")}
                  description={t("replanning.reportBoundary")}
                />
                <Descriptions bordered size="small" column={{ xs: 1, lg: 3 }}>
                  <Descriptions.Item label={t("replanning.tardinessBefore")}>
                    <RawSeconds value={data.report.tardiness.before_seconds} />
                  </Descriptions.Item>
                  <Descriptions.Item label={t("replanning.tardinessAfter")}>
                    <RawSeconds value={data.report.tardiness.after_seconds} />
                  </Descriptions.Item>
                  <Descriptions.Item label={t("replanning.tardinessDelta")}>
                    <RawSeconds value={data.report.tardiness.delta_seconds} />
                  </Descriptions.Item>
                  <Descriptions.Item label={t("replanning.softLockViolations")}>
                    {data.report.report.stability.soft_lock_violations}
                  </Descriptions.Item>
                  <Descriptions.Item label={t("replanning.changedExisting")}>
                    {data.report.report.stability.changed_existing_operations}
                  </Descriptions.Item>
                  <Descriptions.Item label={t("replanning.resourceChanges")}>
                    {data.report.report.stability.resource_changes}
                  </Descriptions.Item>
                  <Descriptions.Item label={t("replanning.absoluteShift")}>
                    <RawSeconds
                      value={data.report.report.stability.absolute_start_shift_seconds}
                    />
                  </Descriptions.Item>
                  <Descriptions.Item label={t("replanning.unchangedExisting")}>
                    {data.report.report.stability.unchanged_existing}
                  </Descriptions.Item>
                  <Descriptions.Item label={t("replanning.operationUniverse")}>
                    {data.report.report.operation_universe_count}
                  </Descriptions.Item>
                </Descriptions>
                <div className="table-scroll">
                  <table>
                    <caption>{t("replanning.operationsCaption")}</caption>
                    <thead>
                      <tr>
                        <th>{t("replanning.operationId")}</th>
                        <th>{t("replanning.classification")}</th>
                        <th>{t("replanning.baseAssignment")}</th>
                        <th>{t("replanning.newAssignment")}</th>
                        <th>{t("replanning.deltas")}</th>
                        <th>{t("replanning.reasons")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.report.report.operations.map((operation) => (
                        <tr key={operation.operation_id}>
                          <td>{operation.operation_id}</td>
                          <td>
                            <MachineValue
                              namespace="changeClassification"
                              raw={operation.classification}
                            />
                          </td>
                          <td>{assignmentSummary(operation.base_assignment)}</td>
                          <td>{assignmentSummary(operation.new_assignment)}</td>
                          <td>
                            <pre className="payload-cell">
                              {JSON.stringify(operation.deltas, null, 2)}
                            </pre>
                          </td>
                          <td>
                            <pre className="payload-cell">
                              {JSON.stringify(operation.reasons, null, 2)}
                            </pre>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </section>
        </div>
      )}
      <Paragraph type="secondary" className="replanning-footer-boundary">
        {t("replanning.phaseBoundary")}
      </Paragraph>
    </main>
  );
}
