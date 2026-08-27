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
import { labelBusinessValue } from "../i18n/business-labels";
import { useLocale } from "../i18n/locale";

const { Paragraph, Title } = Typography;

export function ScheduleVersionPage() {
  const navigate = useNavigate();
  const { runtime } = useAppServices();
  const { locale, t } = useLocale();
  const { scheduleVersionId, query } = useScheduleVersion();
  if (scheduleVersionId === null || scheduleVersionId.length === 0) {
    return (
      <WorkspaceStatePanel
        state="contract_error"
        detail={t("schedule.identityRequired")}
      />
    );
  }
  if (query.isPending) return <WorkspaceStatePanel state="loading" />;
  if (query.error !== null) {
    const failure = stateForError(query.error, locale);
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
      <Title level={2}>{t("schedule.title")}</Title>
      <Paragraph type="secondary">
        {t("schedule.description")}
      </Paragraph>
      <Alert
        type="info"
        showIcon
        title={t("schedule.boundaryTitle")}
        description={t("schedule.boundaryDescription")}
      />
      <ScheduleVersionPanel version={query.data} />
      <Space wrap>
        <Link to={`/planning/versions/${encodeURIComponent(query.data.schedule_version_id)}/orders`}>
          {labelBusinessValue("workspaceView", "ORDERS", locale).label}
        </Link>
        <Link to={`/operations${search}`}>{labelBusinessValue("workspaceView", "OPERATIONS", locale).label}</Link>
        <Link to={`/resources${search}`}>{labelBusinessValue("workspaceView", "RESOURCES", locale).label}</Link>
        <Link to={`/calendars${search}`}>{labelBusinessValue("workspaceView", "CALENDARS", locale).label}</Link>
        <Link to={`/validation${search}`}>{t("route.validation")}</Link>
        <Link to={`/kpi${search}`}>{labelBusinessValue("workspaceView", "KPI", locale).label}</Link>
        <Link to={`/diagnostics${search}`}>{labelBusinessValue("workspaceView", "DIAGNOSTICS", locale).label}</Link>
        <Link to={`/audit${search}`}>{labelBusinessValue("workspaceView", "AUDIT", locale).label}</Link>
        <Link
          to={`/planning/versions/${encodeURIComponent(query.data.schedule_version_id)}/gantt/factory`}
        >
          {t("route.factoryGantt")}
        </Link>
        <Link
          to={`/planning/versions/${encodeURIComponent(query.data.schedule_version_id)}/gantt/workshops`}
        >
          {t("route.workshopGantt")}
        </Link>
        <Link
          to={`/planning/versions/${encodeURIComponent(query.data.schedule_version_id)}/gantt/machines`}
        >
          {t("route.machineGantt")}
        </Link>
        <Link to={`/resource-load${search}`}>{labelBusinessValue("workspaceView", "RESOURCE_LOAD", locale).label}</Link>
        <Link to={`/compare${search}`}>{labelBusinessValue("workspaceView", "VERSION_COMPARISON", locale).label}</Link>
      </Space>
      <Title level={3}>{t("schedule.humanControls")}</Title>
      {!humanControlsEnabled && (
        <Alert
          type="warning"
          showIcon
          title={t("schedule.controlsHidden")}
          description={t("schedule.controlsHiddenDescription")}
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
