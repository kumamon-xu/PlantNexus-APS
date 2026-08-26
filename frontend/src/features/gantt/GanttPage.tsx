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

const { Paragraph, Text, Title } = Typography;

interface OverlayProps {
  title: string;
  pending: boolean;
  error: unknown;
  data: WorkspaceHttpResponse | undefined;
}

function ServerOverlay({ title, pending, error, data }: OverlayProps) {
  if (pending) return <Card title={title} loading />;
  if (error !== null) {
    return (
      <Card title={title}>
        <Alert type="error" showIcon title={stateForError(error).detail} />
      </Card>
    );
  }
  if (data === undefined || data.items.length === 0) {
    return (
      <Card title={title}>
        <Alert
          type="warning"
          showIcon
          title="Server returned no overlay facts; nothing was inferred."
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
    detail = "A version-scoped Gantt route requires an immutable ScheduleVersion ID.";
  } else if (versionQuery.error !== null) {
    ({ state, detail } = stateForError(versionQuery.error));
  } else if (ganttQuery.error !== null) {
    ({ state, detail } = stateForError(ganttQuery.error));
  } else if (ganttQuery.data !== undefined) {
    const result = ganttQuery.data.document.result;
    if (result === null) {
      state = "contract_error";
      detail = "The Gantt RESULT carrier has no result body.";
    } else if (result.freshness !== "FRESH") {
      state = "stale";
      detail = `Server freshness is ${result.freshness}; refresh the Version precondition.`;
    } else if (!result.found || ganttQuery.data.items.length === 0) {
      state = "empty";
    } else {
      try {
        segments = parseGanttSegments(ganttQuery.data);
        state = "ready";
      } catch (error) {
        state = "contract_error";
        detail = error instanceof Error ? error.message : "Gantt payload contract failed.";
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
      throw new TypeError("Gantt command returned no authoritative Version");
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
          <Title level={2}>{grouping[0]?.toUpperCase()}{grouping.slice(1)} Gantt</Title>
          <Paragraph type="secondary">
            Server segments remain authoritative. In an isolated synthetic DRAFT, drag
            only proposes a bounded move; nothing changes until a command returns a new
            Version and the browser refreshes it.
          </Paragraph>
        </div>
        <Button
          onClick={() => void ganttQuery.refetch()}
          disabled={version === undefined || ganttQuery.isFetching}
        >
          Refresh read
        </Button>
      </Flex>

      <section className="visualization-controls" aria-label="Gantt read filters and zoom">
        <label>
          Order ID
          <Input value={orderDraft} onChange={(event) => setOrderDraft(event.target.value)} />
        </label>
        <label>
          Resource ID
          <Input
            value={resourceDraft}
            onChange={(event) => setResourceDraft(event.target.value)}
          />
        </label>
        <label>
          Visual zoom
          <Select
            aria-label="Visual zoom"
            value={zoom}
            onChange={setZoom}
            options={[
              { label: "50%", value: 0.5 },
              { label: "100%", value: 1 },
              { label: "200%", value: 2 },
            ]}
          />
        </label>
        <Button type="primary" onClick={applyFilters}>Apply server filters</Button>
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
          Clear
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
              title={`Server reports ${result.observed_count} matching rows; this bounded page shows ${ganttQuery.data.items.length}. Narrow the server filters to avoid a partial view.`}
            />
          )}
          {state === "ready" && version !== undefined && (
            <>
              {selected !== null && (
                <Alert
                  type="info"
                  showIcon
                  title={`Selected ${selected.operation_id}`}
                  description={`Order ${selected.order_id} · Resource ${selected.resource_id}`}
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

      <Title level={3}>Server KPI and diagnostics overlay</Title>
      <Paragraph>
        <Text strong>No browser recomputation:</Text> these payloads are rendered verbatim,
        and a missing or failed overlay remains visible.
      </Paragraph>
      <div className="overlay-grid">
        <ServerOverlay
          title="KPI facts"
          pending={kpiQuery.isPending}
          error={kpiQuery.error}
          data={kpiQuery.data}
        />
        <ServerOverlay
          title="Diagnostics facts"
          pending={diagnosticsQuery.isPending}
          error={diagnosticsQuery.error}
          data={diagnosticsQuery.data}
        />
      </div>
    </article>
  );
}
