---
doc_id: ADR-0003
title: Solver-neutral PlanningProblem
status: accepted
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [13, 14, 24]
last_reviewed: 2026-08-19
---

# ADR-0003 — Solver-neutral PlanningProblem

## Decision

PlanningProblem 是可序列化、deterministic、solver-neutral 的版本化合同。Domain 和 Problem 不包含 OR-Tools 类型；SolverBackend 通过协议接收 Problem/Policy/Limits 并返回 PlanningSolution。

## Consequences

问题可重放、独立验证并允许未来替换 Backend；需要维护清晰的 domain→problem 和 problem→backend 映射。修改 Problem contract 触发 version、ADR、replay 和 Benchmark。

## Rejected

在 ORM Model、API Controller 或领域实体中直接构造 CpModel。
