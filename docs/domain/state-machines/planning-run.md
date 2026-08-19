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
