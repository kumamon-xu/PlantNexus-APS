import { Layout, Menu, Select, Space, Tag, Typography } from "antd";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { navigationRoutes } from "./routeInventory";
import { PlanningRunPage } from "../pages/PlanningRunPage";
import { ScheduleVersionPage } from "../pages/ScheduleVersionPage";
import { ValidationPage } from "../pages/ValidationPage";
import { WorkspaceCollectionPage } from "../pages/WorkspaceCollectionPage";
import { WorkspaceStatePanel } from "../components/WorkspaceStatePanel";
import { GanttPage } from "../features/gantt/GanttPage";
import { ResourceLoadPage } from "../features/resource-load/ResourceLoadPage";
import { ReplanningWorkspacePage } from "../features/replanning/ReplanningWorkspacePage";
import { VersionComparisonPage } from "../features/version-comparison/VersionComparisonPage";
import { useAppServices } from "./context";
import { labelBusinessValue } from "../i18n/business-labels";
import { useLocale } from "../i18n/locale";
import type { AppLocale } from "../i18n/types";

const { Content, Header, Sider } = Layout;
const { Text, Title } = Typography;

export function PlanningWorkspaceApp() {
  const navigate = useNavigate();
  const location = useLocation();
  const { runtime } = useAppServices();
  const { locale, setLocale, t } = useLocale();
  const selected = navigationRoutes.find((route) => route.path === location.pathname);
  const routeLabel = (route: (typeof navigationRoutes)[number]) =>
    route.labelKey === undefined
      ? labelBusinessValue("workspaceView", route.view ?? route.path, locale).label
      : t(route.labelKey);
  return (
    <Layout className="app-shell" data-locale={locale}>
      <Header className="app-header">
        <div>
          <Title level={4}>PlantNexus APS</Title>
          <Text>{t("app.workspace")}</Text>
        </div>
        <Space wrap>
          <label className="locale-control">
            <span>{t("locale.label")}</span>
            <Select<AppLocale>
              aria-label={t("locale.label")}
              value={locale}
              onChange={setLocale}
              options={[
                { value: "zh-CN", label: t("locale.zhCN") },
                { value: "en-US", label: t("locale.enUS") },
              ]}
            />
          </label>
          <Tag color={runtime.dataPlane === "SIMULATION" ? "gold" : "green"}>
            {runtime.dataPlane === "SIMULATION"
              ? t("app.simulationBadge")
              : t("app.productionBadge")}
          </Tag>
        </Space>
      </Header>
      <Layout>
        <Sider width={232} breakpoint="lg" collapsedWidth="0" className="app-sider">
          <nav aria-label={t("app.navigation")}>
            <Menu
              mode="inline"
              selectedKeys={selected === undefined ? [] : [selected.path]}
              items={navigationRoutes.map((route) => ({
                key: route.path,
                label: routeLabel(route),
              }))}
              onClick={({ key }) => void navigate(key)}
            />
          </nav>
        </Sider>
        <Content className="app-content" id="main-content">
          <Routes>
            <Route path="/" element={<Navigate to="/planning/data-health" replace />} />
            <Route
              path="/planning/data-health"
              element={<WorkspaceCollectionPage view="DATA_HEALTH" />}
            />
            <Route
              path="/planning/import-runs"
              element={<WorkspaceCollectionPage view="IMPORT_RUNS" />}
            />
            <Route
              path="/planning/runs"
              element={<WorkspaceCollectionPage view="PLANNING_RUNS" />}
            />
            <Route path="/planning/runs/:planning_run_id" element={<PlanningRunPage />} />
            <Route
              path="/planning/versions/:schedule_version_id"
              element={<ScheduleVersionPage />}
            />
            <Route
              path="/planning/versions/:schedule_version_id/orders"
              element={
                <WorkspaceCollectionPage view="ORDERS" scheduleScoped />
              }
            />
            <Route
              path="/planning/versions/:schedule_version_id/gantt/factory"
              element={<GanttPage grouping="factory" />}
            />
            <Route
              path="/planning/versions/:schedule_version_id/gantt/workshops"
              element={<GanttPage grouping="workshop" />}
            />
            <Route
              path="/planning/versions/:schedule_version_id/gantt/machines"
              element={<GanttPage grouping="machine" />}
            />
            <Route
              path="/operations"
              element={
                <WorkspaceCollectionPage
                  view="OPERATIONS"
                  scheduleScoped
                />
              }
            />
            <Route
              path="/resources"
              element={
                <WorkspaceCollectionPage
                  view="RESOURCES"
                  scheduleScoped
                />
              }
            />
            <Route
              path="/calendars"
              element={
                <WorkspaceCollectionPage
                  view="CALENDARS"
                  scheduleScoped
                />
              }
            />
            <Route path="/validation" element={<ValidationPage />} />
            <Route
              path="/kpi"
              element={<WorkspaceCollectionPage view="KPI" scheduleScoped />}
            />
            <Route
              path="/diagnostics"
              element={
                <WorkspaceCollectionPage
                  view="DIAGNOSTICS"
                  scheduleScoped
                />
              }
            />
            <Route
              path="/audit"
              element={<WorkspaceCollectionPage view="AUDIT" scheduleScoped />}
            />
            <Route path="/resource-load" element={<ResourceLoadPage />} />
            <Route path="/compare" element={<VersionComparisonPage />} />
            <Route path="/planning/replanning" element={<ReplanningWorkspacePage />} />
            <Route
              path="*"
              element={
                <WorkspaceStatePanel
                  state="contract_error"
                  detail={t("app.routeOutside")}
                />
              }
            />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}
