---
doc_id: DOC-DOM-004
title: 执行事实、锁定与重排边界
status: baseline
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [21, 26, 33, 35, 47, 48, 50, 69, 79]
last_reviewed: 2026-08-24
---

# 执行事实、锁定与重排边界

## TASK-P3-17 phase boundary

P3只审计既有execution fact/hard lock作为P2输入以及workspace lock command的copy-on-write行为；没有接入新ExecutionEvent、事实覆盖、freeze window、dynamic replan或ChangeReport。P4仍需新的明确phase transition与Task规划。

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

## TASK-P2-01 Problem v2 fact and lock boundary

v2 builder把COMPLETED→active precedence前驱解析成HistoricalCompletionAnchor：保存operation/fact/resource、actual start/end和source三元组，并要求completion不晚于Snapshot cutoff。COMPLETED→COMPLETED edge排除；active→COMPLETED说明事实状态与routing order冲突，按`INVALID_HISTORICAL_FACT`在Solver前拒绝。

active OperationInstance引用的lock只要`end_at_utc`严格晚于cutoff/horizon start即完整进入Problem；刚好结束或更早的lock为expired并排除。Builder不按horizon end裁剪或丢弃未来lock，且保留`HARD_LOCK`/`SOFT_LOCK`和source。该合同只让后续C-008输入可表达：HARD enforcement属于P2-07，SOFT cost/OBJ-002仍明确排除，Replan/P4状态不启动。

## TASK-P2-07 Solver preservation boundary

COMPLETED继续不进入future assignment；其historical anchor仍可约束active successor。RUNNING保留actual start在Problem identity中，固定assigned resource，并把完整ceiled remainder从horizon start作为future occupancy；不得重选资源、按option duration重算、裁剪或移动该区间。

HARD lock精确固定resource/start/end。若HARD interval不在tick grid、与权威duration不一致、多个HARD互相冲突或与RUNNING tuple冲突，输入在model build前以稳定MODEL_INVALID拒绝；与calendar、其他固定占用或horizon的合法冲突由CP-SAT认证INFEASIBLE。SOFT lock只回写metadata reference，不形成hard constraint、hint或稳定性成本。

本Task不产生ExecutionEvent、ReplanRequest、freeze window、ChangeReport或ScheduleVersion变更；OBJ-002和P4仍未启动。Production fact/lock authority及freeze policy继续由OPEN-005/007约束。

## P3 lock boundary

P3-06只允许针对既有计划内容提交human edit/lock command，经server validation与formal Validator后产生新DRAFT；它不能消费新的ExecutionEvent、移动RUNNING/HARD事实、应用freeze window、计算OBJ-002或生成ChangeReport。上述动态事实保护继续属于P4，OPEN-005/007不因P3锁UI关闭。

TASK-P3-01已把`SET_LOCK/RELEASE_LOCK`固定为versioned、copy-on-write command：必须引用同一ScheduleVersion/Problem lineage，保留COMPLETED/RUNNING事实与HARD tuple，fresh Validator PASS后才可形成成功新DRAFT。该lock是P3 plan-version control，不是P4 freeze/stability/replan；不存在ExecutionEvent ingest、SOFT stability cost、OBJ-002或ChangeReport实现。

## TASK-P3-06 formed lock behavior

机器合同与实现统一使用`SET_LOCK/REMOVE_LOCK`。SET HARD只接受与当前assignment完全相同的resource/start/end；MOVE/ASSIGN若破坏任一Version HARD lock即拒绝；Problem中原有`HARD_LOCK`不能被REMOVE。SOFT lock只作为version-local metadata，可带null resource/time且不进入formal hard constraint。SET/REMOVE都更新assignment的stable lock IDs并创建`LOCK_CHANGE` DRAFT，不改Problem、Snapshot、RUNNING/COMPLETED事实或source Version。

Fresh Validator仍只按immutable Problem重算C-001～C-011，version-local lock的引用/shape/HARD tuple由server semantic guard补充；二者均通过才可提交DRAFT，显式review submit还必须再次fresh PASS且lineage fingerprint一致。该行为没有freeze window、ExecutionEvent ingest、stability objective、ReplanRequest或ChangeReport，OPEN-005/007保持OPEN。
