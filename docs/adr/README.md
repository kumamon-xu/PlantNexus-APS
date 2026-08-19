---
doc_id: DOC-ADR-INDEX
title: Architecture Decision Records
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [97]
last_reviewed: 2026-08-19
---

# Architecture Decision Records

ADR 记录 Architecture、Solver Backend、Constraint semantics、Objective hierarchy、PlanningProblem、Schedule state machine、Data authority、Decomposition、Advanced APS capability 和 Production performance threshold 的决定。

ADR 状态：`proposed`、`accepted`、`rejected`、`superseded`。Accepted ADR 不重写历史；变更通过新 ADR `supersedes` 旧记录。

ADR-0001～0009 是从 implementation spec 0.3.0 已明确决定中建立的基线记录。它们不表示对应代码已经实现。

TASK-P0-03 的 Schema/type skeleton 落实 ADR-0001（共同入口 envelope）、ADR-0003（Solver-neutral Problem）、ADR-0007（immutable Snapshot）、ADR-0008（UTC/seconds/ticks）和 ADR-0009（Production/Simulation 标识隔离）的既有决定，没有改变这些决定，因此不新增 ADR。Problem builder、hash、Solver 或字段权威若偏离这些决定，必须另建 ADR，不能借 skeleton 隐式修改。

TASK-P0-04 把总规既有 C-001～C-018、ADR-0005 独立 Validator 边界和 ADR-0007 ScheduleVersion 不可变/发布状态固定为 versioned rule/state contracts。没有改变 Constraint semantics、Schedule state machine、PlanningProblem、Solver backend 或发布规则，因此不新增 ADR。`EXPORT_FAILED → EXPORTING` 只是既有“可重试”合同的显式 pair；若未来改变 pair/guard、允许 published mutation、共享 Solver validator logic 或启用高级 capability，必须新建 superseding ADR。
