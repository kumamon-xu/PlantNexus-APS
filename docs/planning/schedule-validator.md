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

## Mutation Set

至少人工构造并拒绝：machine overlap、wrong resource、wrong duration、wrong precedence、calendar overlap、lock movement、material early start、cross-workshop lag violation、missing operation、duplicate operation。

## 验证顺序建议

先检查结构完整性与引用，再检查 duration/time domain，然后按 Operation/Edge/Resource/Lock/Execution 分类检查。验证结果应尽可能收集多个独立违反，而不是遇到第一条即只返回通用错误。

## 变更门

新增 Constraint 时必须同时更新 Validator 合同、正/反 Fixture、Mutation test、Property test 和 Benchmark 影响，不允许“Solver 先支持、Validator 后补”。
