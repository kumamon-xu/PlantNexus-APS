import type { WorkspaceView } from "../api/types";

export interface WorkspaceRouteDefinition {
  path: string;
  label: string;
  view?: WorkspaceView;
  scheduleScoped?: boolean;
}

export const workspaceRoutes: readonly WorkspaceRouteDefinition[] = [
  { path: "/planning/data-health", label: "Data health", view: "DATA_HEALTH" },
  { path: "/planning/import-runs", label: "Import runs", view: "IMPORT_RUNS" },
  { path: "/planning/runs", label: "Planning runs", view: "PLANNING_RUNS" },
  { path: "/planning/runs/:planning_run_id", label: "Planning run detail" },
  {
    path: "/planning/versions/:schedule_version_id",
    label: "ScheduleVersion",
    scheduleScoped: true,
  },
  {
    path: "/planning/versions/:schedule_version_id/orders",
    label: "Orders",
    view: "ORDERS",
    scheduleScoped: true,
  },
  {
    path: "/planning/versions/:schedule_version_id/gantt/factory",
    label: "Factory Gantt",
    view: "GANTT",
    scheduleScoped: true,
  },
  {
    path: "/planning/versions/:schedule_version_id/gantt/workshops",
    label: "Workshop Gantt",
    view: "GANTT",
    scheduleScoped: true,
  },
  {
    path: "/planning/versions/:schedule_version_id/gantt/machines",
    label: "Machine Gantt",
    view: "GANTT",
    scheduleScoped: true,
  },
  { path: "/operations", label: "Operations", view: "OPERATIONS", scheduleScoped: true },
  { path: "/resources", label: "Resources", view: "RESOURCES", scheduleScoped: true },
  { path: "/calendars", label: "Calendars", view: "CALENDARS", scheduleScoped: true },
  { path: "/validation", label: "Validation", scheduleScoped: true },
  { path: "/kpi", label: "KPI", view: "KPI", scheduleScoped: true },
  { path: "/diagnostics", label: "Diagnostics", view: "DIAGNOSTICS", scheduleScoped: true },
  { path: "/audit", label: "Audit", view: "AUDIT", scheduleScoped: true },
  {
    path: "/resource-load",
    label: "Resource Load",
    view: "RESOURCE_LOAD",
    scheduleScoped: true,
  },
  {
    path: "/compare",
    label: "Version comparison",
    view: "VERSION_COMPARISON",
    scheduleScoped: true,
  },
] as const;

export const excludedP312RouteFragments = [
  "commands",
  "approve",
  "reject",
  "publish",
  "export",
  "locks",
] as const;

export const navigationRoutes = workspaceRoutes.filter(
  (route) => !route.path.includes(":"),
);
