---
doc_id: DOC-STATE-002
title: ScheduleVersion 状态机
status: baseline
spec_version: 0.3.0
phase: P0-P3
normative: true
source_sections: [30, 33, 35, 66, 69, 78]
last_reviewed: 2026-08-19
---

# ScheduleVersion 状态机

```text
DRAFT
→ READY_FOR_REVIEW
→ APPROVED
→ PUBLISHED
→ SUPERSEDED

READY_FOR_REVIEW
→ REJECTED
→（通过新 Planning/Editing command 产生新 DRAFT Version）
```

## 转移门

| 转移 | 必须满足 |
|---|---|
| DRAFT → READY_FOR_REVIEW | 独立 Validator PASS，硬违反数为 0，provenance 完整 |
| READY_FOR_REVIEW → APPROVED | 有权限的人工作出审批并记录 audit |
| READY_FOR_REVIEW → REJECTED | 记录 actor、reason；原版本保留 |
| APPROVED → PUBLISHED | 发布操作幂等、目标明确、没有 synthetic/production 混用 |
| PUBLISHED → SUPERSEDED | 新版本已成为当前生产参考；旧版本仍不可变 |

## 不变量

- DRAFT 和 REJECTED 不可发布；仅 APPROVED 可发布。
- PUBLISHED Version 不可修改或删除。
- Reject、Gantt 编辑、Replan 都产生新版本，不复用旧 ID。
- 发布重试不能 double publish。
- “Rollback”只表示选择历史版本作为新计划的参考输入；不得直接把历史 PUBLISHED 行改回当前。

## P0 versioned transition table

允许 pair 仅为：

| From | To | Guard/evidence boundary |
|---|---|---|
| DRAFT | READY_FOR_REVIEW | independent validation PASS、hard count 0、provenance 完整 |
| READY_FOR_REVIEW | APPROVED | authorized human actor/decision/audit；角色仍受 OPEN-010 约束 |
| READY_FOR_REVIEW | REJECTED | actor/reason/audit；修订必须产生新 DRAFT version |
| APPROVED | PUBLISHED | idempotent、target 明确、Production/Synthetic 安全 |
| PUBLISHED | SUPERSEDED | 新版本成为当前生产参考，旧版本仍不可变 |

`SUPERSEDED` 与 `REJECTED` 为终态；REJECTED 没有回到 DRAFT 的同实体转移。任何 `DRAFT → PUBLISHED`、PUBLISHED 修改或 REJECTED 复用均返回 `INVALID_STATE_TRANSITION`。

[`state-transition.v1`](../../../schemas/json/state-transition.schema.json) 只验证 machine/state 名称，[`state-machines.v1`](../../../schemas/rules/state-machines.v1.yaml) 和纯状态合同授权 pair。TEST-STATE-TRANSITION-001 不替代 P3 权限、audit、immutability、publish/idempotency tests。

## TASK-P0-08 generic idempotency review

process-local `InMemoryIdempotencyStore` 只固定“同 scope/key + 同 request hash 返回原 logical ID；不同 hash 冲突”的工程原语，不注册 Publish/Export task，也不授权 `APPROVED → PUBLISHED`。ScheduleVersion pair、guard、权限、不可变与发布副作用全部未实现且未改变；business publish idempotency 继续 `PLANNED`。
