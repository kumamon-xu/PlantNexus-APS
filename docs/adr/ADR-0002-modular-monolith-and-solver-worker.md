---
doc_id: ADR-0002
title: Modular Monolith 与独立 Solver Worker
status: accepted
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [12, 65, 70]
last_reviewed: 2026-08-19
---

# ADR-0002 — Modular Monolith 与独立 Solver Worker

## Context

V1 需要快速形成端到端闭环，同时长时间求解不能阻塞 API Process。

## Decision

采用 Modular Monolith：FastAPI、PostgreSQL、Redis、Solver Worker 和 React Frontend。Solver 与 API Process 分离，长任务异步并带 heartbeat、lease、attempt 和幂等性。

## Consequences

领域与事务仍在单一产品边界内，降低早期分布式复杂度；计算故障与 API 隔离。未来拆服务需基于性能/组织证据提交新 ADR，不能预先微服务化。
