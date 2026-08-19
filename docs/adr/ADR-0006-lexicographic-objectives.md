---
doc_id: ADR-0006
title: 词典序目标层级
status: accepted
spec_version: 0.3.0
phase: P2-P4
normative: true
source_sections: [28, 35]
last_reviewed: 2026-08-19
---

# ADR-0006 — 词典序目标层级

## Decision

目标分轮执行：首先 OBJ-001 weighted tardiness；Replan 时在 delivery 等价后执行 OBJ-002 stability；最后 OBJ-003 makespan 作为 tie breaker。

## Rejected

使用未经业务证据支持的 `0.6/0.3/0.1` 混合权重。

## Consequences

目标优先级可解释、可审计，但可能增加多轮求解成本。SolverReport 必须记录每一轮目标、bound、预算和停止原因。业务 tardiness/priority 语义受 OPEN-006 约束。
