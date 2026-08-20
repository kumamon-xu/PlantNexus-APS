---
doc_id: DOC-CONTRACT-008
title: Schema 计划索引
status: living
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [36, 38, 39, 70, 71, 103]
last_reviewed: 2026-08-20
---

# Schema 计划索引

当前 schema set 为additive `2.3.0`。`CONTRACT_V1/V2/V3`表示机器可验证的合同已形成，不表示Solver、KPI计算、ScheduleValidator、状态持久化或业务动作已完成。`1.0.0/1.1.0/1.2.0/2.0.0/2.1.0/2.2.0` artifact均保留，未被原地覆盖。

| Schema | 目标路径 | 首个 Task | 状态 |
|---|---|---|---|
| Canonical records | [`/schemas/json/canonical-records.v1.schema.json`](../../schemas/json/canonical-records.v1.schema.json) | TASK-P1-02 | CONTRACT_V1；Normalization/Data Validation/Expansion formed |
| Canonical import v1 | [`/schemas/json/import-package.schema.json`](../../schemas/json/import-package.schema.json) | TASK-P0-03 skeleton | SKELETON_V1 retained |
| Canonical import v2 | [`/schemas/json/import-package.v2.schema.json`](../../schemas/json/import-package.v2.schema.json) | TASK-P1-02 | CONTRACT_V2；Reference/Synthetic common-ingress pipeline formed；Production binding PLANNED |
| Unit conversion registry | [`/schemas/rules/unit-conversion-registry.v1.yaml`](../../schemas/rules/unit-conversion-registry.v1.yaml) | TASK-P1-05 | RULE_V1；explicit integer duration conversion formed，Production default forbidden |
| PlanningSnapshot v1 | [`/schemas/json/planning-snapshot.schema.json`](../../schemas/json/planning-snapshot.schema.json) | TASK-P0-03 | SKELETON_V1 retained |
| PlanningSnapshot v2 | [`/schemas/json/planning-snapshot.v2.schema.json`](../../schemas/json/planning-snapshot.v2.schema.json) | TASK-P1-02 | CONTRACT_V2；builder/hash/insert-only persistence formed |
| PlanningProblem v1 | [`/schemas/json/planning-problem.schema.json`](../../schemas/json/planning-problem.schema.json) | TASK-P0-03；TASK-P1-09 | CONTRACT_V1；default builder/hash/fixed replay preserved，Solver PLANNED |
| PlanningProblem v2 | [`/schemas/json/planning-problem.v2.schema.json`](../../schemas/json/planning-problem.v2.schema.json) | TASK-P2-01 | CONTRACT_V2；opt-in builder/hash、due/priority/resource/lock/historical-anchor input formed，Solver/Validator PLANNED |
| PlanningSolution | `/schemas/json/planning-solution.schema.json` | later P2 | PLANNED |
| KPI | [`/schemas/json/kpi.schema.json`](../../schemas/json/kpi.schema.json) | TASK-P0-03 skeleton | SKELETON_V1；calculation PLANNED |
| ValidationReport v1 | [`/schemas/json/validation-report.schema.json`](../../schemas/json/validation-report.schema.json) | TASK-P0-03 | SKELETON_V1 retained |
| ValidationReport v2 | [`/schemas/json/validation-report.v2.schema.json`](../../schemas/json/validation-report.v2.schema.json) | TASK-P0-04 rules；TASK-P0-07 mutations | SKELETON_V2 + C-ID shape formed；schedule evaluation PLANNED |
| Error v1 | [`/schemas/json/error.schema.json`](../../schemas/json/error.schema.json) | TASK-P0-03 | SKELETON_V1 retained |
| Error v2 | [`/schemas/json/error.v2.schema.json`](../../schemas/json/error.v2.schema.json) | TASK-P0-04 | SKELETON_V2 + code/category registry formed |
| Error v3 | [`/schemas/json/error.v3.schema.json`](../../schemas/json/error.v3.schema.json) | TASK-P1-06 | CONTRACT_V3；rich deterministic Data Validation detail formed |
| ImportQualityReport v1 | [`/schemas/json/import-quality-report.schema.json`](../../schemas/json/import-quality-report.schema.json) | TASK-P1-06 | CONTRACT_V1 + deterministic evaluator/sample + Snapshot handoff formed |
| StateTransition | [`/schemas/json/state-transition.schema.json`](../../schemas/json/state-transition.schema.json) | TASK-P0-04 | SKELETON_V1；machine/state names formed，business persistence PLANNED |
| Constraint Rule Sheet | [`/schemas/rules/constraint-rule-sheet.v1.yaml`](../../schemas/rules/constraint-rule-sheet.v1.yaml) | TASK-P0-04 | C-001～C-018 machine contract + fixture-local evaluator/mutations formed；P2 integration PLANNED |
| Capability/Error/State registries | [`/schemas/rules/`](../../schemas/rules/) | TASK-P0-04；TASK-P1-06 error v2 | versioned registry contracts formed；error v2 additive，capability implementation claims remain false |
| FactoryProfile | [`/schemas/scenario/factory-profile.schema.json`](../../schemas/scenario/factory-profile.schema.json) | TASK-P0-05 | SKELETON_V1；versioned P1 synthetic generator asset formed；Production distribution PLANNED |
| ScenarioSpec | [`/schemas/scenario/scenario-spec.schema.json`](../../schemas/scenario/scenario-spec.schema.json) | TASK-P0-05 | SKELETON_V1；P0 fixture与`SIM-P1-INGRESS-001` formed；broader Scenario library PLANNED |
| Scenario manifest | [`/schemas/scenario/scenario-manifest.schema.json`](../../schemas/scenario/scenario-manifest.schema.json) | TASK-P0-05 | SKELETON_V1 + empty Import replay formed；run/export audit PLANNED |

[`/schemas/data_dictionary.yaml`](../../schemas/data_dictionary.yaml) 登记 schema set、canonical collections、版本/provenance、未知字段/默认值策略、兼容边界和 PROD_OPEN/SIM_ASSUMPTION 关联。Set-level `2.3.0`只新增Problem v2合同；Import/Snapshot v2 JSON document继续固定`2.0.0`、unit registry v1固定`2.1.0`、quality合同固定`2.2.0`且历史artifact hash不变。Problem v2 sample证明contract replay，不是Solver/Validator/Benchmark或Production证据。

TASK-P2-01新增Problem v2 Schema/sample并将global set提升到`2.3.0`；v1 Schema/sample SHA-256仍为`41b01f...e943`/`aa31fb...4093`，Import/Snapshot/quality/unit document版本不改。PlanningSolution、Solver、Validator、Benchmark和Production合同继续`PLANNED`。
