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

## P0 executable evidence

TASK-P0-07 以 [`schedule_validator.py`](../../backend/app/planning/validation/schedule_validator.py) 落实该 Decision 的 fixture-local correctness slice：它从 `SIM-MINIMAL-001` Import facts 与 candidate assignments 独立复算 C-001～C-011，不导入 planning backend/OR-Tools、不读取 expected outcome，也不复用未来 CP-SAT builder。13 个声明式 mutation 与 exact v2 reports/errors 形成 TEST-VALIDATOR-MUTATION evidence，并保持 positive Golden 不变。

ADR 决策本身未改变，因此不新建替代 ADR。当前实现不声明 P2 完成：输入仍是 fixture-local vocabulary，尚无正式 PlanningProblem/candidate contract、Solver comparison、Benchmark、API/persistence 或 READY_FOR_REVIEW 状态动作。
