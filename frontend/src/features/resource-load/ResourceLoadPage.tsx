import { Alert, Button, Flex, Typography } from "antd";
import { Link, useSearchParams } from "react-router-dom";

import { parseResourceLoads } from "../../api/contracts";
import type { ResourceLoad, WorkspaceUiState } from "../../api/types";
import { stateForError } from "../../app/state";
import { useScheduleVersion } from "../../app/useScheduleVersion";
import { useScheduleWorkspaceView } from "../../app/useWorkspaceView";
import { AuthorityPanel } from "../../components/AuthorityPanel";
import { WorkspaceStatePanel } from "../../components/WorkspaceStatePanel";
import { formatInteger, formatSeconds, formatUtc, formatUtilization } from "../../i18n/formatters";
import { useLocale } from "../../i18n/locale";

const { Paragraph, Title } = Typography;

export function ResourceLoadPage() {
  const { locale, t } = useLocale();
  const [search] = useSearchParams();
  const resourceId = search.get("resource_id")?.trim() ?? "";
  const { scheduleVersionId, query: versionQuery } = useScheduleVersion();
  const version = versionQuery.data;
  const loadQuery = useScheduleWorkspaceView("RESOURCE_LOAD", version, {
    filters: { resource_ids: resourceId.length === 0 ? [] : [resourceId] },
    pageSize: 500,
  });

  let state: WorkspaceUiState = "loading";
  let detail: string | undefined;
  let loads: ResourceLoad[] = [];
  if (scheduleVersionId === null || scheduleVersionId.length === 0) {
    state = "contract_error";
    detail = t("load.identityRequired");
  } else if (versionQuery.error !== null) {
    ({ state, detail } = stateForError(versionQuery.error, locale));
  } else if (loadQuery.error !== null) {
    ({ state, detail } = stateForError(loadQuery.error, locale));
  } else if (loadQuery.data !== undefined) {
    const result = loadQuery.data.document.result;
    if (result === null) {
      state = "contract_error";
      detail = t("load.resultMissing");
    } else if (result.freshness !== "FRESH") {
      state = "stale";
      detail = t("collection.stale", { freshness: result.freshness });
    } else if (!result.found || loadQuery.data.items.length === 0) {
      state = "empty";
    } else {
      try {
        loads = parseResourceLoads(loadQuery.data);
        state = "ready";
      } catch (error) {
        state = "contract_error";
        detail = error instanceof Error ? error.message : t("load.contractFailed");
      }
    }
  }
  const result = loadQuery.data?.document.result ?? null;

  return (
    <article className="workspace-page visualization-page">
      <Flex justify="space-between" align="flex-start" gap="middle" wrap>
        <div>
          <Title level={2}>{t("load.title")}</Title>
          <Paragraph type="secondary">
            {t("load.description")}
          </Paragraph>
        </div>
        <Button
          onClick={() => void loadQuery.refetch()}
          disabled={version === undefined || loadQuery.isFetching}
        >
          {t("common.refreshRead")}
        </Button>
      </Flex>
      {resourceId.length > 0 && (
        <Alert type="info" showIcon title={t("load.filter", { resource: resourceId })} />
      )}
      <WorkspaceStatePanel
        state={state}
        detail={detail}
        emptyKind={result?.found === false ? "missing" : "collection"}
      />
      {loadQuery.data !== undefined && state !== "contract_error" && (
        <div className="workspace-results">
          <AuthorityPanel response={loadQuery.data} />
          {result !== null && result.observed_count > loadQuery.data.items.length && (
            <Alert
              type="warning"
              showIcon
              title={t("load.partialRows", { observed: result.observed_count, shown: loadQuery.data.items.length })}
            />
          )}
          {state === "ready" && version !== undefined && (
            <div className="table-scroll">
              <table className="resource-load-table">
                <caption>{t("load.caption")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("gantt.resource")}</th>
                    <th scope="col">{t("load.horizonUtc")}</th>
                    <th scope="col">{t("load.assignments")}</th>
                    <th scope="col">{t("load.busySeconds")}</th>
                    <th scope="col">{t("load.availableSeconds")}</th>
                    <th scope="col">{t("load.utilization")}</th>
                    <th scope="col">{t("load.relatedGantt")}</th>
                  </tr>
                </thead>
                <tbody>
                  {loads.map((load) => {
                    const start = formatUtc(load.start_at_utc, locale);
                    const end = formatUtc(load.end_at_utc, locale);
                    const assignments = formatInteger(load.assignment_count, locale);
                    const busy = formatSeconds(load.planned_busy_seconds, locale);
                    const available = formatSeconds(load.available_seconds, locale);
                    const utilization = formatUtilization(load.utilization, locale);
                    return <tr key={load.item_id}>
                      <td>{load.resource_code}<br /><code>{load.resource_id}</code></td>
                      <td>
                        <time dateTime={load.start_at_utc}>{start.display}<code className="localized-raw">{start.raw}</code></time>
                        <br />{t("common.to")}<br />
                        <time dateTime={load.end_at_utc}>{end.display}<code className="localized-raw">{end.raw}</code></time>
                      </td>
                      <td>{assignments.display}<code className="localized-raw">{assignments.raw}</code></td>
                      <td>{busy.display}<code className="localized-raw">{busy.raw}</code></td>
                      <td>{available.display}<code className="localized-raw">{available.raw}</code></td>
                      <td>
                        <progress max={1} value={Math.min(load.utilization, 1)}>
                          {load.utilization}
                        </progress>
                        <output>{utilization.display}</output>
                        <code className="localized-raw">{utilization.raw}</code>
                      </td>
                      <td>
                        <Link
                          to={`/planning/versions/${encodeURIComponent(version.schedule_version_id)}/gantt/machines?resource_id=${encodeURIComponent(load.resource_id)}`}
                        >
                          {t("route.machineGantt")}
                        </Link>
                      </td>
                    </tr>;
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </article>
  );
}
