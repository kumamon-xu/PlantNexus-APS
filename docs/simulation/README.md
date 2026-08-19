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

Schema set 为 additive `1.2.0`。三份 `.synthetic.json` 仅验证合同，不是 Fixture 或生产数据；P0-05 的 TEST-SCENARIO-REPLAY/TEST-SIM-ISOLATION 只证明 empty package 的确定性与 pure isolation guard。下方 P0-06 fixture 在不改变 schema set 的前提下增加 non-empty committed correctness evidence，仍不证明 Import pipeline、Execution Simulator、Reference Scheduler、Benchmark 或 Solver 已实现。

## P0-06 deterministic Golden

[`SIM-MINIMAL-001@1.0.0`](../../fixtures/deterministic/SIM-MINIMAL-001/calculation-note.md) 是首个正式 correctness fixture：2 workshops、3 resources、alternative resource、cross-workshop transport、maintenance 和人工 Golden Schedule。它保留 `factory-profile.v1` / `scenario-spec.v1` / `scenario-manifest.v1` / `import-package.v1`，以 `P0-MANUAL-FIXTURE-ASSEMBLER@1.0.0`、seed 6001 和 `canonical-json.v1` 形成稳定 hash。

其 non-empty `records` 只属于 `sim-minimal-records.v1` fixture vocabulary；它证明 committed Standard Import envelope 可重放，不证明 P1字段权威、Normalization/Snapshot/Problem pipeline 或程序化 distribution generator。Golden direct calculations 与 replay loader 均不导入 Planning/Solver；P0-07 才实现 reusable rule evaluator/invalid mutations。
