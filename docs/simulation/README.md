---
doc_id: DOC-SIM-INDEX
title: Simulation 子系统
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [0, 10, 37, 46, 57, 84, 85, 112]
last_reviewed: 2026-08-19
---

# Simulation 子系统

Simulation 不是 Demo、Mock 或随机构造测试数据，而是无真实生产数据阶段的第一套可控计划环境。它模拟 APS Planning Reality：工厂结构、订单、工艺、资源、日历、工时、物料释放、WIP、锁定、执行事件和异常，不宣称模拟真实物理设备。

## 分类

| 类型 | 目的 |
|---|---|
| Deterministic Fixture | correctness，可人工/暴力验证 |
| Synthetic Scenario | scalability、robustness、coverage |
| Disruption Scenario | replanning 和事实保护 |
| Historical Scenario | 未来 calibration 和 production validation |

## 核心链路

```text
FactoryProfile + ScenarioSpec + Seed + GeneratorVersion
→ Versioned Import Package
→ Standard Import
→ Snapshot → Problem → Strategy → Solver → Validator
→ Benchmark / Export
```

## 不变量

- 同版本与 seed 可重放；
- 不绕过正式输入和校验；
- synthetic 与 production 隔离；
- unsupported capability 得到明确结果；
- Synthetic Benchmark 不转化为生产容量承诺；
- 真实数据进入后使用 Reality Gap 持续校准，而不是废弃 Simulation。

## P0-05 executable contracts

| Contract | Machine artifact | P0 evidence / remaining boundary |
|---|---|---|
| FactoryProfile v1 | [`factory-profile.schema.json`](../../schemas/scenario/factory-profile.schema.json) | synthetic ranges/capabilities formed；factory generation PLANNED |
| ScenarioSpec v1 | [`scenario-spec.schema.json`](../../schemas/scenario/scenario-spec.schema.json) | version/profile/generator/seed/complexity/expected behavior formed；formal library PLANNED |
| ScenarioManifest v1 | [`scenario-manifest.schema.json`](../../schemas/scenario/scenario-manifest.schema.json) | empty Standard Import replay/hash formed；run/export audit PLANNED |
| Generator protocol | [`simulation/generators`](../../backend/app/simulation/generators) | seven layers + named seed + canonical package boundary formed；non-empty records PLANNED |

Schema set 为 additive `1.2.0`。三份 `.synthetic.json` 仅验证合同，不是 Fixture 或生产数据；`SIM-MINIMAL-001` 仍由 TASK-P0-06 创建。TEST-SCENARIO-REPLAY/TEST-SIM-ISOLATION 只证明 empty package 的确定性与 pure isolation guard，不证明 Import pipeline、Execution Simulator、Reference Scheduler、Benchmark 或 Solver 已实现。
