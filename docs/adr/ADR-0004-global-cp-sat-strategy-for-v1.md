---
doc_id: ADR-0004
title: V1 使用 Global CP-SAT Strategy
status: accepted
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [14, 25, 75, 82]
last_reviewed: 2026-08-19
---

# ADR-0004 — V1 使用 Global CP-SAT Strategy

## Decision

V1 使用 GlobalCpSatStrategy，在单个 PlanningRun 中统一建模 Snapshot 内全部 V1 OperationInstance，主 Backend 为固定精确版本的 Google OR-Tools CP-SAT。

## Consequences

跨车间依赖和全局目标语义直接、可验证；模型规模可能成为风险，因此从 P2 起记录完整 complexity/performance metrics。

Decomposed/Rolling/Hybrid strategy 只有在大型 Benchmark、历史回放、内存预算或模型爆炸证据存在时才能通过新 ADR 进入。
