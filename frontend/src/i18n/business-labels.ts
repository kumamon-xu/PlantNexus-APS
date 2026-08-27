import type {
  ComparisonChangeKind,
  DataPlane,
  ExportJobState,
  RuntimeEnvironment,
  ScheduleState,
  WorkspaceCommandType,
  WorkspaceUiState,
} from "../api/types";
import type { AppLocale, LocalizedMachineValue } from "./types";

type BilingualLabel = Readonly<Record<AppLocale, string>>;

const label = (en: string, zh: string): BilingualLabel => ({
  "en-US": en,
  "zh-CN": zh,
});

export const officialWorkspaceViews = [
  "DATA_HEALTH",
  "IMPORT_RUNS",
  "PLANNING_RUNS",
  "ORDERS",
  "OPERATIONS",
  "RESOURCES",
  "CALENDARS",
  "GANTT",
  "RESOURCE_LOAD",
  "KPI",
  "DIAGNOSTICS",
  "LOCKS",
  "AUDIT",
  "VERSION_COMPARISON",
] as const;

export const officialAllowedActions = [
  "view",
  "edit",
  "lock",
  "approve",
  "reject",
  "publish",
  "export",
  "audit",
] as const;

export const constraintIds = [
  "C-001",
  "C-002",
  "C-003",
  "C-004",
  "C-005",
  "C-006",
  "C-007",
  "C-008",
  "C-009",
  "C-010",
  "C-011",
] as const;

export const businessLabelRegistries = {
  scheduleState: {
    DRAFT: label("Draft", "草稿"),
    READY_FOR_REVIEW: label("Ready for review", "待评审"),
    APPROVED: label("Approved", "已批准"),
    PUBLISHED: label("Published internally", "已内部发布"),
    SUPERSEDED: label("Superseded", "已被取代"),
    REJECTED: label("Rejected", "已驳回"),
  } satisfies Record<ScheduleState, BilingualLabel>,
  exportJobState: {
    CREATED: label("Created", "已创建"),
    EXPORTING: label("Exporting", "导出中"),
    EXPORTED: label("Exported", "已导出"),
    EXPORT_FAILED: label("Export failed", "导出失败"),
    CANCELLED: label("Cancelled", "已取消"),
  } satisfies Record<ExportJobState, BilingualLabel>,
  dataPlane: {
    SIMULATION: label("Simulation", "仿真"),
    PRODUCTION: label("Production", "生产"),
  } satisfies Record<DataPlane, BilingualLabel>,
  environment: {
    DEVELOPMENT: label("Development", "开发"),
    TEST: label("Test", "测试"),
    BENCHMARK: label("Benchmark", "基准测试"),
    PRODUCTION: label("Production", "生产"),
  } satisfies Record<RuntimeEnvironment, BilingualLabel>,
  target: {
    WORKSPACE_INTERNAL: label("Workspace internal", "工作区内部"),
    SIMULATION_INTERNAL: label("Simulation internal", "仿真内部"),
  },
  workspaceView: {
    DATA_HEALTH: label("Data health", "数据健康"),
    IMPORT_RUNS: label("Import runs", "导入运行"),
    PLANNING_RUNS: label("Planning runs", "计划运行"),
    ORDERS: label("Orders", "订单"),
    OPERATIONS: label("Operations", "工序"),
    RESOURCES: label("Resources", "资源"),
    CALENDARS: label("Calendars", "日历"),
    GANTT: label("Gantt", "甘特图"),
    RESOURCE_LOAD: label("Resource load", "资源负荷"),
    KPI: label("KPI", "关键绩效指标"),
    DIAGNOSTICS: label("Diagnostics", "诊断"),
    LOCKS: label("Locks", "锁定"),
    AUDIT: label("Audit", "审计记录"),
    VERSION_COMPARISON: label("Version comparison", "版本对比"),
  } satisfies Record<(typeof officialWorkspaceViews)[number], BilingualLabel>,
  command: {
    MOVE_OPERATION: label("Move operation", "移动工序"),
    ASSIGN_RESOURCE: label("Assign resource", "分配资源"),
    SET_LOCK: label("Set lock", "设置锁定"),
    REMOVE_LOCK: label("Remove lock", "移除锁定"),
    SUBMIT_FOR_REVIEW: label("Submit for review", "提交评审"),
    APPROVE: label("Approve", "批准"),
    REJECT: label("Reject", "驳回"),
    PUBLISH: label("Publish internally", "内部发布"),
    REQUEST_EXPORT: label("Request export", "请求导出"),
    RETRY_EXPORT: label("Retry export", "重试导出"),
    CANCEL_EXPORT: label("Cancel export", "取消导出"),
  } satisfies Record<WorkspaceCommandType, BilingualLabel>,
  allowedAction: {
    view: label("View", "查看"),
    edit: label("Edit", "编辑"),
    lock: label("Lock", "锁定"),
    approve: label("Approve", "批准"),
    reject: label("Reject", "驳回"),
    publish: label("Publish", "发布"),
    export: label("Export", "导出"),
    audit: label("View audit", "查看审计"),
  } satisfies Record<(typeof officialAllowedActions)[number], BilingualLabel>,
  uiState: {
    loading: label("Loading", "加载中"),
    empty: label("No results", "暂无数据"),
    ready: label("Ready", "已就绪"),
    stale: label("Data is stale", "数据已过期"),
    authorization_denied: label("Access denied", "访问被拒绝"),
    contract_error: label("Contract error", "合同错误"),
    server_error: label("Server error", "服务端错误"),
  } satisfies Record<WorkspaceUiState, BilingualLabel>,
  changeKind: {
    ADDED: label("Added", "新增"),
    REMOVED: label("Removed", "移除"),
    RESOURCE_CHANGE: label("Resource changed", "资源变更"),
    DURATION_CHANGE: label("Duration changed", "工时变更"),
    START_SHIFT: label("Start time shifted", "开始时间偏移"),
    UNCHANGED: label("Unchanged", "未变更"),
  } satisfies Record<ComparisonChangeKind, BilingualLabel>,
  constraint: {
    "C-001": label("Assignment completeness", "必排完整性"),
    "C-002": label("Precedence timing", "工艺时间关系"),
    "C-003": label("Candidate resource selection", "候选设备唯一选择"),
    "C-004": label("Unary resource capacity", "单机互斥"),
    "C-005": label("Resource calendar", "设备日历"),
    "C-006": label("Release and material gate", "放行与物料就绪门"),
    "C-007": label("Execution facts", "执行事实保护"),
    "C-008": label("Operation lock", "工序锁定"),
    "C-009": label("Cross-workshop transport", "跨车间衔接"),
    "C-010": label("Duration consistency", "工时一致性"),
    "C-011": label("Planning horizon", "计划时域"),
  } satisfies Record<(typeof constraintIds)[number], BilingualLabel>,
  businessTerm: {
    ScheduleVersion: label("Schedule version", "排程版本"),
    PlanningRun: label("Planning run", "计划运行"),
    ExportJob: label("Export job", "导出任务"),
    weighted_tardiness: label("Weighted tardiness", "加权延期"),
    makespan_seconds: label("Makespan", "总工期"),
    late_order_count: label("Late orders", "延期订单数"),
    scheduled_operation_count: label("Scheduled operations", "已排工序数"),
    utilization: label("Utilization", "利用率"),
    PASS: label("Pass", "通过"),
    FAIL: label("Fail", "失败"),
    HARD: label("Hard violation", "硬约束违反"),
    SOFT: label("Soft observation", "软约束观察"),
    AuditEvent: label("Audit event", "审计事件"),
    PublicationResult: label("Publication result", "发布结果"),
    artifact_manifest: label("Artifact manifest", "成果清单"),
    "idempotent replay": label("Idempotent replay", "幂等重放"),
  },
} as const;

export type BusinessLabelNamespace = keyof typeof businessLabelRegistries;

export function labelBusinessValue(
  namespace: BusinessLabelNamespace,
  raw: string,
  locale: AppLocale,
): LocalizedMachineValue {
  const registry = businessLabelRegistries[namespace] as Readonly<
    Record<string, BilingualLabel>
  >;
  const entry = registry[raw];
  if (entry === undefined) {
    return {
      known: false,
      label: locale === "zh-CN" ? `未知（${raw}）` : `Unknown (${raw})`,
      raw,
    };
  }
  return { known: true, label: entry[locale], raw };
}
