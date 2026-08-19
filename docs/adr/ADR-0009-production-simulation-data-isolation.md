---
doc_id: ADR-0009
title: Production 与 Simulation 数据隔离
status: accepted
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [38, 40, 59, 62, 64, 96]
last_reviewed: 2026-08-19
---

# ADR-0009 — Production 与 Simulation 数据隔离

## Decision

Synthetic 数据显式标识并至少使用独立 Database；Production 默认禁用 Simulation API。Simulation Config 不能覆盖 Production Business Policy。

## Consequences

降低数据污染和错误发布风险，但需要独立环境、权限、备份和监控配置。所有发布/导出路径必须检查 synthetic 标识。真实数据进入 Simulation/Historical 环境前需要匿名化和授权治理。
