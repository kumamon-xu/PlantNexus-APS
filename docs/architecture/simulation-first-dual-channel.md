---
doc_id: DOC-ARCH-004
title: Simulation-First 双通道架构
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [0, 10, 37, 40, 41, 42, 62, 74]
last_reviewed: 2026-08-20
---

# Simulation-First 双通道架构

## P4 planned common-path use

TASK-P4-09/10将建立deterministic Execution Simulator、虚拟时钟和五类连续异常，但synthetic事件必须通过TASK-P4-04同一validated event/fact入口，重排必须通过TASK-P4-08同一application service；禁止simulation-only shortcut伪造Production能力。TASK-P4-01的planned Execution Simulator Common-Path ADR必须先决定common-path与隔离边界。当前只有规划，没有Simulator runtime、Production channel或外部集成。

## 核心设计

Production 和 Simulation 只在数据来源及环境隔离上不同，从 Standard Import Contract 开始必须使用同一产品链路。

```text
Production Sources ─┐
                    ├→ Standard Import Contract
Scenario Generator ─┘             │
                                  ▼
Normalization → Data Validation → Snapshot → Problem
→ same Strategy → same Solver → same Validator → same Export
```

## 禁止捷径

- Simulator 直接构造 CpModel；
- Generator 直接构造仅 Solver 可识别的对象；
- Simulation 绕过数据质量校验；
- Simulation 调用特殊简化 Solver；
- 为了通过场景而在生产链路添加 synthetic-only 默认规则。

## 可重放标识

Synthetic 输入和成果必须记录：

```text
scenario_id
scenario_version
seed
factory_profile
profile_version
generator_version
generated_at
dataset_hash
```

同 ScenarioSpec、FactoryProfile、Generator Version 和 seed 必须得到相同 canonical dataset 和 hash。

## 隔离

- `synthetic=true` 是 Snapshot 的显式属性；
- 至少使用独立数据库（推荐 `aps_dev`、`aps_sim`、`aps_prod`）；
- Production 默认对 `/api/v1/sim/*` 返回 404/disabled；
- Simulation Config 不能覆盖 Production Business Policy。

## P0 executable boundary

TASK-P0-05 以七层 pure Protocol 固定 Generator 责任，并提供 `build_empty_import_package` 作为最小边界证据。该 primitive 的唯一数据输出是 `import-package.v1` metadata envelope，`records={}`；它不生成 PlanningProblem、Snapshot、CpModel 或任何生产字段。`ScenarioManifest v1` 引用该 Import package 并记录 Profile/Scenario/Generator/seed、目标环境、generated-at 与 dataset hash。

`canonical-json.v1` 的 hash 输入是完整 canonical Import package bytes，不含 manifest `generated_at`。相同 Profile/Scenario/Generator version/seed 得到相同 package/hash；generator version 或 seed 变化会进入 source provenance 并改变 hash。Development/Test/Benchmark 可创建 context，`production` 在 context 建立阶段以 `SYNTHETIC_REFERENCE_IN_PRODUCTION` 拒绝。

TASK-P1-03～05已形成双方共用的Raw Staging、Reference transport和Normalization primitive：Simulation batch必须携带一致Scenario/Profile/Generator/seed，Production batch禁止这些字段；两者随后使用同一MappingProfile/unit/time/ID/canonical serializer。TASK-P1-06新增单一`app.data_validation` evaluator，既不读取data plane也不提供synthetic-only规则；Production/Simulation canonical Import必须得到相同结构/reference/DAG/resource/capability/time/unit/duration判定。

TASK-P1-06完成时仍没有Synthetic Generator→staging orchestration、Order Expansion、Snapshot/Problem或common-ingress Gate；该历史边界解释为什么固定schema sample的quality PASS不能单独视为双通道闭环。后续TASK-P1-10/11已按下节形成对应实现，但Simulation仍不得伪造PASS report或绕过Data Validation。

## TASK-P1-10 executable synthetic channel

七层Generator现从frozen FactoryProfile/ScenarioSpec context与命名child seed生成source-shaped topology/routing/orders/calendars/material/execution/locks records，再进入Simulation StagedImportBatch、公开Normalization和Data Validation，形成非空Import v2及PASS/0 quality evidence。Canonical package hash覆盖Import完整bytes，不覆盖generator-local manifest的`generated_at`；同Profile/Scenario/generator/seed得到相同bytes/hash。

本Slice只形成synthetic channel到canonical Import gate；没有把Production source接入同一application use case，也没有构建Snapshot/Problem/Solver。TASK-P1-11 common-ingress evidence、独立Production/Simulation数据库和Production connector仍未形成，不能因source形状相同而宣布双通道Exit Gate完成。

## TASK-P1-11 shared application channel

Generator公开`prepare_batch()`和ReferenceFileAdapter现分别产生Simulation `StagedImportBatch`，然后同时进入唯一`CommonIngressPipeline`直到PlanningProblem。Reference侧使用temporary CSV表达同一synthetic source semantics，因此证明的是adapter/generator双入口共用产品链路，不是真实Production connector。

Application在Normalization前比对explicit expected plane，交叉输入以`DATA_PLANE_MISMATCH`拒绝。独立aps_sim/aps_prod数据库、network/role、Production API与发布隔离仍未形成；ADR-0009与RISK-007仍然有效。

## TASK-P1-12 Exit Gate audit

独立审计以`SIM-P1-INGRESS-001@1.0.0`/generator`1.0.0`/seed`20260820`执行两次Synthetic replay并用同义Reference CSV进入同一application链，Import/Snapshot/Problem完整bytes/hash parity与14/14 checks均PASS。Import、Snapshot和Problem hashes分别为`sha256:24a74b4f43b0ba42ed458983e0c4776613911924ae5250d9df8ae9e4f14cb1c4`、`sha256:090e0e08e05bb569d0aae00461803cebd56f87444243484a3696126bfe510409`、`sha256:71c0b729dd2b08ba1d14d5a281029b8d9bc13596a90a5189fb20176e19f690da`。

该PASS使总规§74的共同数据链Gate=`READY`，但Reference文件仍为synthetic temporary input、`production_binding=false`；独立Production/Simulation数据库与角色、真实connector、Solver/Validator/Export链仍未形成。P1-12没有进入P2。

## TASK-P2-09 Simulation correctness channel

新Scenario assembler从versioned blueprint产生source-shaped Raw rows，并复用P1 mapping/Normalization/Data Validation/Expansion/Snapshot/Problem公开边界；随后才调用P2 Global Strategy和formal Validator。它不允许直接Problem/CpModel构造，也不改写P1 Generator或Reference channel，因此新证据验证真实模块边界而不是测试捷径。

七例全部属于Simulation correctness；它们不会绑定Production source、修改Production policy、生成Reference Scheduler/Benchmark/Export或进入P3。真实双通道Production authority仍由后续OPEN closure和Task治理。
