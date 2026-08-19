---
doc_id: ADR-0005
title: 独立 ScheduleValidator
status: accepted
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [30, 31]
last_reviewed: 2026-08-19
---

# ADR-0005 — 独立 ScheduleValidator

## Decision

所有候选计划使用独立 Validator 检查 C-001～C-011。Validator 不导入 CpSatBackend、不复用 CP-SAT constraint builder、不信任 Solver status。

## Consequences

需要维护第二条规则实现和 Mutation Test，但能发现建模、映射和 Solver 输出的共同风险。任何新 Constraint 必须 Solver/Validator/Fixture/Benchmark 同步交付。

进入 READY_FOR_REVIEW 的必要条件为 Validator PASS 且 hard violation count 为 0。
