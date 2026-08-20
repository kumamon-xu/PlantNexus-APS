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

当前仍没有Synthetic Generator→staging orchestration、Order Expansion、Snapshot/Problem或TASK-P1-11 common-ingress Gate，因此固定schema sample的quality PASS不能视为完整双通道闭环或独立数据库隔离证据。Simulation不得直接伪造PASS report或绕过Data Validation。

## TASK-P1-10 executable synthetic channel

七层Generator现从frozen FactoryProfile/ScenarioSpec context与命名child seed生成source-shaped topology/routing/orders/calendars/material/execution/locks records，再进入Simulation StagedImportBatch、公开Normalization和Data Validation，形成非空Import v2及PASS/0 quality evidence。Canonical package hash覆盖Import完整bytes，不覆盖generator-local manifest的`generated_at`；同Profile/Scenario/generator/seed得到相同bytes/hash。

本Slice只形成synthetic channel到canonical Import gate；没有把Production source接入同一application use case，也没有构建Snapshot/Problem/Solver。TASK-P1-11 common-ingress evidence、独立Production/Simulation数据库和Production connector仍未形成，不能因source形状相同而宣布双通道Exit Gate完成。

## TASK-P1-11 shared application channel

Generator公开`prepare_batch()`和ReferenceFileAdapter现分别产生Simulation `StagedImportBatch`，然后同时进入唯一`CommonIngressPipeline`直到PlanningProblem。Reference侧使用temporary CSV表达同一synthetic source semantics，因此证明的是adapter/generator双入口共用产品链路，不是真实Production connector。

Application在Normalization前比对explicit expected plane，交叉输入以`DATA_PLANE_MISMATCH`拒绝。独立aps_sim/aps_prod数据库、network/role、Production API与发布隔离仍未形成；ADR-0009与RISK-007仍然有效。
