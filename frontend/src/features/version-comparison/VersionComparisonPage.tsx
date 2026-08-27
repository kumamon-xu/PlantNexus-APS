import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Descriptions, Flex, Input, Radio, Tag, Typography } from "antd";
import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { parseVersionComparison } from "../../api/contracts";
import { buildWorkspaceQuery } from "../../api/query";
import type {
  OperationDelta,
  ScheduleVersionComparison,
  WorkspaceUiState,
} from "../../api/types";
import { useAppServices } from "../../app/context";
import { stateForError } from "../../app/state";
import { useScheduleVersion } from "../../app/useScheduleVersion";
import { AuthorityPanel } from "../../components/AuthorityPanel";
import { WorkspaceStatePanel } from "../../components/WorkspaceStatePanel";
import { labelBusinessValue } from "../../i18n/business-labels";
import { formatNumber, formatUtc } from "../../i18n/formatters";
import { useLocale } from "../../i18n/locale";

const { Paragraph, Text, Title } = Typography;
type DeltaFilter = "ALL" | "CHANGED" | "UNCHANGED";

function visibleDeltas(
  deltas: OperationDelta[],
  filter: DeltaFilter,
): OperationDelta[] {
  if (filter === "ALL") return deltas;
  if (filter === "UNCHANGED") {
    return deltas.filter((delta) => delta.change_kind === "UNCHANGED");
  }
  return deltas.filter((delta) => delta.change_kind !== "UNCHANGED");
}

export function VersionComparisonPage() {
  const { client, runtime } = useAppServices();
  const { locale, t } = useLocale();
  const [search, setSearch] = useSearchParams();
  const initialCompared = search.get("compared_schedule_version_id") ?? "";
  const [comparedDraft, setComparedDraft] = useState(initialCompared);
  const [requestedId, setRequestedId] = useState(initialCompared.trim());
  const [deltaFilter, setDeltaFilter] = useState<DeltaFilter>("CHANGED");
  const { scheduleVersionId, query: baseQuery } = useScheduleVersion();
  const baseVersion = baseQuery.data;
  const comparedQuery = useQuery({
    queryKey: ["compared-schedule-version", requestedId],
    queryFn: () => client.getScheduleVersion(requestedId),
    enabled: requestedId.length > 0,
    retry: false,
    staleTime: 0,
  });
  const comparedVersion = comparedQuery.data;
  const comparisonQuery = useQuery({
    queryKey: [
      "version-comparison",
      baseVersion?.schedule_version_id ?? "ABSENT",
      baseVersion?.state ?? "ABSENT",
      baseVersion?.content_fingerprint ?? "ABSENT",
      comparedVersion?.schedule_version_id ?? "ABSENT",
      comparedVersion?.state ?? "ABSENT",
      comparedVersion?.content_fingerprint ?? "ABSENT",
    ],
    queryFn: async () => {
      if (baseVersion === undefined || comparedVersion === undefined) {
        throw new Error(t("comparison.preconditionsRequired"));
      }
      const query = await buildWorkspaceQuery({
        authority: runtime,
        view: "VERSION_COMPARISON",
        scheduleVersion: baseVersion,
        pageSize: 1,
      });
      return client.compareScheduleVersions(query, comparedVersion);
    },
    enabled:
      baseVersion !== undefined &&
      comparedVersion !== undefined &&
      baseVersion.schedule_version_id !== comparedVersion.schedule_version_id,
    retry: false,
    staleTime: 0,
  });

  let state: WorkspaceUiState = "loading";
  let detail: string | undefined;
  let comparison: ScheduleVersionComparison | null = null;
  if (scheduleVersionId === null || scheduleVersionId.length === 0) {
    state = "contract_error";
    detail = t("comparison.identityRequired");
  } else if (baseQuery.error !== null) {
    ({ state, detail } = stateForError(baseQuery.error, locale));
  } else if (requestedId.length === 0) {
    state = "empty";
    detail = t("comparison.enterCompared");
  } else if (baseVersion?.schedule_version_id === requestedId) {
    state = "contract_error";
    detail = t("comparison.mustDiffer");
  } else if (comparedQuery.error !== null) {
    ({ state, detail } = stateForError(comparedQuery.error, locale));
  } else if (comparisonQuery.error !== null) {
    ({ state, detail } = stateForError(comparisonQuery.error, locale));
  } else if (comparisonQuery.data !== undefined) {
    const result = comparisonQuery.data.document.result;
    if (result === null) {
      state = "contract_error";
      detail = t("comparison.resultMissing");
    } else if (result.freshness !== "FRESH") {
      state = "stale";
      detail = t("comparison.stale", { freshness: result.freshness });
    } else if (!result.found || comparisonQuery.data.items.length === 0) {
      state = "empty";
    } else {
      try {
        comparison = parseVersionComparison(comparisonQuery.data);
        state = "ready";
      } catch (error) {
        state = "contract_error";
        detail = error instanceof Error ? error.message : t("comparison.contractFailed");
      }
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const next = comparedDraft.trim();
    setRequestedId(next);
    const nextSearch = new URLSearchParams(search);
    if (next.length === 0) nextSearch.delete("compared_schedule_version_id");
    else nextSearch.set("compared_schedule_version_id", next);
    setSearch(nextSearch, { replace: true });
  }

  const deltas = comparison === null
    ? []
    : visibleDeltas(comparison.operation_deltas, deltaFilter);

  return (
    <article className="workspace-page visualization-page">
      <Title level={2}>{t("comparison.title")}</Title>
      <Paragraph type="secondary">
        {t("comparison.description")}
      </Paragraph>
      <form className="comparison-form" onSubmit={submit}>
        <label htmlFor="compared-version-id">{t("comparison.comparedId")}</label>
        <Input
          id="compared-version-id"
          value={comparedDraft}
          onChange={(event) => setComparedDraft(event.target.value)}
        />
        <Button htmlType="submit" type="primary">{t("comparison.run")}</Button>
      </form>

      {requestedId.length === 0 ? (
        <Alert type="info" showIcon title={detail} />
      ) : (
        <WorkspaceStatePanel state={state} detail={detail} />
      )}

      {comparisonQuery.data !== undefined && state !== "contract_error" && (
        <div className="workspace-results">
          <AuthorityPanel response={comparisonQuery.data} />
        </div>
      )}

      {comparison !== null && state === "ready" && (
        <>
          <Descriptions bordered size="small" column={1} className="comparison-authority">
            <Descriptions.Item label={t("comparison.id")}>
              <Text copyable>{comparison.comparison_id}</Text>
            </Descriptions.Item>
            <Descriptions.Item label={t("comparison.baseVersion")}>
              {comparison.base_version.schedule_version_id} · {labelBusinessValue("scheduleState", comparison.base_version.state, locale).label} <Text code>{comparison.base_version.state}</Text>
            </Descriptions.Item>
            <Descriptions.Item label={t("comparison.comparedVersion")}>
              {comparison.compared_version.schedule_version_id} · {labelBusinessValue("scheduleState", comparison.compared_version.state, locale).label} <Text code>{comparison.compared_version.state}</Text>
            </Descriptions.Item>
            <Descriptions.Item label={t("comparison.fingerprint")}>
              <Text copyable>{comparison.comparison_fingerprint}</Text>
            </Descriptions.Item>
            <Descriptions.Item label={t("comparison.generatedRawUtc")}>
              <time dateTime={comparison.generated_at_utc}>
                {formatUtc(comparison.generated_at_utc, locale).display}
                <code className="localized-raw">{comparison.generated_at_utc}</code>
              </time>
            </Descriptions.Item>
          </Descriptions>

          <Title level={3}>{t("comparison.summary")}</Title>
          <dl className="comparison-summary">
            {Object.entries(comparison.summary).map(([name, value]) => {
              const display = typeof value === "number"
                ? formatNumber(value, locale).display
                : String(value);
              return <div key={name}><dt>{labelBusinessValue("businessTerm", name, locale).label}<code className="localized-raw">{name}</code></dt><dd>{display}<code className="localized-raw">{String(value)}</code></dd></div>;
            })}
          </dl>

          <Title level={3}>{t("comparison.kpiDeltas")}</Title>
          <div className="table-scroll">
            <table>
              <caption>{t("comparison.kpiCaption")}</caption>
              <thead><tr><th scope="col">{t("comparison.metric")}</th><th scope="col">{t("comparison.base")}</th><th scope="col">{t("comparison.compared")}</th><th scope="col">{t("comparison.delta")}</th></tr></thead>
              <tbody>
                {comparison.kpi_deltas.map((delta) => (
                  <tr key={delta.metric}><th scope="row">{labelBusinessValue("businessTerm", delta.metric, locale).label}<code className="localized-raw">{delta.metric}</code></th><td>{formatNumber(delta.base_value, locale).display}<code className="localized-raw">{String(delta.base_value)}</code></td><td>{formatNumber(delta.compared_value, locale).display}<code className="localized-raw">{String(delta.compared_value)}</code></td><td>{formatNumber(delta.delta, locale).display}<code className="localized-raw">{String(delta.delta)}</code></td></tr>
                ))}
              </tbody>
            </table>
          </div>

          <Flex justify="space-between" align="center" gap="middle" wrap>
            <Title level={3}>{t("comparison.operationDeltas")}</Title>
            <Radio.Group
              aria-label={t("comparison.visibilityAria")}
              value={deltaFilter}
              onChange={(event) => setDeltaFilter(event.target.value as DeltaFilter)}
              options={[
                { label: t("comparison.changed"), value: "CHANGED" },
                { label: t("comparison.unchanged"), value: "UNCHANGED" },
                { label: t("comparison.all"), value: "ALL" },
              ]}
            />
          </Flex>
          <div className="table-scroll">
            <table>
              <caption>{t("comparison.operationCaption", { filter: deltaFilter })}</caption>
              <thead>
                <tr><th scope="col">{t("gantt.operation")}</th><th scope="col">{t("comparison.changeKind")}</th><th scope="col">{t("comparison.baseResourceTime")}</th><th scope="col">{t("comparison.comparedResourceTime")}</th></tr>
              </thead>
              <tbody>
                {deltas.map((delta) => (
                  <tr key={delta.operation_id}>
                    <th scope="row">{delta.operation_id}</th>
                    <td><Tag>{labelBusinessValue("changeKind", delta.change_kind, locale).label}</Tag><code className="localized-raw">{delta.change_kind}</code></td>
                    <td>{delta.base_resource_id ?? t("common.absent")}<br />{delta.base_start_at_utc === null ? t("common.absent") : formatUtc(delta.base_start_at_utc, locale).display}<br />{delta.base_end_at_utc === null ? t("common.absent") : formatUtc(delta.base_end_at_utc, locale).display}<code className="localized-raw">{delta.base_start_at_utc ?? "null"} · {delta.base_end_at_utc ?? "null"}</code></td>
                    <td>{delta.compared_resource_id ?? t("common.absent")}<br />{delta.compared_start_at_utc === null ? t("common.absent") : formatUtc(delta.compared_start_at_utc, locale).display}<br />{delta.compared_end_at_utc === null ? t("common.absent") : formatUtc(delta.compared_end_at_utc, locale).display}<code className="localized-raw">{delta.compared_start_at_utc ?? "null"} · {delta.compared_end_at_utc ?? "null"}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Flex gap="middle" wrap>
            <Link to={`/planning/versions/${encodeURIComponent(comparison.base_version.schedule_version_id)}/gantt/factory`}>{t("comparison.baseGantt")}</Link>
            <Link to={`/planning/versions/${encodeURIComponent(comparison.compared_version.schedule_version_id)}/gantt/factory`}>{t("comparison.comparedGantt")}</Link>
          </Flex>
        </>
      )}
    </article>
  );
}
