---
doc_id: DOC-SIM-002
title: ScenarioSpec 与 Provenance
status: baseline
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [39, 40, 44, 46, 49, 104]
last_reviewed: 2026-08-28
---

# ScenarioSpec 与 Provenance

## TASK-P4-09 provenance consumption

TASK-P4-09现在把scenario/profile/generator/simulator的ID、semantic version和fingerprint、seed、PUBLISHED base、Snapshot/Problem、Policy/Limits、virtual-clock origin/resolution、event-schedule fingerprint、run fingerprint、ordered event fingerprints及code commit纳入manifest/stream证据，且强制`synthetic=true`、`production_binding=false`。Core只消费versioned asset reference和已登记capability；不修改ScenarioSpec Schema/sample，也不生成P4-10定量事件。SIM-ASSUMPTION-018只保存core correctness vector。

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

`SCHEMA-SCENARIO-P0-05` 和对应 manifest 是 Schema/empty-package sample，不是正式 Scenario，不声称 expected Solver result 已发生。它们与下方 TASK-P0-06 形成的 `SIM-MINIMAL-001` 正式 asset 保持不同 ID/hash，不能互相替代。

## SIM-MINIMAL-001@1.0.0

首个正式 Scenario 资产位于 [`fixtures/deterministic/SIM-MINIMAL-001`](../../fixtures/deterministic/SIM-MINIMAL-001/calculation-note.md)：Profile `PROFILE-SIM-MINIMAL-FJSP@1.0.0`、assembler identity `P0-MANUAL-FIXTURE-ASSEMBLER@1.0.0`、seed 6001、5 个 V1 capability、XS correctness complexity 和允许结果 FEASIBLE/OPTIMAL。人工 Golden 证明本 fixture 的 weighted tardiness 0 与 horizon-relative makespan 10800 秒 lower bound；这不是 Solver status 已发生的声明。

manifest 固定 Import package `SIMPKG-SIM-MINIMAL-001-1.0.0` 与 hash `sha256:fd8e5af387c7d4197a2664dfa89e93912091647d5809f1b76468d36edab29c10`。`generated_at=2026-08-19T00:00:00Z` 只记录 artifact assembly instant，不进入 hash。Profile/Scenario/Assembler/Fixture record vocabulary 任一语义变化必须新建版本；不得覆盖历史 artifact/hash。

## SIM-P1-INGRESS-001@1.0.0

P1 regression Scenario引用`PROFILE-SIM-P1-INGRESS-001@1.0.0`、generator `PLANTNEXUS-P1-CANONICAL-IMPORT-GENERATOR@1.0.0`和seed `20260820`，声明七项V1 capability及material/WIP/lock/cross-workshop比例0.5。两条order/lot lineage使quota各选择一条material delay、RUNNING fact和operation lock；expected FEASIBLE/OPTIMAL仍只是未来Solver允许结果，不代表本Task执行了求解。

P1 Import v2使用generator-local `synthetic-generation-manifest.v1`记录quality/normalization/unit引用，因为发布的`scenario-manifest.v1`固定Import v1且保持不变。相同输入重放hash为`sha256:24a74b4f43b0ba42ed458983e0c4776613911924ae5250d9df8ae9e4f14cb1c4`；generated-at不同不影响hash。

TASK-P1-11又将该固定asset从公开Raw Staging连续重放到Snapshot/Problem：Gate配置cutoff=`2026-11-06T12:30:00Z`、horizon end=`2026-11-07T12:30:00Z`、tick=60s，得到Snapshot hash `sha256:090e0e08e05bb569d0aae00461803cebd56f87444243484a3696126bfe510409`和Problem hash `sha256:71c0b729dd2b08ba1d14d5a281029b8d9bc13596a90a5189fb20176e19f690da`。该配置只是asset-local correctness replay，不变更ScenarioSpec/manifest版本、expected Solver results或Production policy。

## TASK-P2-09 resolved correctness manifests

两份Golden以独立`factory-profile.json`、`scenario-spec.json`、`scenario-blueprint.json`、`correctness-manifest.json`、`expected-outcome.json`和手算说明发布；五例矩阵以共享Profile、catalog和blueprint-set发布。`p2-correctness-manifest.v1`是fixture-local resolved evidence contract，固定asset对象hash、pipeline versions、approved policy、Backend/Solver identity与Import/Snapshot/Problem expected hash；它不取代或修改`scenario-manifest.v1`发布Schema。

Assembler `PLANTNEXUS-P2-CORRECTNESS-ASSEMBLER@1.0.0`只把小型blueprint扩展为source-shaped Raw records，随后使用公开P1/P2链路。Scenario expected只允许OPTIMAL且Validator PASS；任何version/reference/hash/status漂移都会在求解前后hard fail。新数值绑定SIM-ASSUMPTION-011，不构成Benchmark/Production default。
