import { Alert, Button, Card, Flex, Input, Select, Space, Typography } from "antd";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { parseGanttSegments } from "../../api/contracts";
import type {
  GanttSegment,
  WorkspaceActionResult,
  WorkspaceHttpResponse,
  WorkspaceUiState,
} from "../../api/types";
import { useAppServices } from "../../app/context";
import { stateForError } from "../../app/state";
import { useScheduleVersion } from "../../app/useScheduleVersion";
import { useScheduleWorkspaceView } from "../../app/useWorkspaceView";
import { AuthorityPanel } from "../../components/AuthorityPanel";
import { WorkspaceStatePanel } from "../../components/WorkspaceStatePanel";
import { GanttEditControls } from "../schedule-actions/ScheduleActionsPanel";
import { GanttTimeline, type GanttGrouping } from "./GanttTimeline";
import { useLocale } from "../../i18n/locale";

const { Paragraph, Text, Title } = Typography;

interface OverlayProps {
  title: string;
  pending: boolean;
  error: unknown;
  data: WorkspaceHttpResponse | undefined;
}

function ServerOverlay({ title, pending, error, data }: OverlayProps) {
  const { locale, t } = useLocale();
  if (pending) return <Card title={title} loading />;
  if (error !== null) {
    return (
      <Card title={title}>
        <Alert type="error" showIcon title={stateForError(error, locale).detail} />
      </Card>
    );
  }
  if (data === undefined || data.items.length === 0) {
    return (
      <Card title={title}>
        <Alert
          type="warning"
          showIcon
          title={t("gantt.noOverlay")}
        />
      </Card>
    );
  }
  return (
    <Card title={title}>
      {data.items.map((item) => (
        <pre className="payload-cell" key={item.item_id}>
          {JSON.stringify(item.payload, null, 2)}
        </pre>
      ))}
    </Card>
  );
}

function oneFilter(value: string): string[] {
  const trimmed = value.trim();
  return trimmed.length === 0 ? [] : [trimmed];
}

export function GanttPage({ grouping }: { grouping: GanttGrouping }) {
  const navigate = useNavigate();
  const { runtime } = useAppServices();
  const { locale, t } = useLocale();
  const [search, setSearch] = useSearchParams();
  const initialOrder = search.get("order_id") ?? "";
  const initialResource = search.get("resource_id") ?? "";
  const [orderDraft, setOrderDraft] = useState(initialOrder);
  const [resourceDraft, setResourceDraft] = useState(initialResource);
  const [filters, setFilters] = useState({
    order_ids: oneFilter(initialOrder),
    resource_ids: oneFilter(initialResource),
  });
  const [zoom, setZoom] = useState(1);
  const [selected, setSelected] = useState<GanttSegment | null>(null);
  const [proposedOffsetSeconds, setProposedOffsetSeconds] = useState(0);
  const { scheduleVersionId, query: versionQuery } = useScheduleVersion();
  const version = versionQuery.data;
  const ganttQuery = useScheduleWorkspaceView("GANTT", version, {
    filters,
    pageSize: 500,
  });
  const kpiQuery = useScheduleWorkspaceView("KPI", version, { pageSize: 10 });
  const diagnosticsQuery = useScheduleWorkspaceView("DIAGNOSTICS", version, {
    pageSize: 100,
  });

  let state: WorkspaceUiState = "loading";
  let detail: string | undefined;
  let segments: GanttSegment[] = [];
  if (scheduleVersionId === null || scheduleVersionId.length === 0) {
    state = "contract_error";
    detail = t("gantt.identityRequired");
  } else if (versionQuery.error !== null) {
    ({ state, detail } = stateForError(versionQuery.error, locale));
  } else if (ganttQuery.error !== null) {
    ({ state, detail } = stateForError(ganttQuery.error, locale));
  } else if (ganttQuery.data !== undefined) {
    const result = ganttQuery.data.document.result;
    if (result === null) {
      state = "contract_error";
      detail = t("gantt.resultMissing");
    } else if (result.freshness !== "FRESH") {
      state = "stale";
      detail = t("collection.stale", { freshness: result.freshness });
    } else if (!result.found || ganttQuery.data.items.length === 0) {
      state = "empty";
    } else {
      try {
        segments = parseGanttSegments(ganttQuery.data);
        state = "ready";
      } catch (error) {
        state = "contract_error";
        detail = error instanceof Error ? error.message : t("gantt.contractFailed");
      }
    }
  }
  const result = ganttQuery.data?.document.result ?? null;
  const selection = {
    operationId: selected?.operation_id ?? null,
    orderId: selected?.order_id ?? filters.order_ids[0] ?? null,
    resourceId: selected?.resource_id ?? filters.resource_ids[0] ?? null,
  };
  const editable =
    runtime.dataPlane === "SIMULATION" &&
    runtime.environment !== "PRODUCTION" &&
    runtime.synthetic &&
    version?.synthetic === true &&
    version.state === "DRAFT" &&
    version.allowed_actions.includes("edit");

  async function refreshAuthority() {
    const refreshedVersion = await versionQuery.refetch();
    if (refreshedVersion.error !== null) throw refreshedVersion.error;
    const refreshedGantt = await ganttQuery.refetch();
    if (refreshedGantt.error !== null) throw refreshedGantt.error;
  }

  async function onActionResult(result: WorkspaceActionResult) {
    const authority = result.authoritativeVersion;
    if (authority === null) {
      throw new TypeError(t("gantt.commandNoVersion"));
    }
    setSelected(null);
    setProposedOffsetSeconds(0);
    if (authority.schedule_version_id !== version?.schedule_version_id) {
      void navigate(
        `/planning/versions/${encodeURIComponent(authority.schedule_version_id)}/gantt/${grouping === "factory" ? "factory" : grouping === "workshop" ? "workshops" : "machines"}`,
      );
      return;
    }
    await refreshAuthority();
  }

  function applyFilters() {
    const nextFilters = {
      order_ids: oneFilter(orderDraft),
      resource_ids: oneFilter(resourceDraft),
    };
    setFilters(nextFilters);
    setSelected(null);
    const nextSearch = new URLSearchParams(search);
    for (const [name, value] of [
      ["order_id", orderDraft.trim()],
      ["resource_id", resourceDraft.trim()],
    ] as const) {
      if (value.length === 0) nextSearch.delete(name);
      else nextSearch.set(name, value);
    }
    setSearch(nextSearch, { replace: true });
  }

  return (
    <article className="workspace-page visualization-page">
      <Flex justify="space-between" align="flex-start" gap="middle" wrap>
        <div>
          <Title level={2}>
            {t(grouping === "factory" ? "gantt.factoryTitle" : grouping === "workshop" ? "gantt.workshopTitle" : "gantt.machineTitle")}
          </Title>
          <Paragraph type="secondary">
            {t("gantt.description")}
          </Paragraph>
        </div>
        <Button
          onClick={() => void ganttQuery.refetch()}
          disabled={version === undefined || ganttQuery.isFetching}
        >
          {t("common.refreshRead")}
        </Button>
      </Flex>

      <section className="visualization-controls" aria-label={t("gantt.filtersAria")}>
        <label>
          {t("gantt.orderId")}
          <Input value={orderDraft} onChange={(event) => setOrderDraft(event.target.value)} />
        </label>
        <label>
          {t("gantt.resourceId")}
          <Input
            value={resourceDraft}
            onChange={(event) => setResourceDraft(event.target.value)}
          />
        </label>
        <label>
          {t("gantt.visualZoom")}
          <Select
            aria-label={t("gantt.visualZoom")}
            value={zoom}
            onChange={setZoom}
            options={[
              { label: "50%", value: 0.5 },
              { label: "100%", value: 1 },
              { label: "200%", value: 2 },
            ]}
          />
        </label>
        <Button type="primary" onClick={applyFilters}>{t("gantt.applyFilters")}</Button>
        <Button
          onClick={() => {
            setOrderDraft("");
            setResourceDraft("");
            setFilters({ order_ids: [], resource_ids: [] });
            setSelected(null);
            const nextSearch = new URLSearchParams(search);
            nextSearch.delete("order_id");
            nextSearch.delete("resource_id");
            setSearch(nextSearch, { replace: true });
          }}
        >
          {t("gantt.clear")}
        </Button>
      </section>

      <WorkspaceStatePanel
        state={state}
        detail={detail}
        emptyKind={result?.found === false ? "missing" : "collection"}
      />
      {ganttQuery.data !== undefined && state !== "contract_error" && (
        <Space orientation="vertical" size="large" className="workspace-results">
          <AuthorityPanel response={ganttQuery.data} />
          {result !== null && result.observed_count > ganttQuery.data.items.length && (
            <Alert
              type="warning"
              showIcon
              title={t("gantt.partialRows", { observed: result.observed_count, shown: ganttQuery.data.items.length })}
            />
          )}
          {state === "ready" && version !== undefined && (
            <>
              {selected !== null && (
                <Alert
                  type="info"
                  showIcon
                  title={t("gantt.selected", { operation: selected.operation_id })}
                  description={t("gantt.selectedDescription", { order: selected.order_id, resource: selected.resource_id })}
                />
              )}
              <GanttTimeline
                segments={segments}
                grouping={grouping}
                scheduleVersionId={version.schedule_version_id}
                zoom={zoom}
                selection={selection}
                editable={editable}
                onSelect={(segment) => {
                  setSelected(segment);
                  setProposedOffsetSeconds(0);
                }}
                onMoveIntent={(segment, offsetSeconds) => {
                  setSelected(segment);
                  setProposedOffsetSeconds(offsetSeconds);
                }}
              />
              {selected !== null && version !== undefined && (
                <GanttEditControls
                  key={`${selected.item_id}:${proposedOffsetSeconds}`}
                  version={version}
                  segment={selected}
                  proposedOffsetSeconds={proposedOffsetSeconds}
                  refreshAuthority={refreshAuthority}
                  onActionResult={onActionResult}
                />
              )}
            </>
          )}
        </Space>
      )}

      <Title level={3}>{t("gantt.overlayTitle")}</Title>
      <Paragraph>
        <Text strong>{t("gantt.noRecompute")}</Text> {t("gantt.overlayDescription")}
      </Paragraph>
      <div className="overlay-grid">
        <ServerOverlay
          title={t("gantt.kpiFacts")}
          pending={kpiQuery.isPending}
          error={kpiQuery.error}
          data={kpiQuery.data}
        />
        <ServerOverlay
          title={t("gantt.diagnosticFacts")}
          pending={diagnosticsQuery.isPending}
          error={diagnosticsQuery.error}
          data={diagnosticsQuery.data}
        />
      </div>
    </article>
  );
}
