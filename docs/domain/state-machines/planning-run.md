---
doc_id: DOC-STATE-001
title: PlanningRun 状态机
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [29, 32, 65]
last_reviewed: 2026-08-19
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
