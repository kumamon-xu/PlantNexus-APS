import { Layout, Menu, Tag, Typography } from "antd";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { navigationRoutes } from "./routeInventory";
import { PlanningRunPage } from "../pages/PlanningRunPage";
import { ScheduleVersionPage } from "../pages/ScheduleVersionPage";
import { ValidationPage } from "../pages/ValidationPage";
import { WorkspaceCollectionPage } from "../pages/WorkspaceCollectionPage";
import { WorkspaceStatePanel } from "../components/WorkspaceStatePanel";

const { Content, Header, Sider } = Layout;
const { Text, Title } = Typography;

export function PlanningWorkspaceApp() {
  const navigate = useNavigate();
  const location = useLocation();
  const selected = navigationRoutes.find((route) => route.path === location.pathname);
  return (
    <Layout className="app-shell">
      <Header className="app-header">
        <div>
          <Title level={4}>PlantNexus APS</Title>
          <Text>Planning Workspace</Text>
        </div>
        <Tag color="green">read-only · server authority</Tag>
      </Header>
      <Layout>
        <Sider width={232} breakpoint="lg" collapsedWidth="0" className="app-sider">
          <nav aria-label="Planning Workspace read-only navigation">
            <Menu
              mode="inline"
              selectedKeys={selected === undefined ? [] : [selected.path]}
              items={navigationRoutes.map((route) => ({
                key: route.path,
                label: route.label,
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
              element={<WorkspaceCollectionPage title="Data health" view="DATA_HEALTH" />}
            />
            <Route
              path="/planning/import-runs"
              element={<WorkspaceCollectionPage title="Import runs" view="IMPORT_RUNS" />}
            />
            <Route
              path="/planning/runs"
              element={<WorkspaceCollectionPage title="Planning runs" view="PLANNING_RUNS" />}
            />
            <Route path="/planning/runs/:planning_run_id" element={<PlanningRunPage />} />
            <Route
              path="/planning/versions/:schedule_version_id"
              element={<ScheduleVersionPage />}
            />
            <Route
              path="/planning/versions/:schedule_version_id/orders"
              element={
                <WorkspaceCollectionPage title="Orders" view="ORDERS" scheduleScoped />
              }
            />
            <Route
              path="/operations"
              element={
                <WorkspaceCollectionPage
                  title="Operations"
                  view="OPERATIONS"
                  scheduleScoped
                />
              }
            />
            <Route
              path="/resources"
              element={
                <WorkspaceCollectionPage
                  title="Resources"
                  view="RESOURCES"
                  scheduleScoped
                />
              }
            />
            <Route
              path="/calendars"
              element={
                <WorkspaceCollectionPage
                  title="Calendars"
                  view="CALENDARS"
                  scheduleScoped
                />
              }
            />
            <Route path="/validation" element={<ValidationPage />} />
            <Route
              path="/kpi"
              element={<WorkspaceCollectionPage title="KPI" view="KPI" scheduleScoped />}
            />
            <Route
              path="/diagnostics"
              element={
                <WorkspaceCollectionPage
                  title="Diagnostics"
                  view="DIAGNOSTICS"
                  scheduleScoped
                />
              }
            />
            <Route
              path="/audit"
              element={<WorkspaceCollectionPage title="Audit" view="AUDIT" scheduleScoped />}
            />
            <Route
              path="*"
              element={
                <WorkspaceStatePanel
                  state="contract_error"
                  detail="This route is outside the P3-11 read-only inventory."
                />
              }
            />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}
