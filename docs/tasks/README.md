---
doc_id: DOC-TASK-INDEX
title: Task Card 索引
status: living
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [2, 6, 73, 74, 98, 99, 100]
last_reviewed: 2026-08-19
---

# Task Card 索引

当前 Phase为 P1。P0 Task作为 terminal历史保留；只允许创建/执行 P1详细 Task Card，P2～P7继续只保留 Milestone。

## P0 history

| Task | 目标 | 依赖 | 状态 |
|---|---|---|---|
| TASK-P0-01 | Repository/document governance skeleton | 文档基线 | `done` |
| TASK-P0-02 | Requirements、NFR/ENG 与追踪机制 | P0-01 | `done` |
| TASK-P0-03 | Domain contract 与 Schema skeleton | P0-01/02 | `done` |
| TASK-P0-04 | Constraint、State、Error、Capability contracts | P0-02/03 | `done` |
| TASK-P0-05 | Simulation contracts 与 module skeleton | P0-03/04 | `done` |
| TASK-P0-06 | SIM-MINIMAL-001 与人工 Golden Schedule | P0-05 | `done` |
| TASK-P0-07 | Illegal Fixtures 与 Validator Rule Sheet | P0-04/06 | `done` |
| TASK-P0-08 | CI、logging、DB、worker、health skeleton | P0-01/02 | `done` |
| TASK-P0-09 | P0 Exit Gate audit | P0-01～08 | `done` |
| TASK-P0-10 | CI workflow/provider evidence remediation | P0-09 | `done` |

P0 superseding audit=`READY`，用户于 2026-08-19 明确批准进入 P1；历史 Task/失败 run/evidence不删除或重写。

## P1 execution order

| Task | 目标 | 依赖 | 状态 |
|---|---|---|---|
| [TASK-P1-01](P1/TASK-P1-01-phase-governance-and-ci-handoff.md) | Phase-aware governance 与 CI handoff | P0-10 | `in_progress` |
| [TASK-P1-02](P1/TASK-P1-02-canonical-import-contracts.md) | Canonical records、Import v2、Snapshot v2合同 | P1-01 | `planned` |
| [TASK-P1-03](P1/TASK-P1-03-raw-staging-and-import-provenance.md) | Raw Staging、provenance、idempotent persistence | P1-02 | `planned` |
| [TASK-P1-04](P1/TASK-P1-04-csv-excel-reference-adapter.md) | CSV、Excel与ReferenceFileAdapter v1 | P1-02/03 | `planned` |
| [TASK-P1-05](P1/TASK-P1-05-normalization-and-unit-time-rules.md) | Deterministic ID/time/unit Normalization | P1-02/03/04 | `planned` |
| [TASK-P1-06](P1/TASK-P1-06-data-quality-and-routing-validation.md) | DAG/reference/capability Data Validation | P1-05 | `planned` |
| [TASK-P1-07](P1/TASK-P1-07-deterministic-order-expansion.md) | Deterministic Order/Lot/Operation expansion | P1-06 | `planned` |
| [TASK-P1-08](P1/TASK-P1-08-immutable-snapshot-and-hash.md) | Immutable PlanningSnapshot 与 hash | P1-03/06/07 | `planned` |
| [TASK-P1-09](P1/TASK-P1-09-planning-problem-builder-and-hash.md) | Solver-neutral PlanningProblem builder/hash | P1-07/08 | `planned` |
| [TASK-P1-10](P1/TASK-P1-10-synthetic-generator-records.md) | 七层 Synthetic Generator非空 canonical records | P1-02/05/06/07 | `planned` |
| [TASK-P1-11](P1/TASK-P1-11-common-ingress-pipeline-and-gate-evidence.md) | Common-ingress E2E与 P1 Gate evidence | P1-03～10 | `planned` |
| [TASK-P1-12](P1/TASK-P1-12-p1-exit-gate-audit.md) | P1 Exit Gate Audit | P1-01～11 | `planned` |

## Lifecycle rules

状态由 Task front matter记录：`planned`、`ready`、`in_progress`、`blocked`、`done`、`cancelled`。只有真实验收证据存在时才能标记 `done`。

Task进入 `in_progress` 时必须先把当时完整 40字符 HEAD SHA写入 `Diff base`。验收器使用 `Diff base..HEAD`与 working tree路径并集检查范围和change-impact；P1 Task还必须有明确 `Completion conditions`。

每张 Task Card在开始前完成文档影响分析：`Documentation impact`、明确 `Documents to update`、理由、`IMPACT-*` Rule IDs与`Traceability updates`。`Documents to update`必须包含在允许范围；发现额外文件先停止并修订卡片。

当前唯一 `in_progress` Task为 TASK-P1-01，Diff base=`430506349ccdc135072e12fc98f7df1744a63e2c`；它先消除现有 P0-10-specific CI handoff，再允许启动 canonical contracts。完成一个 Task不会自动启动下一个；P1-12即使审计 `READY`也不自动进入 P2。
