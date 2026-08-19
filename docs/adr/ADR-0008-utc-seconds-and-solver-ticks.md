---
doc_id: ADR-0008
title: UTC、整数秒与可配置 Solver Tick
status: accepted
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [16, 20, 24]
last_reviewed: 2026-08-19
---

# ADR-0008 — UTC、整数秒与可配置 Solver Tick

## Decision

数据库使用 UTC TIMESTAMPTZ，显示使用 factory timezone；权威 duration 为整数秒，Solver 使用 `ceil(seconds/tick_seconds)` 的可配置 tick，默认 60 秒。

## Consequences

跨系统时间和 duration 可追溯，Solver 域可控；向上取整可能影响精度和 horizon/model size，因此 tick 必须进入 Problem/Report/Benchmark。生产 timezone 未确认阻止生产，不阻止开发。
