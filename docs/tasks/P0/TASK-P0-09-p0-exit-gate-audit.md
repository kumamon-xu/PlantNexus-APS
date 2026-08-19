---
doc_id: TASK-P0-09
title: P0 Exit Gate Audit
status: planned
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [72, 98, 99, 100, 110]
last_reviewed: 2026-08-19
---

# TASK-P0-09 — P0 Exit Gate Audit

Requirement IDs: REQ-001～REQ-015

NFR / ENG IDs: all registered P0 NFR/ENG

Depends on: TASK-P0-01～TASK-P0-08

Goal: 独立核验 P0 全部交付与 Exit Gate，形成证据包和是否允许请求进入 P1 的结论。

Inputs: 所有 P0 Task completion evidence、schemas、fixtures、tests、CI、registries。

Files allowed to change: Gate command/artifact manifests、发现问题的修复 Task Card，以及下方 `Documents to update` 的明确文档路径；`docs/current_phase.md` 仅在用户批准后修改。

Files forbidden to change: 为通过审计而修改 Solver/Constraint/Test assertion；任何 P1 实现。

Implementation steps: 校验每个 Task scope/evidence；执行 Schema/Golden/Rule Sheet/Replay/Build/CI gates；检查 registry 完整性；检查无 CpModel/IntervalVar；抽查追踪链；列出差距。

Outputs: P0 audit report、gate evidence manifest、go/no-go recommendation。

Documentation impact: required

Documents to update: `docs/milestones/P0-executable-specification.md`、`docs/milestones/P0-exit-gate-audit-report.md`（创建）、`docs/governance/traceability-matrix.md`、`docs/governance/document-inventory.md`、`docs/tasks/README.md`、本 Task Card；`docs/current_phase.md` 仅在用户批准进入下一阶段后更新。

Documentation impact rationale: Exit Gate 会把计划证据变成真实审计结论，并可能改变 Milestone/Phase 状态。

Change-impact matrix rows reviewed: milestones/current phase；tests/fixtures/benchmark artifacts；只修改文档。

Traceability updates: 所有 P0 REQ/NFR/ENG/TASK/TEST/ARTIFACT 状态、Gate evidence 和未关闭差距；未经批准不创建 P1 Task。

Schema changes: 审计阶段不直接改 Schema；问题回到原 Task 或新 P0 remediation Task。

Migration: 无。

Error behavior: 任一必需 Gate 无证据即 FAIL/NOT READY，不用文档声明替代测试结果。

Tests: 执行 P0 全部 acceptance suite。

Benchmark impact: P0 不要求真实 Solver Benchmark。

Simulation scenarios: SIM-MINIMAL-001 replay 和 illegal fixtures。

Acceptance commands: P0 aggregate validation command、CI run、repository build。

Artifacts: signed/dated audit report、command logs、manifest、open gaps。

Explicitly excluded: 自动进入 P1、关闭未解决 PROD_OPEN、生产就绪声明。

PROD_OPEN: 必须全部登记，不要求全部关闭。

SIM_ASSUMPTIONS: 必须全部可追溯且未泄漏 Production。

Rollback: 不适用；审计发现问题创建有界 remediation Task。
