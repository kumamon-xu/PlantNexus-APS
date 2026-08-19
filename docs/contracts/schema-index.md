---
doc_id: DOC-CONTRACT-008
title: Schema 计划索引
status: living
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [36, 38, 39, 70, 71, 103]
last_reviewed: 2026-08-19
---

# Schema 计划索引

当前 schema set 为 `1.0.0`。`SKELETON_V1` 表示机器可验证的 P0 合同已形成，不表示 Import、Snapshot builder、Problem builder、KPI 计算或 Validator 业务实现已完成。

| Schema | 目标路径 | 首个 Task | 状态 |
|---|---|---|---|
| Canonical import | [`/schemas/json/import-package.schema.json`](../../schemas/json/import-package.schema.json) | TASK-P0-03 skeleton | SKELETON_V1；P1 fields PLANNED |
| PlanningSnapshot | [`/schemas/json/planning-snapshot.schema.json`](../../schemas/json/planning-snapshot.schema.json) | TASK-P0-03 | SKELETON_V1；builder/hash PLANNED |
| PlanningProblem | [`/schemas/json/planning-problem.schema.json`](../../schemas/json/planning-problem.schema.json) | TASK-P0-03 | SKELETON_V1；builder/Solver PLANNED |
| PlanningSolution | `/schemas/json/planning-solution.schema.json` | later P2 | PLANNED |
| KPI | [`/schemas/json/kpi.schema.json`](../../schemas/json/kpi.schema.json) | TASK-P0-03 skeleton | SKELETON_V1；calculation PLANNED |
| ValidationReport | [`/schemas/json/validation-report.schema.json`](../../schemas/json/validation-report.schema.json) | TASK-P0-03 skeleton；TASK-P0-04/07 rules | SKELETON_V1；rule/mutation evidence PLANNED |
| Error | [`/schemas/json/error.schema.json`](../../schemas/json/error.schema.json) | TASK-P0-03 envelope；TASK-P0-04 codes | SKELETON_V1；code registry PLANNED |
| FactoryProfile | `/schemas/scenario/factory-profile.schema.json` | TASK-P0-05 | PLANNED |
| ScenarioSpec | `/schemas/scenario/scenario-spec.schema.json` | TASK-P0-05 | PLANNED |
| Scenario manifest | `/schemas/scenario/scenario-manifest.schema.json` | TASK-P0-05 | PLANNED |

[`/schemas/data_dictionary.yaml`](../../schemas/data_dictionary.yaml) 登记 schema set、字段单位、未知字段/默认值策略和 PROD_OPEN 关联。Scenario/Profile schemas 仍由 TASK-P0-05 建立；不得从本 Task 的 sample 推断它们已经实现。
