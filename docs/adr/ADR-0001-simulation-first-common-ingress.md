---
doc_id: ADR-0001
title: Simulation-First 使用共同数据入口
status: accepted
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [0, 10, 37, 62]
last_reviewed: 2026-08-19
---

# ADR-0001 — Simulation-First 使用共同数据入口

## Context

当前没有可直接使用的真实工厂 APS 历史环境，需要在真实数据进入前发现模型、约束、规模和重排风险。

## Decision

Synthetic Generator 输出 Standard Import Contract，随后与生产输入使用同一 Normalization、Validation、Snapshot、Problem、Solver、Validator 和 Export 链路。Simulation 与 Production 数据/环境隔离。

## Rejected

Simulator 直接构造 CpModel、绕过校验或调用特殊简化 Solver。

## Consequences

仿真能验证真实产品链路，但 Generator/Schema 的初期建设成本更高。Synthetic 结果必须带 provenance，不能成为生产默认值或容量承诺。
