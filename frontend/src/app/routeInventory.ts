import type { WorkspaceView } from "../api/types";
import type { TranslationKey } from "../i18n/dictionaries/en-US";

export interface WorkspaceRouteDefinition {
  path: string;
  labelKey?: TranslationKey;
  view?: WorkspaceView;
  scheduleScoped?: boolean;
}

export const workspaceRoutes: readonly WorkspaceRouteDefinition[] = [
  { path: "/planning/data-health", view: "DATA_HEALTH" },
  { path: "/planning/import-runs", view: "IMPORT_RUNS" },
  { path: "/planning/runs", view: "PLANNING_RUNS" },
  { path: "/planning/runs/:planning_run_id", labelKey: "route.planningRunDetail" },
  {
    path: "/planning/versions/:schedule_version_id",
    labelKey: "route.scheduleVersion",
    scheduleScoped: true,
  },
  {
    path: "/planning/versions/:schedule_version_id/orders",
    view: "ORDERS",
    scheduleScoped: true,
  },
  {
    path: "/planning/versions/:schedule_version_id/gantt/factory",
    labelKey: "route.factoryGantt",
    view: "GANTT",
    scheduleScoped: true,
  },
  {
    path: "/planning/versions/:schedule_version_id/gantt/workshops",
    labelKey: "route.workshopGantt",
    view: "GANTT",
    scheduleScoped: true,
  },
  {
    path: "/planning/versions/:schedule_version_id/gantt/machines",
    labelKey: "route.machineGantt",
    view: "GANTT",
    scheduleScoped: true,
  },
  { path: "/operations", view: "OPERATIONS", scheduleScoped: true },
  { path: "/resources", view: "RESOURCES", scheduleScoped: true },
  { path: "/calendars", view: "CALENDARS", scheduleScoped: true },
  { path: "/validation", labelKey: "route.validation", scheduleScoped: true },
  { path: "/kpi", view: "KPI", scheduleScoped: true },
  { path: "/diagnostics", view: "DIAGNOSTICS", scheduleScoped: true },
  { path: "/audit", view: "AUDIT", scheduleScoped: true },
  {
    path: "/resource-load",
    view: "RESOURCE_LOAD",
    scheduleScoped: true,
  },
  {
    path: "/compare",
    view: "VERSION_COMPARISON",
    scheduleScoped: true,
  },
] as const;

export const excludedP313RouteFragments = [
  "replan",
  "execution-events",
  "change-report",
  "production-publish",
] as const;

export const navigationRoutes = workspaceRoutes.filter(
  (route) => !route.path.includes(":"),
);
