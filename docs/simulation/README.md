---
doc_id: DOC-SIM-INDEX
title: Simulation 子系统
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [0, 10, 37, 46, 57, 84, 85, 112]
last_reviewed: 2026-08-28
---

# Simulation 子系统

## TASK-P4-10 continuous disruption library

`simulation/scenarios/disruption_replay.py`现拥有strict versioned asset loader与五步连续编排；fixture固定Urgent、Machine fail/recover、Material delay/ready、Processing duration/remaining与Early Completion共8个标准event。每步必须返回完整Event→Snapshot→Replan→fresh Validator→DRAFT/ChangeReport envelope并承接前一步baseline；missing/extra字段、coverage/order/seed/plane或任何invariant漂移均拒绝。

该层不拥有P4-04/05/06/07/08/09语义实现，只组合其公开合同和machine evidence。所有baseline advance均为`SIMULATION_NON_PRODUCTION`且无authority claim；不存在自动approval/publication/export、P5 capability或Production connector/capacity/SLA。

## TASK-P4-09 Execution Simulator core

TASK-P4-09现建立deterministic虚拟时钟、versioned event schedule、named-child-seed队列、canonical standard ExecutionEvent stream、prefix checkpoint/restart与P4-04同一`ingest_event`公共入口；完整stream在任何入口调用前strict precheck。TASK-P4-10才增加Urgent Demand、Machine Failure/Recovery、Material Delay/Ready、Processing Duration/Remaining变化与Early Completion五类连续场景及replay；TASK-P4-14/15分别聚合与审计。所有数据仍为versioned synthetic provenance，不形成Production twin、真实MES、外部发布或capacity/SLA结论。

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

PUBLISHED ScheduleVersion + Scenario/Profile/Generator/Simulator versions
+ Seed + Versioned Event Schedule + Virtual Clock
→ Standard ExecutionEvent → P4-04 ledger/fact ingress
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

## P1-10 canonical generator

[`SIM-P1-INGRESS-001@1.0.0`](../../fixtures/synthetic/SIM-P1-INGRESS-001/calculation-note.md)现由七层`PLANTNEXUS-P1-CANONICAL-IMPORT-GENERATOR@1.0.0`程序化生成。它使用FactoryProfile/ScenarioSpec/seed，经source-shaped Raw Staging、`P1-SYNTHETIC-SOURCE-MAPPING@1.0.0`、unit registry、Normalization和Data Validation产生16个非空canonical collections、49 records与PASS/0报告；canonical hash为`sha256:24a74b4f43b0ba42ed458983e0c4776613911924ae5250d9df8ae9e4f14cb1c4`。

该asset只验证correctness/replay/common-format ingress的一侧，不是Solver/Benchmark、Execution Simulator、Production capacity或P1-11双来源application Gate证据。P0 manual fixture保持只读且使用Import v1/fixture-local vocabulary。

## P2-12 Benchmark profiles

[`benchmarks/profiles.yaml`](../../benchmarks/profiles.yaml)发布strict internal `benchmark-profile-set.v1`，只包含XS/S/M。`PLANTNEXUS-P2-BENCHMARK-GENERATOR@1.0.0`确定性生成source-shaped blueprint，再复用`PLANTNEXUS-P2-CORRECTNESS-ASSEMBLER@1.0.0`进入正式Raw→Problem链；它不会直接构造Problem或CpModel。XS/S/M分别固定8/24/48 operations及对应immutable v1 baseline，全部参数由SIM-ASSUMPTION-013登记。

Runner只用于development/test/benchmark data plane。L/XL、故障分布、Production topology/capacity/SLA均不在当前profile set；不得从本地或CI结果外推真实工厂能力。
