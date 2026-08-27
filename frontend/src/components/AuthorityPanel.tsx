import { Descriptions, Tag, Typography } from "antd";

import type {
  ScheduleLineage,
  VersionReference,
  WorkspaceHttpResponse,
} from "../api/types";
import { labelBusinessValue } from "../i18n/business-labels";
import { formatUtc } from "../i18n/formatters";
import { useLocale } from "../i18n/locale";

const { Text } = Typography;

function lineageFingerprints(lineage: ScheduleLineage | null, missing: string): string {
  if (lineage === null) return missing;
  return [
    lineage.snapshot.fingerprint,
    lineage.problem.fingerprint,
    lineage.planning_solution.fingerprint,
    lineage.validation_report.fingerprint,
    lineage.kpi.fingerprint,
    lineage.solver_report.fingerprint,
  ].join(" · ");
}

export function AuthorityPanel({ response }: { response: WorkspaceHttpResponse }) {
  const { locale, t } = useLocale();
  const result = response.document.result;
  if (result === null) return null;
  const authority: VersionReference | null = result.authoritative_schedule_version;
  return (
    <section aria-label={t("authority.section")}>
      <Descriptions bordered size="small" column={1}>
        <Descriptions.Item label={t("authority.authority")}>
          <Tag color="green">{t("authority.serverApplication")}</Tag>
          <Text code>{response.document.data_plane}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t("authority.scheduleVersion")}>
          {authority === null
            ? t("authority.workspaceScope")
            : <>{authority.schedule_version_id} · {labelBusinessValue("scheduleState", authority.state, locale).label} <Text code>{authority.state}</Text></>}
        </Descriptions.Item>
        <Descriptions.Item label={t("authority.contentFingerprint")}>
          <Text copyable>{authority?.content_fingerprint ?? t("authority.notScheduleScoped")}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t("authority.sourceCollection")}>
          <Text copyable>
            {response.source_fingerprint ?? t("common.missing")} ·{" "}
            {response.collection_fingerprint ?? t("common.missing")}
          </Text>
        </Descriptions.Item>
        <Descriptions.Item label={t("authority.lineageFingerprints")}>
          <Text className="fingerprint-wrap">{lineageFingerprints(result.lineage, t("authority.notScheduleScoped"))}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t("authority.generatedRawUtc")}>
          <time dateTime={result.generated_at_utc}>
            {formatUtc(result.generated_at_utc, locale).display}
            <code className="localized-raw">{result.generated_at_utc}</code>
          </time>
        </Descriptions.Item>
        <Descriptions.Item label={t("authority.correlationId")}>
          <Text copyable>{response.correlation_id}</Text>
        </Descriptions.Item>
      </Descriptions>
    </section>
  );
}
