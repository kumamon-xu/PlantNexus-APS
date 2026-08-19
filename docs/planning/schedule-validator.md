---
doc_id: DOC-PLAN-005
title: 独立 ScheduleValidator 合同
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [30, 31, 50, 75, 86, 87]
last_reviewed: 2026-08-19
---

# 独立 ScheduleValidator 合同

## 独立性

Validator 必须：

- 不导入 CpSatBackend；
- 不复用 CP-SAT constraint builder；
- 不信任 Solver status；
- 使用 PlanningProblem、candidate schedule 和独立规则判定；
- 检查 C-001～C-011。

可以共享稳定领域类型、时间换算和 Schema parser，但任何会让 Solver 与 Validator 产生同源逻辑缺陷的共享均禁止。

## 输出

```text
validation_passed
hard_violation_count
violations[]:
  constraint_id
  severity
  entity_ids
  observed_value
  expected_rule
  message
```

进入 READY_FOR_REVIEW 必须 `validation_passed=true` 且 `hard_violation_count=0`。

P0 当前机器输出合同为 [`validation-report.v2`](../../schemas/json/validation-report.v2.schema.json)：状态字段使用 `PASS/FAIL`，`hard_violation_count` 为非负整数，violation 只接受 C-001～C-011、`severity=HARD`、非空 entity IDs、observed value、expected rule 和 message。PASS 必须 count=0 且无 violations；FAIL 必须至少一个 hard violation。Emitter/consumer 还必须保证 count 与实际 hard violations 一致，不能依赖 JSON Schema 表达跨数组计数等式。

## Mutation Set

至少人工构造并拒绝：machine overlap、wrong resource、wrong duration、wrong precedence、calendar overlap、lock movement、material early start、cross-workshop lag violation、missing operation、duplicate operation。

## 验证顺序建议

先检查结构完整性与引用，再检查 duration/time domain，然后按 Operation/Edge/Resource/Lock/Execution 分类检查。验证结果应尽可能收集多个独立违反，而不是遇到第一条即只返回通用错误。

## 变更门

新增 Constraint 时必须同时更新 Validator 合同、正/反 Fixture、Mutation test、Property test 和 Benchmark 影响，不允许“Solver 先支持、Validator 后补”。

## P0 implementation boundary

TASK-P0-04 形成 [`constraint-rule-sheet.v1`](../../schemas/rules/constraint-rule-sheet.v1.yaml) 和 completeness CLI。它只检查 C-001～C-018 metadata、code/category/capability/state registry 一致性，并显式扫描 validation contract package 不导入 backend/OR-Tools。它没有 `validate_schedule`、不读取 candidate schedule，也不构成 ADR-0005 的完整 Validator implementation。

TEST-RULE-SHEET-001/TEST-ERROR-MAPPING-001/TEST-CAPABILITY-001/TEST-STATE-TRANSITION-001 是 P0 contract evidence；TEST-VALIDATOR-MUTATION、illegal fixtures、Golden PASS、independent evaluator 和 Property/Benchmark evidence 继续由 TASK-P0-07/P2 负责。
