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

## TASK-P0-08 implementation evidence

同一 Python package/container image 现在可用不同 command 启动 health-only FastAPI process 与 JSON-only Celery process；通用 Job pure contract 固定 heartbeat、lease、attempt、STALLED 和 idempotency reference semantics。API 不导入/执行 Planning，Celery 不注册业务或 Solver task；因此这里只形成 process/config/reliability skeleton，不证明 Solver Worker、distributed persistence、crash recovery 或业务事务已经实现。Decision 未改变。
