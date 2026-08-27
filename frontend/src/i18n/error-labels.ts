import type { AppLocale, LocalizedMachineValue } from "./types";

type BilingualLabel = Readonly<Record<AppLocale, string>>;
const label = (en: string, zh: string): BilingualLabel => ({
  "en-US": en,
  "zh-CN": zh,
});

export const productErrorCategories = [
  "DATA_ERROR",
  "UNSUPPORTED_CAPABILITY",
  "MODEL_INVALID",
  "INFEASIBLE",
  "NO_SOLUTION_WITHIN_LIMIT",
  "VALIDATION_FAILED",
  "SYSTEM_ERROR",
] as const;

export const productErrorCodes = [
  "INVALID_TIME",
  "DUPLICATE_ID",
  "MISSING_SCENARIO_ID",
  "SYNTHETIC_REFERENCE_IN_PRODUCTION",
  "INVALID_ENTITY_COUNT",
  "INVALID_DURATION",
  "INVALID_TIME_RANGE",
  "MISSING_RUNNING_FACT",
  "INVALID_REFERENCE",
  "INVALID_LAG_RANGE",
  "INVALID_CAPABILITY_DECLARATION",
  "DUPLICATE_CAPABILITY",
  "INVALID_STATE_TRANSITION",
  "ROUTE_CYCLE",
  "MISSING_RESOURCE",
  "UNIT_CONVERSION_ERROR",
  "MISSING_DURATION",
  "UNSUPPORTED_CAPABILITY",
  "MODEL_INVALID",
  "INFEASIBLE",
  "NO_SOLUTION_WITHIN_LIMIT",
  "SCHEDULE_VALIDATION_FAILED",
  "SYSTEM_ERROR",
] as const;

export const workspaceControlReasons = [
  "AUTHORIZATION_DENIED",
  "UNAUTHORIZED",
  "PRODUCTION_AUTHORITY_UNAVAILABLE",
  "SOURCE_NOT_FOUND",
  "SOURCE_MISSING",
  "PUBLICATION_NOT_FOUND",
  "PREVIOUS_CURRENT_NOT_FOUND",
  "NOT_FOUND",
  "STALE_SOURCE",
  "STALE_VERSION",
  "STALE_CURSOR",
  "STATE_CONFLICT",
  "INVALID_STATE_TRANSITION",
  "CURRENT_REFERENCE_CONFLICT",
  "LEASE_CONFLICT",
  "LOCK_CONFLICT",
  "IMMUTABLE_EXECUTION_FACT",
  "NO_OP",
  "IDEMPOTENCY_CONFLICT",
  "INVALID_REQUEST",
  "INVALID_COMMAND",
  "INVALID_QUERY",
  "INVALID_INPUT",
  "INVALID_REFERENCE",
  "INVALID_TIME",
  "DATA_PLANE_MISMATCH",
  "MIXED_LINEAGE",
  "KPI_MISMATCH",
  "PLANNING_RUN_NOT_COMPLETED",
  "VALIDATION_FAILED",
  "PERSISTENCE_FAILED",
  "EXPORT_FAILED",
  "SERVICE_UNAVAILABLE",
  "SYSTEM_ERROR",
] as const;

export const authorizationDetailReasons = [
  "AUTHENTICATION_REQUIRED",
  "INVALID_AUTHENTICATION",
  "CAPABILITY_DENIED",
  "RESOURCE_SCOPE_DENIED",
  "AUTHORIZATION_PROVIDER_UNAVAILABLE",
  "INVALID_PROVIDER_CONTEXT",
  "SIMULATION_API_DISABLED",
] as const;

export const errorLabelRegistries = {
  productCategory: {
    DATA_ERROR: label("Data error", "数据错误"),
    UNSUPPORTED_CAPABILITY: label("Unsupported capability", "不支持的能力"),
    MODEL_INVALID: label("Invalid model", "模型无效"),
    INFEASIBLE: label("Infeasible", "已证明不可行"),
    NO_SOLUTION_WITHIN_LIMIT: label("No conclusion within limit", "限时内未得出结论"),
    VALIDATION_FAILED: label("Validation failed", "校验失败"),
    SYSTEM_ERROR: label("System error", "系统错误"),
  } satisfies Record<(typeof productErrorCategories)[number], BilingualLabel>,
  productCode: {
    INVALID_TIME: label("Invalid time", "时间值无效"),
    DUPLICATE_ID: label("Duplicate ID", "标识重复"),
    MISSING_SCENARIO_ID: label("Missing scenario ID", "缺少场景标识"),
    SYNTHETIC_REFERENCE_IN_PRODUCTION: label("Synthetic reference in Production", "生产数据中包含仿真引用"),
    INVALID_ENTITY_COUNT: label("Invalid entity count", "实体数量无效"),
    INVALID_DURATION: label("Invalid duration", "工时无效"),
    INVALID_TIME_RANGE: label("Invalid time range", "时间范围无效"),
    MISSING_RUNNING_FACT: label("Missing running fact", "缺少运行事实"),
    INVALID_REFERENCE: label("Invalid reference", "引用无效"),
    INVALID_LAG_RANGE: label("Invalid lag range", "时间间隔范围无效"),
    INVALID_CAPABILITY_DECLARATION: label("Invalid capability declaration", "能力声明无效"),
    DUPLICATE_CAPABILITY: label("Duplicate capability", "能力声明重复"),
    INVALID_STATE_TRANSITION: label("Invalid state transition", "状态转换无效"),
    ROUTE_CYCLE: label("Routing cycle", "工艺路线存在环"),
    MISSING_RESOURCE: label("Missing eligible resource", "缺少可用资源"),
    UNIT_CONVERSION_ERROR: label("Unit conversion error", "单位换算错误"),
    MISSING_DURATION: label("Missing duration", "缺少工时"),
    UNSUPPORTED_CAPABILITY: label("Unsupported capability", "不支持的能力"),
    MODEL_INVALID: label("Invalid model", "模型无效"),
    INFEASIBLE: label("Infeasible", "已证明不可行"),
    NO_SOLUTION_WITHIN_LIMIT: label("No conclusion within limit", "限时内未得出结论"),
    SCHEDULE_VALIDATION_FAILED: label("Schedule validation failed", "排程校验失败"),
    SYSTEM_ERROR: label("System error", "系统错误"),
  } satisfies Record<(typeof productErrorCodes)[number], BilingualLabel>,
  workspaceReason: {
    AUTHORIZATION_DENIED: label("Authorization denied", "授权被拒绝"),
    UNAUTHORIZED: label("Unauthorized", "未获授权"),
    PRODUCTION_AUTHORITY_UNAVAILABLE: label("Production authority unavailable", "生产授权不可用"),
    SOURCE_NOT_FOUND: label("Source not found", "未找到来源"),
    SOURCE_MISSING: label("Source missing", "缺少来源"),
    PUBLICATION_NOT_FOUND: label("Publication not found", "未找到发布记录"),
    PREVIOUS_CURRENT_NOT_FOUND: label("Previous current version not found", "未找到先前当前版本"),
    NOT_FOUND: label("Not found", "未找到"),
    STALE_SOURCE: label("Source is stale", "来源已过期"),
    STALE_VERSION: label("Version is stale", "版本已过期"),
    STALE_CURSOR: label("Cursor is stale", "游标已过期"),
    STATE_CONFLICT: label("State conflict", "状态冲突"),
    INVALID_STATE_TRANSITION: label("Invalid state transition", "状态转换无效"),
    CURRENT_REFERENCE_CONFLICT: label("Current reference conflict", "当前版本引用冲突"),
    LEASE_CONFLICT: label("Lease conflict", "租约冲突"),
    LOCK_CONFLICT: label("Lock conflict", "锁定冲突"),
    IMMUTABLE_EXECUTION_FACT: label("Immutable execution fact", "执行事实不可变"),
    NO_OP: label("No effective change", "没有有效变更"),
    IDEMPOTENCY_CONFLICT: label("Idempotency conflict", "幂等请求冲突"),
    INVALID_REQUEST: label("Invalid request", "请求无效"),
    INVALID_COMMAND: label("Invalid command", "命令无效"),
    INVALID_QUERY: label("Invalid query", "查询无效"),
    INVALID_INPUT: label("Invalid input", "输入无效"),
    INVALID_REFERENCE: label("Invalid reference", "引用无效"),
    INVALID_TIME: label("Invalid time", "时间值无效"),
    DATA_PLANE_MISMATCH: label("Data-plane mismatch", "数据平面不匹配"),
    MIXED_LINEAGE: label("Mixed lineage", "血缘混用"),
    KPI_MISMATCH: label("KPI mismatch", "KPI不一致"),
    PLANNING_RUN_NOT_COMPLETED: label("Planning run is not complete", "计划运行尚未完成"),
    VALIDATION_FAILED: label("Validation failed", "校验失败"),
    PERSISTENCE_FAILED: label("Persistence failed", "持久化失败"),
    EXPORT_FAILED: label("Export failed", "导出失败"),
    SERVICE_UNAVAILABLE: label("Service unavailable", "服务暂不可用"),
    SYSTEM_ERROR: label("System error", "系统错误"),
  } satisfies Record<(typeof workspaceControlReasons)[number], BilingualLabel>,
  authorizationDetail: {
    AUTHENTICATION_REQUIRED: label("Authentication required", "需要身份认证"),
    INVALID_AUTHENTICATION: label("Invalid authentication", "身份认证无效"),
    CAPABILITY_DENIED: label("Capability denied", "能力权限被拒绝"),
    RESOURCE_SCOPE_DENIED: label("Resource scope denied", "资源范围权限被拒绝"),
    AUTHORIZATION_PROVIDER_UNAVAILABLE: label("Authorization provider unavailable", "授权服务不可用"),
    INVALID_PROVIDER_CONTEXT: label("Invalid provider context", "授权上下文无效"),
    SIMULATION_API_DISABLED: label("Simulation API disabled", "仿真API未启用"),
  } satisfies Record<(typeof authorizationDetailReasons)[number], BilingualLabel>,
} as const;

export type ErrorLabelNamespace = keyof typeof errorLabelRegistries;

export function labelErrorValue(
  namespace: ErrorLabelNamespace,
  raw: string,
  locale: AppLocale,
): LocalizedMachineValue {
  const registry = errorLabelRegistries[namespace] as Readonly<
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

export interface ErrorEnvelopeDisplayInput {
  readonly namespace: "PRODUCT" | "WORKSPACE_CONTROL" | "AUTHORIZATION";
  readonly category?: string | null;
  readonly code?: string | null;
  readonly reason?: string | null;
  readonly detailReason?: string | null;
  readonly correlationId?: string | null;
  readonly safeMessage?: string | null;
}

export interface LocalizedErrorDisplay {
  readonly primary: LocalizedMachineValue;
  readonly qualifiers: readonly LocalizedMachineValue[];
  readonly correlationId: string | null;
  readonly safeMessage: string | null;
}

export function localizeErrorEnvelope(
  input: ErrorEnvelopeDisplayInput,
  locale: AppLocale,
): LocalizedErrorDisplay {
  const qualifiers: LocalizedMachineValue[] = [];
  let primary: LocalizedMachineValue;
  if (input.namespace === "PRODUCT") {
    primary = labelErrorValue("productCode", input.code ?? "MISSING_CODE", locale);
    if (input.category !== null && input.category !== undefined) {
      qualifiers.push(labelErrorValue("productCategory", input.category, locale));
    }
  } else if (input.namespace === "AUTHORIZATION") {
    primary = labelErrorValue(
      "authorizationDetail",
      input.detailReason ?? input.reason ?? "MISSING_REASON",
      locale,
    );
  } else {
    primary = labelErrorValue("workspaceReason", input.reason ?? "MISSING_REASON", locale);
    if (input.detailReason !== null && input.detailReason !== undefined) {
      qualifiers.push(labelErrorValue("authorizationDetail", input.detailReason, locale));
    }
  }
  return {
    primary,
    qualifiers,
    correlationId: input.correlationId ?? null,
    safeMessage: input.safeMessage ?? null,
  };
}
