import { DemoClientError } from "../api/client";
import { DemoContractError } from "../api/contracts";
import type { JobStatus, ScheduleState, StoryState } from "../api/types";

export const storyCopy: Record<StoryState, { label: string; detail: string }> = {
  EMPTY: {
    label: "等待初始化",
    detail: "演示数据尚未建立，先初始化固定种子的精密机加工工厂。",
  },
  INITIALIZED: {
    label: "工厂已初始化",
    detail: "行业数据已经通过标准导入和校验，可以开始自动排产。",
  },
  INITIAL_PLAN_RUNNING: {
    label: "正在自动排产",
    detail: "系统正在执行真实求解与独立校验，请关注当前阶段和耗时。",
  },
  READY_FOR_REVIEW: {
    label: "排程待确认",
    detail: "初始排程已通过独立校验，需要显式设为仿真基线。",
  },
  BASELINE_PUBLISHED: {
    label: "仿真基线已发布",
    detail: "当前版本已成为仿真内部基线，可以进入加急重排演示。",
  },
  REPLAN_RUNNING: {
    label: "正在加急重排",
    detail: "系统正在保留已执行和冻结任务的前提下重排剩余工序。",
  },
  DRAFT_COMPARISON_READY: {
    label: "新方案待比较",
    detail: "新的草稿排程已经通过校验，但不会替换当前仿真基线。",
  },
};

export const scheduleStateLabels: Record<ScheduleState, string> = {
  DRAFT: "草稿",
  READY_FOR_REVIEW: "待确认",
  APPROVED: "已批准，待完成发布",
  PUBLISHED: "已发布",
  SUPERSEDED: "已被替代",
  REJECTED: "已拒绝",
};

export const jobStatusLabels: Record<JobStatus, string> = {
  QUEUED: "等待执行",
  RUNNING: "执行中",
  SUCCEEDED: "已完成",
  FAILED: "执行失败",
  INTERRUPTED: "服务重启后已中断",
  CANCELLING: "正在取消",
  CANCELLED: "已取消",
};

export const jobKindLabels = {
  RESET: "初始化演示工厂",
  INITIAL_PLAN: "自动排产",
  URGENT_REPLAN: "加急订单重排",
} as const;

const stageLabels: Readonly<Record<string, string>> = {
  MIGRATING: "建立独立仿真数据库",
  GENERATING: "生成固定场景数据",
  STAGING: "写入标准导入暂存区",
  PERSISTING_IMPORT: "保存规范导入结果",
  SELF_CHECKING: "执行数据完整性自检",
  SWITCHING_ACTIVE_RUN: "切换当前演示运行",
  PERSISTING_SNAPSHOT: "保存不可变快照与排产问题",
  SOLVING: "求解排程",
  VERIFYING_SOLUTION: "独立校验排程",
  PERSISTING_VERSION: "保存待确认排程版本",
  PREPARING_IMPORT: "准备加急订单事实",
  IMPORTING_URGENT_DEMAND: "导入加急订单",
  APPENDING_EVENT: "记录加急需求事件",
  PROJECTING_FACTS: "投影执行事实与锁定",
  CREATING_REQUEST: "创建重排请求",
  COMMITTING_RESULT: "提交重排结果",
  BUILDING_PRESENTATION: "生成版本比较证据",
  COMPLETE: "完成",
};

export function stageLabel(stage: string | null): string {
  if (stage === null) return "正在准备";
  return stageLabels[stage] ?? "执行后台阶段";
}

export function solverCopy(status: "OPTIMAL" | "FEASIBLE") {
  return status === "OPTIMAL"
    ? {
        label: "已证明最优",
        detail: "在当前模型、合成数据和求解参数下已证明最优。",
      }
    : {
        label: "已找到并验证可行",
        detail: "尚未证明最优；该结果已通过独立校验。",
      };
}

export interface UiNotice {
  readonly title: string;
  readonly detail: string;
  readonly correlationId: string | null;
}

const errorMessages: Readonly<Record<string, { title: string; detail: string }>> = {
  NETWORK_ERROR: {
    title: "暂时无法连接演示服务",
    detail: "请确认本地演示后端已启动，然后重新连接。现有服务端状态不会被改变。",
  },
  AUTHORIZATION_DENIED: {
    title: "本地仿真会话无效",
    detail: "请重新建立会话。页面不会请求或显示任何访问令牌。",
  },
  DEMO_NOT_INITIALIZED: {
    title: "演示工厂尚未初始化",
    detail: "请先初始化固定场景，再执行后续操作。",
  },
  ACTIVE_JOB_CONFLICT: {
    title: "已有任务正在执行",
    detail: "请等待当前任务结束，页面会自动恢复最新状态。",
  },
  STALE_RUN: {
    title: "页面中的运行版本已过期",
    detail: "当前演示运行已经变化，请刷新状态后再操作。",
  },
  STALE_BASE_VERSION: {
    title: "仿真基线已经变化",
    detail: "请重新读取当前已发布基线后再确认操作。",
  },
  IDEMPOTENCY_CONFLICT: {
    title: "重复操作的输入不一致",
    detail: "系统已阻止复用同一操作身份提交不同内容。",
  },
  BASELINE_STATE_CONFLICT: {
    title: "当前版本状态不允许此操作",
    detail: "请刷新页面，依据服务端最新版本状态继续。",
  },
  SOLVER_NO_CANDIDATE: {
    title: "达到求解限制，未找到可接受排程",
    detail: "这不能说明问题不可行；原有版本和仿真基线均保持不变。",
  },
  SOLVER_INFEASIBLE: {
    title: "当前问题已证明不可行",
    detail: "原有版本和仿真基线保持不变，请查看技术证据。",
  },
  SOLUTION_VALIDATION_FAILED: {
    title: "排程校验失败",
    detail: "系统已阻止创建或切换版本，请查看技术证据。",
  },
  JOB_EXECUTION_FAILED: {
    title: "后台任务执行失败",
    detail: "错误已被安全记录；不会显示内部异常，也不会自动重复提交命令。",
  },
  PROCESS_INTERRUPTED: {
    title: "服务重启中断了后台任务",
    detail: "系统已明确标记本次任务为中断，没有伪装成成功。请重新执行当前步骤，原幂等身份会被安全复用。",
  },
  RESET_FAILED: {
    title: "初始化未完成",
    detail: "旧的活动运行未被替换，可以检查证据后重新开始。",
  },
  PERSISTENCE_FAILED: {
    title: "演示数据暂时不可读取",
    detail: "服务端已安全停止当前操作，未返回部分可信结果。",
  },
};

export function noticeFor(error: unknown): UiNotice {
  if (error instanceof DemoContractError) {
    return {
      title: "服务响应契约不匹配",
      detail: "页面已停止使用该响应，避免展示不完整或不可信的信息。",
      correlationId: null,
    };
  }
  if (error instanceof DemoClientError) {
    const copy = errorMessages[error.code] ?? {
      title: "操作未能完成",
      detail: "服务端已安全拒绝或停止操作，请刷新状态并查看技术证据。",
    };
    return { ...copy, correlationId: error.correlationId };
  }
  return {
    title: "页面暂时无法继续",
    detail: "本地界面遇到未预期情况，服务端已有状态不会被改变。",
    correlationId: null,
  };
}

const numberFormatter = new Intl.NumberFormat("zh-CN");
const percentFormatter = new Intl.NumberFormat("zh-CN", {
  style: "percent",
  maximumFractionDigits: 1,
});

export function formatNumber(value: number): string {
  return numberFormatter.format(value);
}

export function formatRatio(value: number | null): string {
  return value === null ? "不适用" : percentFormatter.format(value);
}

export function formatSeconds(value: number | null): string {
  if (value === null) return "—";
  if (value < 60) return `${value.toFixed(value < 10 ? 1 : 0)} 秒`;
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return `${minutes} 分 ${seconds} 秒`;
}

export function formatLongDuration(value: number): string {
  const seconds = Math.abs(Math.round(value));
  if (seconds < 60) return `${seconds} 秒`;
  const totalMinutes = Math.round(seconds / 60);
  if (totalMinutes < 60) return `${totalMinutes} 分钟`;
  const totalHours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (totalHours < 24) {
    return `${totalHours} 小时${minutes === 0 ? "" : ` ${minutes} 分钟`}`;
  }
  const days = Math.floor(totalHours / 24);
  const hours = totalHours % 24;
  return `${days} 天${hours === 0 ? "" : ` ${hours} 小时`}${minutes === 0 ? "" : ` ${minutes} 分钟`}`;
}

export function formatLocalTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return "时间不可用";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parsed);
}

export function shortId(value: string | null | undefined): string {
  if (!value) return "尚未建立";
  if (value.length <= 18) return value;
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
}

export function horizonDays(start: string, end: string): number {
  const milliseconds = new Date(end).valueOf() - new Date(start).valueOf();
  return Math.max(0, Math.round(milliseconds / 86_400_000));
}
