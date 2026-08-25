import { Alert, Space, Typography } from "antd";
import { Link } from "react-router-dom";

import { stateForError } from "../app/state";
import { useScheduleVersion } from "../app/useScheduleVersion";
import { ScheduleVersionPanel } from "../components/ScheduleVersionPanel";
import { WorkspaceStatePanel } from "../components/WorkspaceStatePanel";

const { Paragraph, Title } = Typography;

export function ScheduleVersionPage() {
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
  const search = `?schedule_version_id=${encodeURIComponent(query.data.schedule_version_id)}`;
  return (
    <article className="workspace-page">
      <Title level={2}>ScheduleVersion authority</Title>
      <Paragraph type="secondary">
        This page exposes immutable identity, state and lineage without offering a
        client-side transition.
      </Paragraph>
      <Alert
        type="info"
        showIcon
        message="Read-only P3-11 boundary"
        description="Server allowed_actions are displayed as facts; no action control is mounted."
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
      </Space>
    </article>
  );
}
