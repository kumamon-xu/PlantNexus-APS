---
doc_id: DOC-SIM-002
title: ScenarioSpec 与 Provenance
status: baseline
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [39, 40, 44, 46, 49, 104]
last_reviewed: 2026-08-19
---

# ScenarioSpec 与 Provenance

ScenarioSpec 描述一次可完全重放的计划实验：引用 FactoryProfile，给出 seed、能力要求、复杂度、事件和预期行为。

```yaml
scenario_id: SIM-FJSP-BOTTLENECK-001
scenario_version: 1.0.0
factory_profile: machine_shop_medium
seed: 12345
required_capabilities:
  - DAG_ROUTING
  - ALTERNATIVE_RESOURCE
  - MACHINE_CALENDAR
complexity:
  bottleneck_level: high
  due_date_pressure: high
  cross_workshop_ratio: 0.20
expected_behavior:
  result: [FEASIBLE, OPTIMAL]
```

## Provenance

所有 Synthetic 数据记录 `scenario_id/version`、seed、factory profile/version、generator version、generated_at 和 dataset hash。`generated_at` 不参与 canonical dataset hash。

## 期望行为

Expected behavior 可以是允许的 Solver/Product 状态集合、Validator 结果、已知约束、范围型 KPI 或 `UNSUPPORTED_CAPABILITY`。除 Golden Fixture 外，不应固定完整 Gantt 顺序。

## 修改

能力、复杂度、事件、预期行为或引用 Profile 变化时更新 Scenario version。运行时临时覆盖必须进入显式 run manifest，不能产生无法重放的隐式配置。

## v1 machine contracts

[`scenario-spec.v1`](../../schemas/scenario/scenario-spec.schema.json) 强制 `synthetic_only=true`，显式引用 Profile ID/version 与 Generator ID/version，并要求 seed、capability declaration、11 个复杂度维度和非空 expected results。Schema 可表达未支持 capability；生成 context 必须通过 registry precheck，并以 `UNSUPPORTED_CAPABILITY` 显式拒绝，不能静默删除声明。

[`scenario-manifest.v1`](../../schemas/scenario/scenario-manifest.schema.json) 强制 `synthetic=true`，目标只允许 Development/Test/Benchmark，记录 Scenario/Profile/Generator/seed/capabilities/generated-at、canonicalization contract、Standard Import package ID 与 dataset hash。`generated_at` 是运行 provenance，不进入 canonical dataset hash；相同确定性输入允许时间戳不同但 Import bytes/hash 必须相同。

`SCHEMA-SCENARIO-P0-05` 和对应 manifest 是 Schema/empty-package sample，不是正式 Scenario，不声称 expected Solver result 已发生。`SIM-MINIMAL-001`、人工 Golden、非空 records 和正式 Scenario catalog 均保持 TASK-P0-06 `PLANNED`。
