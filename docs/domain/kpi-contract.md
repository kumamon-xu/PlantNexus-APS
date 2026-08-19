---
doc_id: DOC-DOM-005
title: KPI 合同
status: baseline
spec_version: 0.3.0
phase: P0-P3
normative: true
source_sections: [36, 45, 53, 55, 93]
last_reviewed: 2026-08-19
---

# KPI 合同

## Delivery

`on_time_order_ratio`、`total_tardiness_seconds`、`weighted_tardiness`、`late_order_count`。

## Planning

`makespan_seconds`、`scheduled_operation_count`、`unscheduled_operation_count`。

进入 READY_FOR_REVIEW 的计划原则上不得存在未排的 V1 未完成 Operation；若产品状态允许部分结果，必须由后续 ADR 明确，当前不得假设支持。

## Resource

`available_seconds`、`planned_busy_seconds`、`utilization`。

```text
utilization = planned_busy_seconds / available_calendar_time
```

不得以完整自然时间为分母。分母为零时的 API 表示需在 KPI Schema 中明确，不能默认为 0% 或 100%。

## Stability

`changed_operation_count`、`resource_changed_count`、`start_shift_seconds`、`schedule_stability_ratio`。

## Solver

`model_build_time`、`first_feasible_time`、`solve_time`、`objective`、`best_bound`、`relative_gap`、`variables`、`constraints`、`optional_intervals`、`memory_peak`。

所有 duration/time KPI 使用明确单位，报告必须记录 tick、时区、问题 hash、Solver 版本和计算环境。具体业务权重与迟交语义受 OPEN-006 约束。

## P0 Schema skeleton

[`kpi.schema.json`](../../schemas/json/kpi.schema.json) 固定 `kpi_version=kpi.v1`、`problem_hash`、`tick_seconds` 和 Delivery/Planning/Resource/Stability/Solver 五组字段；秒数与计数为非负数，ratio 为 `[0,1]`。`utilization` 允许 `null`，避免在 available time 为零时猜成 0% 或 100%；何时必须为 null 及完整计算校验仍由后续 KPI implementation/contract test 完成。

当前没有 KPI calculator、Solver metrics 或 Benchmark 结果，Schema PASS 不代表这些数值已产生。

## P0 Golden KPI boundary

[`SIM-MINIMAL-001 expected-kpis.json`](../../fixtures/deterministic/SIM-MINIMAL-001/expected-kpis.json) 使用 fixture-local `golden-kpi.v1`，只记录可从人工 Schedule 复算的 Delivery、Planning 和 Resource 子集；它没有 `problem_hash`、Stability 或 Solver metrics，因此故意不冒充 `kpi.v1`。Golden test 从 order/schedule/calendar 重新计算 completion/due/tardiness、`max(end_tick)*tick_seconds` makespan、busy/available/utilization，不信任 expected JSON 自证。

该 fixture 的 synthetic weight 2 与 makespan origin 定义只属于 SIM-ASSUMPTION-009/计算说明，不改变 OBJ/KPI repository-wide 语义或关闭 OPEN-006。正式 KPI calculator、Problem hash、Solver/Stability metrics 和 Benchmark report 仍为后续 Task。
