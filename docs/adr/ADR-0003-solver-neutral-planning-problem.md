---
doc_id: ADR-0003
title: Solver-neutral PlanningProblem
status: accepted
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [13, 14, 24]
last_reviewed: 2026-08-20
---

# ADR-0003 — Solver-neutral PlanningProblem

## Decision

PlanningProblem 是可序列化、deterministic、solver-neutral 的版本化合同。Domain 和 Problem 不包含 OR-Tools 类型；SolverBackend 通过协议接收 Problem/Policy/Limits 并返回 PlanningSolution。

## Consequences

问题可重放、独立验证并允许未来替换 Backend；需要维护清晰的 domain→problem 和 problem→backend 映射。修改 Problem contract 触发 version、ADR、replay 和 Benchmark。

## Rejected

在 ORM Model、API Controller 或领域实体中直接构造 CpModel。

## TASK-P1-09 implementation review

`planning-problem-builder.v1`与`planning-problem-hash-projection.v1`把本ADR既有决定落实为pure Snapshot→canonical JSON/bytes/hash边界；实现不含ORM、API、Infrastructure、OR-Tools、Backend或Solver状态。Active lock及completed-active historical lag在v1无字段时明确拒绝，不以隐藏字段或Backend side channel绕过合同。

该实现没有改变本ADR的Decision、Problem v1 Schema或Backend协议，因此无需新ADR。未来新增上述字段、改变hash projection/builder语义、允许非Problem对象进入Backend或引入Solver-specific类型时，必须发布新version并按ADR/replay/benchmark流程审查。
