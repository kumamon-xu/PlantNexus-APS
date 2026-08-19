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
