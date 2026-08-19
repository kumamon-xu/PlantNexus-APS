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

## TASK-P0-08 implementation evidence

环境配置显式区分 runtime environment 与 data plane；Production 二者必须同时为 production、Simulation API 必须 false、code commit 必须固定。health-only app 没有 Simulation endpoint，development Compose 明确不使用 production data plane。该证据仍没有建立独立 aps_sim/aps_prod Database、权限/backup/monitoring、共同 ingress 或 publish/export guard，不能关闭 RISK-007 或把 local Compose 当作 Production isolation。Decision 未改变。
