---
doc_id: DOC-STATE-001
title: PlanningRun 状态机
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [29, 32, 65]
last_reviewed: 2026-08-24
---

# PlanningRun 状态机

PlanningRun 只描述计算生命周期，不承载批准、发布或版本替代语义。

```text
CREATED
→ INGESTING
→ VALIDATING
→ SNAPSHOTTED
→ BUILDING
→ SOLVING
→ SOLVED
→ VERIFYING
→ COMPLETED
```

## 终止/失败状态

`DATA_REJECTED`、`MODEL_INVALID`、`INFEASIBLE`、`NO_SOLUTION_WITHIN_LIMIT`、`VALIDATION_FAILED`、`CANCELLED`、`FAILED`。

| 终止状态 | 允许来源示例 | 必需证据 |
|---|---|---|
| DATA_REJECTED | INGESTING/VALIDATING | import quality report |
| MODEL_INVALID | BUILDING/SOLVING | model diagnostics、版本信息 |
| INFEASIBLE | SOLVING | 已认证 Solver 状态与诊断 |
| NO_SOLUTION_WITHIN_LIMIT | SOLVING | limits、UNKNOWN 状态、耗时 |
| VALIDATION_FAILED | VERIFYING | independent validation report |
| CANCELLED | 非终止运行状态 | cancel actor/reason/audit |
| FAILED | 任意系统执行状态 | structured error、attempt、trace |

## 不变量

- `APPROVED`、`PUBLISHED`、`SUPERSEDED` 不得出现在 PlanningRun。
- 状态转移持久化必须幂等并有时间戳/audit。
- Worker 失联应通过任务可靠性机制标记 `STALLED`；`STALLED` 是 Job 运行诊断，不得假装 PlanningRun 已完成。
- `COMPLETED` 只说明计算与验证完成，不说明计划已批准或发布。

## P0 versioned transition table

[`state-machines.v1`](../../../schemas/rules/state-machines.v1.yaml) 固定以下允许目标；表外 pair 统一拒绝为 `INVALID_STATE_TRANSITION`。同一幂等事件重放由持久化层识别，不通过 self-transition 表示。

| From | Allowed to |
|---|---|
| CREATED | INGESTING、CANCELLED、FAILED |
| INGESTING | VALIDATING、DATA_REJECTED、CANCELLED、FAILED |
| VALIDATING | SNAPSHOTTED、DATA_REJECTED、CANCELLED、FAILED |
| SNAPSHOTTED | BUILDING、CANCELLED、FAILED |
| BUILDING | SOLVING、MODEL_INVALID、CANCELLED、FAILED |
| SOLVING | SOLVED、MODEL_INVALID、INFEASIBLE、NO_SOLUTION_WITHIN_LIMIT、CANCELLED、FAILED |
| SOLVED | VERIFYING、CANCELLED、FAILED |
| VERIFYING | COMPLETED、VALIDATION_FAILED、CANCELLED、FAILED |

`COMPLETED`、`DATA_REJECTED`、`MODEL_INVALID`、`INFEASIBLE`、`NO_SOLUTION_WITHIN_LIMIT`、`VALIDATION_FAILED`、`CANCELLED`、`FAILED` 均为终态且无 outgoing pair。`SOLVING → SOLVED` 只接受 OPTIMAL/FEASIBLE candidate；UNKNOWN 只能进入 NO_SOLUTION_WITHIN_LIMIT。`VERIFYING → COMPLETED` 的 guard 是独立 `validation-report.v2` PASS 且 hard count 为 0。

`state-transition.v1` JSON Schema 验证 machine/state 名称；纯 transition table 与 TEST-STATE-TRANSITION-001 才授权 pair。本 Task 不持久化 PlanningRun，也不实现 Worker cancellation 或 Solver status ingestion。

## TASK-P0-08 generic worker review

`jobs/contracts.py` 的 `QUEUED/RUNNING/STALLED/SUCCEEDED/FAILED` 是通用执行诊断，不是 PlanningRun 状态扩展。lease 到期只把 Job 标成 STALLED；不得把 PlanningRun 推到 COMPLETED、FAILED、INFEASIBLE 或其他业务状态。P0-08 没有 PlanningRun persistence/task、Solver status 或 cancellation，因此 `state-machines.v1`、27 states/42 transitions 与 TEST-STATE-TRANSITION-001 均保持不变。

## TASK-P2-02 status outcome contract

Pure mapping把OPTIMAL/FEASIBLE送往`SOLVED`，INFEASIBLE送往`INFEASIBLE`，UNKNOWN送往`NO_SOLUTION_WITHIN_LIMIT`，MODEL_INVALID送往`MODEL_INVALID`，CANCELLED送往`CANCELLED`，FAILED送往`FAILED`。该映射与`state-machines.v1`现有状态一致，没有增加state或transition；候选存在性与product error同时机器校验。

本Task不执行`SOLVING → ...` transition、不持久化PlanningRun，也不实现cancel actor/reason或failure audit。`CONTRACT_SAMPLE`中的UNKNOWN只是映射样例，不能证明真实limits耗尽；后继Worker/Backend仍须把真实status和evidence写入持久化transition guard。

## TASK-P2-11 reporting review

KPI v2与internal manifest只引用既有`planning_run_id`，并要求该ID与真实SolverReport完全一致；它们不创建、claim、完成或重试PlanningRun。`generated_at_utc`取同一SolverReport的finished time，只是immutable provenance，不是状态转移时间写入。PlanningRun state registry、repository、worker lease/heartbeat和failure audit均未修改。

## P3 planning allocation

P3只消费已经完成且candidate通过formal Validator的PlanningRun/Solution；创建ScheduleVersion不得改变PlanningRun状态或重试Solver。P3-04负责消费边界，P3-14/15验证lineage和无反向状态副作用；本次不增加PlanningRun pair、repository或worker行为。

## TASK-P3-01 contract review

Workspace合同确认PlanningRun只承担计算生命周期：`COMPLETED`不能授权approve/publish/export，也不等于ScheduleVersion存在。P3 query可只读展示PlanningRun/Solution/Validation lineage；任何manual command只针对ScheduleVersion并产生新DRAFT，不反向改变PlanningRun或重跑Solver。本Task未修改`state-machines.v1`、pure state contract、repository或worker，P3行为仍为`PLANNED`。
## TASK-P3-02 separation review

新增P3 Schema没有修改PlanningRun的16个state、31个allowed pair或terminal集合。`schedule-version.v1.lineage.planning_run_id`只引用已完成的validated P2 run；Workspace command、approval、publication与ExportJob不得重新解释Solver status或推进PlanningRun。Solver `UNKNOWN`继续终止为`NO_SOLUTION_WITHIN_LIMIT`且不能创建Version。

## TASK-P3-03 persistence separation

`0004`没有新增PlanningRun table、state或pair。ScheduleVersion repository只保存已由上游提供的lineage引用，不查询、推进或补写PlanningRun；Publication/Export storage也不能把`COMPLETED`解释为approve/publish/export授权。P3-04+的application仍必须在自己的启动门消费fresh validated solution；本Task的8/8 machine report只证明持久化边界。
