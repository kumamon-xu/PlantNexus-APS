import { Alert, Space, Typography } from "antd";
import { Link, useNavigate } from "react-router-dom";

import type { WorkspaceActionResult } from "../api/types";
import { useAppServices } from "../app/context";
import { stateForError } from "../app/state";
import { useScheduleVersion } from "../app/useScheduleVersion";
import { ScheduleVersionPanel } from "../components/ScheduleVersionPanel";
import { WorkspaceStatePanel } from "../components/WorkspaceStatePanel";
import { ApprovalPanel } from "../features/approval/ApprovalPanel";
import { AuditHistoryPanel } from "../features/audit/AuditHistoryPanel";
import { ExportPanel } from "../features/export/ExportPanel";
import { PublicationPanel } from "../features/publication/PublicationPanel";
import { ScheduleActionsPanel } from "../features/schedule-actions/ScheduleActionsPanel";

const { Paragraph, Title } = Typography;

export function ScheduleVersionPage() {
  const navigate = useNavigate();
  const { runtime } = useAppServices();
  const { scheduleVersionId, query } = useScheduleVersion();
  if (scheduleVersionId === null || scheduleVersionId.length === 0) {
    return (
      <WorkspaceStatePanel
        state="contract_error"
        detail="ScheduleVersion identity is required."
      />
    );
  }
  if (query.isPending) return <WorkspaceStatePanel state="loading" />;
  if (query.error !== null) {
    const failure = stateForError(query.error);
    return <WorkspaceStatePanel {...failure} />;
  }
  if (query.data === undefined) {
    return <WorkspaceStatePanel state="contract_error" />;
  }
  async function refreshAuthority() {
    const refreshed = await query.refetch();
    if (refreshed.error !== null) throw refreshed.error;
  }

  async function onActionResult(result: WorkspaceActionResult) {
    const authority = result.authoritativeVersion;
    if (
      authority !== null &&
      authority.schedule_version_id !== query.data?.schedule_version_id
    ) {
      void navigate(
        `/planning/versions/${encodeURIComponent(authority.schedule_version_id)}`,
      );
      return;
    }
    await refreshAuthority();
  }

  const search = `?schedule_version_id=${encodeURIComponent(query.data.schedule_version_id)}`;
  const humanControlsEnabled =
    runtime.dataPlane === "SIMULATION" &&
    runtime.environment !== "PRODUCTION" &&
    runtime.synthetic &&
    query.data.synthetic;
  return (
    <article className="workspace-page">
      <Title level={2}>ScheduleVersion authority</Title>
      <Paragraph type="secondary">
        Identity, state and lineage remain server authority. Human controls submit
        versioned commands and accept only the returned authoritative result.
      </Paragraph>
      <Alert
        type="info"
        showIcon
        title="P3-13 bounded human-control surface"
        description="Controls are isolated to synthetic Simulation tests. Production identity, MES publication and P4 replanning remain unavailable."
      />
      <ScheduleVersionPanel version={query.data} />
      <Space wrap>
        <Link to={`/planning/versions/${encodeURIComponent(query.data.schedule_version_id)}/orders`}>
          Orders
        </Link>
        <Link to={`/operations${search}`}>Operations</Link>
        <Link to={`/resources${search}`}>Resources</Link>
        <Link to={`/calendars${search}`}>Calendars</Link>
        <Link to={`/validation${search}`}>Validation</Link>
        <Link to={`/kpi${search}`}>KPI</Link>
        <Link to={`/diagnostics${search}`}>Diagnostics</Link>
        <Link to={`/audit${search}`}>Audit</Link>
        <Link
          to={`/planning/versions/${encodeURIComponent(query.data.schedule_version_id)}/gantt/factory`}
        >
          Factory Gantt
        </Link>
        <Link
          to={`/planning/versions/${encodeURIComponent(query.data.schedule_version_id)}/gantt/workshops`}
        >
          Workshop Gantt
        </Link>
        <Link
          to={`/planning/versions/${encodeURIComponent(query.data.schedule_version_id)}/gantt/machines`}
        >
          Machine Gantt
        </Link>
        <Link to={`/resource-load${search}`}>Resource Load</Link>
        <Link to={`/compare${search}`}>Version comparison</Link>
      </Space>
      <Title level={3}>Human controls</Title>
      {!humanControlsEnabled && (
        <Alert
          type="warning"
          showIcon
          title="Human controls are hidden in this runtime."
          description="Production remains default-deny until its separate identity and authorization gates close."
        />
      )}
      {humanControlsEnabled && (
        <div className="control-stack">
          {query.data.state === "DRAFT" && (
            <ScheduleActionsPanel
              version={query.data}
              refreshAuthority={refreshAuthority}
              onActionResult={onActionResult}
            />
          )}
          {query.data.state === "READY_FOR_REVIEW" && (
            <ApprovalPanel
              version={query.data}
              refreshAuthority={refreshAuthority}
              onActionResult={onActionResult}
            />
          )}
          {query.data.state === "APPROVED" && (
            <PublicationPanel
              version={query.data}
              refreshAuthority={refreshAuthority}
              onActionResult={onActionResult}
            />
          )}
          {query.data.state === "PUBLISHED" && (
            <ExportPanel version={query.data} refreshAuthority={refreshAuthority} />
          )}
          <AuditHistoryPanel version={query.data} />
        </div>
      )}
    </article>
  );
}
