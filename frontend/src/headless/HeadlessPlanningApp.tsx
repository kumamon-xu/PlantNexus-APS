import {
  Alert,
  Button,
  Card,
  Descriptions,
  Input,
  Layout,
  Space,
  Tag,
  Typography,
} from "antd";
import { useId, useState } from "react";

import type { RuntimeConfig } from "../api/runtime";
import { useLocale } from "../i18n/locale";
import type { AppLocale } from "../i18n/types";
import { HeadlessClientError, type HeadlessPlanningClient } from "./client";
import { parseCanonicalIngressRequestText } from "./contracts";
import type {
  CanonicalIngressResult,
  EffectiveScope,
  PlanningRun,
  RuntimeResolution,
} from "./types";
import "./headless.css";

const { Content, Header } = Layout;
const { Paragraph, Text, Title } = Typography;
const { TextArea } = Input;

interface VisibleFailure {
  kind: string;
  message: string;
  status: number | null;
  correlationId: string | null;
  code: string | null;
}

export function HeadlessPlanningApp({
  client,
  runtime,
}: {
  client: HeadlessPlanningClient;
  runtime: RuntimeConfig;
}) {
  const { locale, setLocale, t } = useLocale();
  const [requestText, setRequestText] = useState("");
  const [accepted, setAccepted] = useState<CanonicalIngressResult | null>(null);
  const [scope, setScope] = useState<EffectiveScope | null>(null);
  const [run, setRun] = useState<PlanningRun | null>(null);
  const [failure, setFailure] = useState<VisibleFailure | null>(null);
  const [busy, setBusy] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const runtimeResolution: RuntimeResolution | null =
    run?.runtime_resolution ?? accepted?.accepted?.runtime_resolution ?? null;
  const runReference = run ?? accepted?.accepted?.planning_run ?? null;
  const canRead = runReference !== null && scope !== null;
  const correlationId = `CORRELATION-P8-FRONTEND-${useId()}`;

  function showFailure(error: unknown): void {
    if (error instanceof HeadlessClientError) {
      setFailure({
        kind: error.kind,
        message: error.message,
        status: error.status,
        correlationId: error.correlationId,
        code: error.code,
      });
      return;
    }
    setFailure({
      kind: "contract_error",
      message: error instanceof Error ? error.message : t("headless.errorUnexpected"),
      status: null,
      correlationId: null,
      code: "CONTRACT_VIOLATION",
    });
  }

  async function submit(): Promise<void> {
    setBusy(true);
    setFailure(null);
    try {
      const request = parseCanonicalIngressRequestText(requestText);
      const result = await client.create(requestText);
      if (result.disposition !== "ACCEPTED" || result.accepted === null) {
        throw new HeadlessClientError(
          "contract_error",
          result.rejection?.message ?? t("headless.rejected"),
          null,
          result.correlation_id,
          result.rejection?.code ?? null,
        );
      }
      setAccepted(result);
      setScope({
        ...result.effective_scope,
        scope_fingerprint: result.effective_scope.scope_fingerprint,
      });
      setRun(null);
      if (
        request.requestedScope.tenant_id !== result.effective_scope.tenant_id ||
        request.requestedScope.factory_id !== result.effective_scope.factory_id ||
        request.requestedScope.planning_scope_id !==
          result.effective_scope.planning_scope_id
      ) {
        throw new Error(t("headless.scopeChanged"));
      }
    } catch (error) {
      showFailure(error);
    } finally {
      setBusy(false);
    }
  }

  async function refresh(operation: "status" | "result"): Promise<void> {
    if (!canRead) return;
    setBusy(true);
    setFailure(null);
    try {
      const value = await client[operation](
        runReference.planning_run_id,
        scope,
        correlationId,
      );
      setRun(value);
    } catch (error) {
      showFailure(error);
    } finally {
      setBusy(false);
    }
  }

  async function cancel(): Promise<void> {
    if (run === null || cancelReason.trim().length === 0) return;
    setBusy(true);
    setFailure(null);
    try {
      const value = await client.cancel(
        run,
        cancelReason,
        `p8-frontend-cancel-${crypto.randomUUID()}`,
        correlationId,
      );
      setRun(value);
    } catch (error) {
      showFailure(error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Layout className="headless-shell" data-locale={locale}>
      <Header className="app-header">
        <div>
          <Title level={1}>PlantNexus APS</Title>
          <Text>{t("headless.appTitle")}</Text>
        </div>
        <Space wrap>
          <label className="locale-control">
            <span>{t("locale.label")}</span>
            <select
              className="headless-locale-select"
              aria-label={t("locale.label")}
              value={locale}
              onChange={(event) => setLocale(event.target.value as AppLocale)}
            >
              <option value="zh-CN">{t("locale.zhCN")}</option>
              <option value="en-US">{t("locale.enUS")}</option>
            </select>
          </label>
          <Tag color={runtime.dataPlane === "SIMULATION" ? "gold" : "green"}>
            {runtime.dataPlane} / {runtime.environment}
          </Tag>
        </Space>
      </Header>
      <Content className="headless-content" id="main-content">
        <Alert
          type="info"
          showIcon
          title={t("headless.boundaryTitle")}
          description={t("headless.boundaryDescription")}
        />
        <Card title={t("headless.createTitle")}>
          <Paragraph>{t("headless.createDescription")}</Paragraph>
          <label htmlFor="canonical-request">{t("headless.canonicalJson")}</label>
          <TextArea
            id="canonical-request"
            aria-label={t("headless.canonicalJson")}
            autoSize={{ minRows: 10, maxRows: 24 }}
            spellCheck={false}
            value={requestText}
            onChange={(event) => setRequestText(event.target.value)}
          />
          <Button
            type="primary"
            loading={busy}
            disabled={requestText.trim().length === 0}
            onClick={() => void submit()}
          >
            {t("headless.submit")}
          </Button>
        </Card>

        {failure !== null ? (
          <Alert
            type="error"
            showIcon
            title={t("headless.failureTitle")}
            description={
              <dl className="headless-diagnostics">
                <dt>{t("headless.failureKind")}</dt>
                <dd>{failure.kind}</dd>
                <dt>{t("headless.failureMessage")}</dt>
                <dd>{failure.message}</dd>
                <dt>{t("headless.failureCode")}</dt>
                <dd>{failure.code ?? t("common.absent")}</dd>
                <dt>{t("headless.failureStatus")}</dt>
                <dd>{failure.status ?? t("common.absent")}</dd>
                <dt>{t("headless.failureCorrelation")}</dt>
                <dd>{failure.correlationId ?? t("common.absent")}</dd>
              </dl>
            }
          />
        ) : null}

        {runReference !== null ? (
          <Card title={t("headless.runTitle")}>
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label={t("headless.runId")}>
                <Text copyable>{runReference.planning_run_id}</Text>
              </Descriptions.Item>
              <Descriptions.Item label={t("headless.runState")}>
                <Tag>{runReference.state}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label={t("headless.runRevision")}>
                {runReference.revision}
              </Descriptions.Item>
              <Descriptions.Item label={t("headless.runFingerprint")}>
                <Text className="fingerprint-wrap">{runReference.run_fingerprint}</Text>
              </Descriptions.Item>
            </Descriptions>
            <Space wrap>
              <Button disabled={!canRead || busy} onClick={() => void refresh("status")}>
                {t("headless.refreshStatus")}
              </Button>
              <Button
                disabled={!canRead || busy || run?.terminal !== true}
                onClick={() => void refresh("result")}
              >
                {t("headless.loadResult")}
              </Button>
            </Space>
            {run?.allowed_actions.includes("CANCEL") === true ? (
              <Space.Compact block>
                <Input
                  aria-label={t("headless.cancelReason")}
                  placeholder={t("headless.cancelReason")}
                  value={cancelReason}
                  onChange={(event) => setCancelReason(event.target.value)}
                />
                <Button
                  danger
                  disabled={busy || cancelReason.trim().length === 0}
                  onClick={() => void cancel()}
                >
                  {t("headless.cancel")}
                </Button>
              </Space.Compact>
            ) : null}
          </Card>
        ) : null}

        {runtimeResolution !== null ? (
          <Card title={t("headless.runtimeTitle")}>
            <Paragraph>{t("headless.runtimeDescription")}</Paragraph>
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label={t("headless.runtimeVersion")}>
                {runtimeResolution.runtime_version}
              </Descriptions.Item>
              <Descriptions.Item label={t("headless.runtimeFingerprint")}>
                <Text className="fingerprint-wrap">
                  {runtimeResolution.runtime_artifact_fingerprint}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label={t("headless.extensionSet")}>
                {runtimeResolution.extension_set.extension_set_id}
              </Descriptions.Item>
              <Descriptions.Item label={t("headless.extensionFingerprint")}>
                <Text className="fingerprint-wrap">
                  {runtimeResolution.extension_set.extension_set_fingerprint}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label={t("headless.extensionConfigFingerprint")}>
                <Text className="fingerprint-wrap">
                  {runtimeResolution.extension_set.configuration_fingerprint}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label={t("headless.validatorVersion")}>
                {runtimeResolution.validator_version}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        ) : null}
      </Content>
    </Layout>
  );
}
