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
