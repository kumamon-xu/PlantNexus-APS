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

当前 schema set 为 `1.2.0`。`SKELETON_V1/V2` 表示机器可验证的 P0 合同已形成，不表示 Import、Snapshot/Problem builder、KPI 计算、ScheduleValidator、状态持久化、Scenario fixture 或业务动作已完成。`1.0.0/1.1.0` artifact 均保留，未被原地覆盖。

| Schema | 目标路径 | 首个 Task | 状态 |
|---|---|---|---|
| Canonical import | [`/schemas/json/import-package.schema.json`](../../schemas/json/import-package.schema.json) | TASK-P0-03 skeleton | SKELETON_V1；P1 fields PLANNED |
| PlanningSnapshot | [`/schemas/json/planning-snapshot.schema.json`](../../schemas/json/planning-snapshot.schema.json) | TASK-P0-03 | SKELETON_V1；builder/hash PLANNED |
| PlanningProblem | [`/schemas/json/planning-problem.schema.json`](../../schemas/json/planning-problem.schema.json) | TASK-P0-03 | SKELETON_V1；builder/Solver PLANNED |
| PlanningSolution | `/schemas/json/planning-solution.schema.json` | later P2 | PLANNED |
| KPI | [`/schemas/json/kpi.schema.json`](../../schemas/json/kpi.schema.json) | TASK-P0-03 skeleton | SKELETON_V1；calculation PLANNED |
| ValidationReport v1 | [`/schemas/json/validation-report.schema.json`](../../schemas/json/validation-report.schema.json) | TASK-P0-03 | SKELETON_V1 retained |
| ValidationReport v2 | [`/schemas/json/validation-report.v2.schema.json`](../../schemas/json/validation-report.v2.schema.json) | TASK-P0-04 rules；TASK-P0-07 mutations | SKELETON_V2 + C-ID shape formed；schedule evaluation PLANNED |
| Error v1 | [`/schemas/json/error.schema.json`](../../schemas/json/error.schema.json) | TASK-P0-03 | SKELETON_V1 retained |
| Error v2 | [`/schemas/json/error.v2.schema.json`](../../schemas/json/error.v2.schema.json) | TASK-P0-04 | SKELETON_V2 + code/category registry formed |
| StateTransition | [`/schemas/json/state-transition.schema.json`](../../schemas/json/state-transition.schema.json) | TASK-P0-04 | SKELETON_V1；machine/state names formed，business persistence PLANNED |
| Constraint Rule Sheet | [`/schemas/rules/constraint-rule-sheet.v1.yaml`](../../schemas/rules/constraint-rule-sheet.v1.yaml) | TASK-P0-04 | C-001～C-018 machine contract formed；evaluator/mutation PLANNED |
| Capability/Error/State registries | [`/schemas/rules/`](../../schemas/rules/) | TASK-P0-04 | versioned registry contracts formed；implementation claims false |
| FactoryProfile | [`/schemas/scenario/factory-profile.schema.json`](../../schemas/scenario/factory-profile.schema.json) | TASK-P0-05 | SKELETON_V1；synthetic distribution generation PLANNED |
| ScenarioSpec | [`/schemas/scenario/scenario-spec.schema.json`](../../schemas/scenario/scenario-spec.schema.json) | TASK-P0-05 | SKELETON_V1；formal Scenario library/Fixture PLANNED |
| Scenario manifest | [`/schemas/scenario/scenario-manifest.schema.json`](../../schemas/scenario/scenario-manifest.schema.json) | TASK-P0-05 | SKELETON_V1 + empty Import replay formed；run/export audit PLANNED |

[`/schemas/data_dictionary.yaml`](../../schemas/data_dictionary.yaml) 登记 schema set、字段单位、未知字段/默认值策略、兼容边界和 PROD_OPEN/SIM_ASSUMPTION 关联。三份 `.synthetic.json` 是 Schema samples，不是 TASK-P0-06 的 `SIM-MINIMAL-001`；不得从 manifest、empty package 或 rule registry 推断 Import pipeline、Scenario Fixture、Validator、Benchmark 或 Solver 已实现。
