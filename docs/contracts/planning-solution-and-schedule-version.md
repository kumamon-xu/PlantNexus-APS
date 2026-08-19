---
doc_id: DOC-CONTRACT-005
title: PlanningSolution 与 ScheduleVersion 合同
status: baseline
spec_version: 0.3.0
phase: P0-P3
normative: true
source_sections: [29, 30, 32, 33, 67, 78]
last_reviewed: 2026-08-19
---

# PlanningSolution 与 ScheduleVersion 合同

PlanningSolution 是 SolverBackend 的候选输出，应包含 Solver 状态、operation assignments、objective/bound/gap、diagnostics 和 provenance。它不代表已经验证、批准或发布。

## Operation assignment

每个被排 Operation 至少给出 operation ID、selected resource、start/end tick 和可还原 UTC 时间、duration、lock/execution references。不得只返回展示用 Gantt 坐标。

## 从 Solution 到 Version

```text
PlanningSolution
→ independent validation
→ validation report PASS
→ DRAFT ScheduleVersion
→ READY_FOR_REVIEW
```

如果验证失败，PlanningRun 进入 VALIDATION_FAILED，不得生成可评审版本。

## ScheduleVersion

ScheduleVersion 必须引用 source PlanningRun、Snapshot、Problem、base version（若 Replan）、validation report、KPI、ChangeReport 和 audit。版本内容在 PUBLISHED 后不可变。

只有 APPROVED version 可以发布。所有编辑、拒绝后修订和 Replan 产生新 version ID。

## P0 state contract boundary

[`state-transition.v1`](../../schemas/json/state-transition.schema.json) 只验证 machine/state 名称；[`state-machines.v1`](../../schemas/rules/state-machines.v1.yaml) 与纯状态枚举共同固定允许 pair、终态、guard/evidence 文本。`DRAFT → PUBLISHED` 即使字段名称合法也必须由 transition table 拒绝为 `INVALID_STATE_TRANSITION`。

这些 artifact 不持久化状态、不执行审批/发布、不解决 OPEN-010 权限角色。P3 实现必须保留 ADR-0007 的新版本/不可变语义，并把 actor、reason、audit、idempotency 等 guard evidence 落为真实记录。
