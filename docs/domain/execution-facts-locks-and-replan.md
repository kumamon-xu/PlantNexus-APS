---
doc_id: DOC-DOM-004
title: 执行事实、锁定与重排边界
status: baseline
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [21, 26, 33, 35, 47, 48, 50, 69, 79]
last_reviewed: 2026-08-19
---

# 执行事实、锁定与重排边界

## 执行状态

COMPLETED Operation 不进入未来排程，其 actual facts 保留。RUNNING Operation 必须保留：

```text
actual_start_at
resource_id
remaining_quantity
remaining_seconds
```

RUNNING 的未来占用从 `horizon_start` 表达，资源固定；Validator 独立检查资源未变化、remaining duration 和 future occupancy 正确。

## Lock

- HARD_LOCK：resource、start、end 全部固定，是硬约束。
- SOFT_LOCK：允许变化，但通过 OBJ-002 Stability 产生变化成本。
- Hint：只改善搜索，不是约束；不能用 Hint 宣称锁定被保护。

## Replan 输入与输出

```text
base_schedule_version_id
new_snapshot_id
replan_reason
freeze_window
→ new ScheduleVersion + ChangeReport
```

Replan 必须保留 completed/running facts 和 HARD_LOCK，对 SOFT_LOCK 计价，并比较交期与稳定性。旧 ScheduleVersion 不修改、不覆盖。

## UI 编辑

拖拽操作必须转成 UI Command，经服务端验证后产生新 DRAFT，再由 Validator 检查。任何 `UPDATE published_schedule` 路径均禁止。

## TASK-P1-07 execution-fact projection

Order Expansion按`production_lot_id + routing_operation_id`查找唯一current ExecutionFact：无fact为NOT_STARTED；RUNNING/COMPLETED逐字保留status并写入`execution_fact_id`，不把实际历史时刻改写成未来排程时刻。COMPLETED OperationInstance继续存在于expansion/Snapshot事实层，未来PlanningProblem是否排除由TASK-P1-09单独实现和测试。

OperationLock同样只按lot/operation lineage附加稳定排序的`lock_ids`；跨RoutingVersion的fact/lock或同一实例多个fact明确拒绝，不做自动选择/修复。实际start/resource/remaining quantity/seconds仍保留在canonical ExecutionFact中，由引用回链；本Task不实现Replan、freeze policy、lock目标或ScheduleValidator。
