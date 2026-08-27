---
doc_id: DOC-SIM-005
title: Execution Simulator 与异常模型
status: baseline
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [47, 48, 49, 50, 79, 80]
last_reviewed: 2026-08-19
---

# Execution Simulator 与异常模型

## TASK-P4-02 ExecutionSimulationManifest carrier

Manifest v1固定Scenario/Profile/Generator/Simulator版本、seed/named-child derivation、virtual clock、authority/source stream、Policy/Limits、ordered event fingerprints与fact checkpoint；它没有业务state且`production_binding=false`。SIM-ASSUMPTION-016只提供Schema replay vector，本Task不生成事件、不推进时钟、不写事实或触发Replan；P4-09/10仍须实现并证明共同入口与连续场景。

## TASK-P4-01 accepted common-path boundary

ADR-0015已固定virtual clock、named seed derivation、source-position ordering、content-derived event identity、prefix checkpoint/restart和共同入口。Simulator唯一业务输出是ADR-0013的标准ExecutionEvent stream，必须走ledger→fact/new Snapshot→ReplanRequest→Solver→fresh Validator→new DRAFT/ChangeReport；不得直接修改fact/ScheduleVersion或调用私有replan捷径。TASK-P4-02形成carrier，P4-09实现core，P4-10实现连续五类disruption；本Task没有runtime或场景结果。

ExecutionSimulator 输入 PUBLISHED ScheduleVersion，模拟生产时间推进并输出标准 `ExecutionEvent[]`。它不得直接修改计划数据库或调用特殊 Replan 入口。

## 事件

`OPERATION_STARTED`、`OPERATION_COMPLETED`、`OPERATION_DELAYED`、`MACHINE_DOWN`、`MACHINE_RECOVERED`、`MATERIAL_DELAYED`、`URGENT_ORDER_CREATED`、`LOCK_CREATED`、`LOCK_RELEASED`。

## Disruption 配置

设备故障、processing delay、urgent order、material delay等时间/持续量/概率均必须是versioned `SIM_ASSUMPTION`；TASK-P4-01不新增数值。相同base PUBLISHED schedule、Snapshot/Problem、Simulator/Scenario/Profile/Generator versions、virtual clock、policy和seed必须产生byte-identical event stream与相同semantic chain。Host wall clock、线程顺序和runtime timing不进入identity。

Checkpoint只保存run identity、last source position和event-prefix fingerprint，不新增业务state machine。Restart先重新计算prefix；不一致即拒绝。已经合法投影的事实不因Simulator停止/失败被删除。

## 验证

动态重排至少检查：

- completed operation unchanged；
- running resource unchanged；
- HARD_LOCK unchanged；
- changed operation、machine change、time deviation 被记录；
- before/after tardiness 可比较；
- 新 ScheduleVersion Validator PASS。

P4 Gate 需要连续模拟 Urgent Order、Machine Failure、Material Delay、Processing Delay 和 Early Completion，而非仅单事件单元测试。

“连续”要求每一步消费前一步形成的明确Snapshot/Version基线并保留独立Request/Run/DRAFT/ChangeReport；test harness的基线推进必须标记non-Production，不能解释为自动approval/publish。Simulator仅允许Development/Test/Benchmark + SIMULATION + synthetic + `production_binding=false`，Production不注册其route/worker/authority。

TASK-P0-05 的 ScenarioManifest v1 可作为未来 ExecutionSimulator 输入链的 Scenario/Profile/Generator/seed provenance，但当前没有 `simulation/execution/**` 代码、事件概率、event stream 或 fact-preservation test。`failure_frequency` 只是 Scenario contract 维度，不能替代版本化 disruption 配置或关闭 REQ-013；simulator version 与事件 hash 仍为 P4 `PLANNED`。
