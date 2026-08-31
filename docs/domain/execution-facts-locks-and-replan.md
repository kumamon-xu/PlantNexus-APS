---
doc_id: DOC-DOM-004
title: 执行事实、锁定与重排边界
status: baseline
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [21, 26, 33, 35, 47, 48, 50, 69, 79]
last_reviewed: 2026-08-31
---

# 执行事实、锁定与重排边界

## TASK-P4-15 independently audited invariants

Exit Audit fresh复核了11种标准ExecutionEvent、source-position ledger、事实prefix/checkpoint、新Snapshot、half-open freeze、COMPLETED/RUNNING/显式HARD/freeze-derived HARD/SOFT优先级、immutable ReplanRequest及PlanningRun attempt归属。两轮连续五场景共10步均保持facts/locks、fresh Validator PASS和complete ChangeReport；tamper、gap、stale、cross-plane、Production与partial-result向量均在写new DRAFT前fail closed。

本结论没有把Simulation event source提升为真实authority，也没有关闭OPEN-005/007或改写事实、锁、Schema、migration、state pair。Replan仍只产生新DRAFT；P5和Production审批/发布/外部执行边界未形成。

## TASK-P4-08 formed replan application

一个ReplanRequest现可在exact current PUBLISHED base、event-derived new Snapshot/Problem、P4-05 effective protections、P4-06 reporting和P4-07 solve均一致时形成新的DRAFT。Application不重新解释event payload，而是读取stored Snapshot并以冻结builder参数重建Problem；facts、explicit/freeze-derived HARD和SOFT evidence全部进入ScheduleVersion/ChangeReport lineage。

COMPLETED/RUNNING保护、freeze半开区间、OBJ-002四元向量与candidate universe仍分别由P4-04～07 owner计算；P4-08只编排并再次验证。Unsupported disruption、stale base、missing provenance、Production authority或任何fresh validation/report失败都不创建Version。P4-09 continuous Simulator仍未启动。

## TASK-P4-05 formed freeze/effective-lock projection

Event-derived new Snapshot、其exact PlanningProblem v2、base PUBLISHED Version和versioned Simulation policy现可确定性投影为独立carrier。权威COMPLETED/RUNNING事实优先级为1，显式HARD为2，freeze-derived HARD为3，SOFT为4；NOT_STARTED且base start落在`[cutoff, freeze_end)`时才产生exact resource/start/end derived lock，start等于freeze end归入outside-freeze。缺失事实authority、stale base、跨plane、grid/horizon不可精确表达或前三层冲突全部fail closed，不调用Solver或推进任何状态。

## TASK-P4-04 formed execution-fact projection

现已形成Simulation-only projector：OPERATION_STARTED/COMPLETED与PROCESSING_REMAINING_CHANGED生成单一effective execution fact并保护COMPLETED终态；MACHINE_UNAVAILABLE/RECOVERED更新resource与calendar interval；MATERIAL_DELAYED/READY更新order及expanded instance readiness；PROCESSING_DURATION_CHANGED更新未完成operation的resource options；LOCK_CREATED/RELEASED维护effective lock与instance lock refs；URGENT_DEMAND_RECEIVED只合并标准Import新增lineage并保留显式priority source。完整prefix顺序、引用、冲突和事实时间均fail closed。

这些事实只形成new Snapshot输入。Freeze/effective HARD projection、SOFT penalty、ReplanRequest、OBJ-002、Solver/Validator、ChangeReport与new DRAFT仍分别属于P4-05～08。


## TASK-P4-01 accepted fact/replan boundary

ADR-0013～0015现已在任何P4 machine carrier或实现前固定：ExecutionEvent是唯一动态事实入口；source position而非received-at决定顺序；ledger接收与fact→new Snapshot→ReplanRequest投影分成两个可重放事务；每个有效事实变化只创建新Snapshot，不改旧事实或Version。ReplanRequest是immutable intent/result lineage且不拥有状态机，attempt继续由PlanningRun承载。

Freeze以new Snapshot cutoff为half-open区间锚；COMPLETED/RUNNING、显式HARD与freeze-derived effective HARD按顺序保护，冲突直接失败。SOFT与旧计划movement只进入Delivery之后的OBJ-002整数向量。P4-04/05/06/07/08仍分别负责行为实现，本Task没有修改事实、锁、Schema、state pair或测试断言；OPEN-005/007及Production event authority继续阻断真实执行。

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

TASK-P4-01进一步固定resolved freeze interval、base content fingerprint、ordered event/fact references、Policy/Limits与request fingerprint必须进入ReplanRequest；new result必须同时绑定fresh Validator与完整ChangeReport。Same input exact replay不重复事实/Snapshot/Request/Version；different fingerprint、gap/late、stale base或cross-plane均fail closed。

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
