---
doc_id: DOC-ARCH-004
title: Simulation-First 双通道架构
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [0, 10, 37, 40, 41, 42, 62, 74]
last_reviewed: 2026-08-19
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

TASK-P1-03～05已形成双方共用的Raw Staging、Reference transport和Normalization primitive：Simulation batch必须携带一致Scenario/Profile/Generator/seed，Production batch禁止这些字段；两者随后使用同一MappingProfile/unit/time/ID/canonical serializer。当前仍没有Synthetic Generator→staging orchestration或Data Validation/Snapshot/Problem common-ingress Gate，因此不能把单元测试视为完整双通道闭环。
