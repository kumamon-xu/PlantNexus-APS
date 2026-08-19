---
doc_id: DOC-GOV-005
title: 追踪矩阵
status: living
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [5, 6, 71, 86]
last_reviewed: 2026-08-19
---

# 追踪矩阵

当前矩阵只登记已经存在的规范和计划证据。代码、自动化测试和成果产物尚未创建，统一标记 `PLANNED`。

| Root | 规范落点 | 首个 Milestone | 首个 Task | Test/Artifact 状态 |
|---|---|---|---|---|
| REQ-001～REQ-003 | `contracts/import-and-normalization.md`、Snapshot/Problem contract | P1 | 不提前创建 | PLANNED |
| REQ-004 | `architecture/end-to-end-planning-flow.md`、`planning/constraint-catalog.md` | P2 | 不提前创建 | PLANNED |
| REQ-005 / ENG-VAL-001 | `planning/schedule-validator.md` | P0/P2 | TASK-P0-07 | Rule sheet PLANNED |
| REQ-006 | `contracts/export-package.md` | P2/P3 | 不提前创建 | PLANNED |
| REQ-007 / NFR-HUM-001 | ScheduleVersion state machine | P3 | 不提前创建 | PLANNED |
| REQ-008 | `planning/replanning.md` | P4 | 不提前创建 | PLANNED |
| REQ-009 / NFR-TRC-001 | `architecture/provenance-and-versioning.md` | P1 | TASK-P0-02 establishes IDs | PLANNED |
| REQ-010 | Capability matrix | P6 | 不提前创建 | DEFERRED |
| REQ-011～REQ-012 | `simulation/` contracts | P0/P1 | TASK-P0-05/06 | Schema/Fixture PLANNED |
| REQ-013 | Execution Simulator contract | P4 | 不提前创建 | PLANNED |
| REQ-014～REQ-015 | Benchmark/Reference Scheduler docs | P2 | 不提前创建 | PLANNED |
| NFR-COR-001 | Constraint + Validator contracts | P0/P2 | TASK-P0-04/07 | PLANNED |
| NFR-DET-001 | Snapshot/Problem/Simulation contracts | P0/P1 | TASK-P0-05/06 | PLANNED |
| NFR-OBS-001 | Observability contract | P0 | TASK-P0-08 | PLANNED |

每个 Task 完成时必须更新本矩阵；只增加真实路径和真实测试结果。
