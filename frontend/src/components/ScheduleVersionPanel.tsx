import { Descriptions, Tag, Typography } from "antd";

import type { ScheduleVersion } from "../api/types";
import { labelBusinessValue } from "../i18n/business-labels";
import { formatInteger, formatUtc } from "../i18n/formatters";
import { useLocale } from "../i18n/locale";

const { Text, Title } = Typography;

export function ScheduleVersionPanel({ version }: { version: ScheduleVersion }) {
  const { locale, t } = useLocale();
  const state = labelBusinessValue("scheduleState", version.state, locale);
  const plane = labelBusinessValue("dataPlane", version.data_plane, locale);
  const environment = labelBusinessValue("environment", version.environment, locale);
  const created = formatUtc(version.created_at_utc, locale);
  return (
    <section aria-label={t("version.section")}>
      <Title level={3}>{t("version.title")}</Title>
      <Descriptions bordered column={1} size="small">
        <Descriptions.Item label={t("version.identity")}>
          <Text copyable>{version.schedule_version_id}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t("version.state")}>
          <Tag color="green">{state.label}</Tag> <Text code>{state.raw}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t("version.revision")}>
          {formatInteger(version.revision, locale).display} <Text code>{version.revision}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t("version.planeEnvironment")}>
          {plane.label} <Text code>{plane.raw}</Text> / {environment.label}{" "}
          <Text code>{environment.raw}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t("version.parent")}>
          {version.parent_schedule_version?.schedule_version_id ?? t("common.none")}
        </Descriptions.Item>
        <Descriptions.Item label={t("authority.contentFingerprint")}>
          <Text copyable>{version.content_fingerprint}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t("version.snapshotFingerprint")}>
          <Text copyable>{version.lineage.snapshot.fingerprint}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t("version.problemFingerprint")}>
          <Text copyable>{version.lineage.problem.fingerprint}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t("version.solutionFingerprint")}>
          <Text copyable>{version.lineage.planning_solution.fingerprint}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t("version.validationFingerprint")}>
          <Text copyable>{version.lineage.validation_report.fingerprint}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t("version.createdRawUtc")}>
          <time dateTime={version.created_at_utc}>
            {created.display}<code className="localized-raw">{created.raw}</code>
          </time>
        </Descriptions.Item>
        <Descriptions.Item label={t("version.allowedActions")}>
          {version.allowed_actions.length === 0
            ? t("common.none")
            : version.allowed_actions.map(String).map((action, index) => {
                const value = labelBusinessValue("allowedAction", action, locale);
                return <span key={`${action}:${index}`}>{index > 0 ? ", " : ""}{value.label} <Text code>{value.raw}</Text></span>;
              })}
        </Descriptions.Item>
      </Descriptions>
    </section>
  );
}
