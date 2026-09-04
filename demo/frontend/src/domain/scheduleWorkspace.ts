import type {
  DemoFactoryView,
  DemoScheduleView,
  FactoryResource,
  FactoryWorkshop,
  ScheduleAssignment,
  ScheduleOrder,
  SchedulePresentationQuery,
  ScheduleQueryInput,
} from "../api/types";

const HOUR_MS = 3_600_000;
const DAY_MS = 86_400_000;

export const priorityLabels = {
  NORMAL: "普通",
  KEY: "重点",
  URGENT: "加急",
} as const;

export const protectionLabels = {
  FREE: "正常计划",
  RUNNING: "正在加工",
  HARD_LOCK: "硬锁定",
  SOFT_LOCK: "软锁定",
} as const;

export const operationStateLabels = {
  NOT_STARTED: "待加工",
  RUNNING: "正在加工",
} as const;

export interface LocatedResource {
  readonly resource: FactoryResource;
  readonly workshop: FactoryWorkshop;
}

export function factoryResources(factory: DemoFactoryView): readonly LocatedResource[] {
  return factory.factory.workshops.flatMap((workshop) =>
    workshop.production_line.resource_groups.flatMap((group) =>
      group.resources.map((resource) => ({ resource, workshop })),
    ),
  );
}

export interface OrderFilters {
  readonly search: string;
  readonly priority: "ALL" | ScheduleOrder["priority_class"];
  readonly risk: "ALL" | "LATE" | "RUNNING";
}

export function filterAndSortOrders(
  orders: readonly ScheduleOrder[],
  filters: OrderFilters,
): readonly ScheduleOrder[] {
  const search = filters.search.trim().toLocaleLowerCase("zh-CN");
  return orders
    .filter((order) => {
      if (
        search.length > 0 &&
        !`${order.order_code} ${order.product_code}`
          .toLocaleLowerCase("zh-CN")
          .includes(search)
      ) {
        return false;
      }
      if (filters.priority !== "ALL" && order.priority_class !== filters.priority) {
        return false;
      }
      if (filters.risk === "LATE" && order.on_time) return false;
      if (filters.risk === "RUNNING" && order.running_operation_count === 0) {
        return false;
      }
      return true;
    })
    .sort(
      (left, right) =>
        Number(left.on_time) - Number(right.on_time) ||
        right.tardiness_seconds - left.tardiness_seconds ||
        right.priority_weight - left.priority_weight ||
        Date.parse(left.due_at.utc) - Date.parse(right.due_at.utc) ||
        left.order_code.localeCompare(right.order_code),
    );
}

export interface TimelineWindow {
  readonly startMs: number;
  readonly endMs: number;
}

export function timelineWindow(
  schedule: DemoScheduleView,
  factory: DemoFactoryView,
): TimelineWindow {
  const startMs = schedule.query.start_at_utc
    ? Date.parse(schedule.query.start_at_utc)
    : Date.parse(factory.horizon_start.utc);
  const endMs = schedule.query.end_at_utc
    ? Date.parse(schedule.query.end_at_utc)
    : Date.parse(factory.horizon_end.utc);
  return { startMs, endMs };
}

export interface BarGeometry {
  readonly leftPercent: number;
  readonly widthPercent: number;
}

export function barGeometry(
  start: string,
  end: string,
  window: TimelineWindow,
): BarGeometry | null {
  const startMs = Math.max(Date.parse(start), window.startMs);
  const endMs = Math.min(Date.parse(end), window.endMs);
  if (endMs <= startMs || window.endMs <= window.startMs) return null;
  const span = window.endMs - window.startMs;
  return {
    leftPercent: ((startMs - window.startMs) / span) * 100,
    widthPercent: Math.max(((endMs - startMs) / span) * 100, 0.18),
  };
}

export function timelineTicks(
  window: TimelineWindow,
  count = 7,
): readonly { readonly value: number; readonly leftPercent: number }[] {
  if (count < 2) return [{ value: window.startMs, leftPercent: 0 }];
  return Array.from({ length: count }, (_, index) => ({
    value:
      window.startMs +
      ((window.endMs - window.startMs) * index) / (count - 1),
    leftPercent: (index / (count - 1)) * 100,
  }));
}

export function shiftedWindowQuery(
  query: SchedulePresentationQuery,
  factory: DemoFactoryView,
  direction: -1 | 1,
): ScheduleQueryInput {
  const lowerBound = Date.parse(factory.horizon_start.utc) - 6 * HOUR_MS;
  const upperBound = Date.parse(factory.horizon_end.utc);
  const currentStart = query.start_at_utc
    ? Date.parse(query.start_at_utc)
    : Date.parse(factory.horizon_start.utc);
  const currentEnd = query.end_at_utc
    ? Date.parse(query.end_at_utc)
    : Math.min(currentStart + 72 * HOUR_MS, upperBound);
  const duration = currentEnd - currentStart;
  let nextStart = currentStart + direction * duration;
  nextStart = Math.max(lowerBound, Math.min(nextStart, upperBound - duration));
  const nextEnd = Math.min(nextStart + duration, upperBound);
  return {
    ...query,
    start_at_utc: new Date(nextStart).toISOString(),
    end_at_utc: new Date(nextEnd).toISOString(),
    offset: 0,
  };
}

export function fullHorizonQuery(
  query: SchedulePresentationQuery,
): ScheduleQueryInput {
  return {
    ...query,
    start_at_utc: null,
    end_at_utc: null,
    offset: 0,
  };
}

export function queryWithFilters(
  query: SchedulePresentationQuery,
  patch: ScheduleQueryInput,
): ScheduleQueryInput {
  return { ...query, ...patch, offset: patch.offset ?? 0 };
}

export function assignmentsByResource(
  assignments: readonly ScheduleAssignment[],
): ReadonlyMap<string, readonly ScheduleAssignment[]> {
  const grouped = new Map<string, ScheduleAssignment[]>();
  for (const assignment of assignments) {
    const current = grouped.get(assignment.resource_id) ?? [];
    current.push(assignment);
    grouped.set(assignment.resource_id, current);
  }
  return grouped;
}

export function formatWorkspaceTime(value: string | number): string {
  const parsed = typeof value === "number" ? new Date(value) : new Date(value);
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parsed);
}

export function formatWorkspaceDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    weekday: "short",
  }).format(new Date(value));
}

export function formatDurationSeconds(seconds: number): string {
  if (seconds < 3_600) return `${Math.round(seconds / 60)} 分钟`;
  if (seconds < DAY_MS / 1_000) {
    const hours = seconds / 3_600;
    return `${hours.toFixed(Number.isInteger(hours) ? 0 : 1)} 小时`;
  }
  return `${(seconds / 86_400).toFixed(1)} 天`;
}

export function formatHours(seconds: number): string {
  return `${(seconds / 3_600).toFixed(1)} 小时`;
}

export function quantityUnitLabel(value: string): string {
  const labels: Readonly<Record<string, string>> = {
    piece: "件",
    pieces: "件",
    kg: "千克",
    set: "套",
  };
  return labels[value.toLocaleLowerCase("en-US")] ?? "单位";
}
