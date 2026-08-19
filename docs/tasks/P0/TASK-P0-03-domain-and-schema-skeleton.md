---
doc_id: TASK-P0-03
title: Domain and Schema Skeleton
status: planned
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [17, 18, 19, 20, 23, 24, 36, 70, 71, 103]
last_reviewed: 2026-08-19
---

# TASK-P0-03 — Domain and Schema Skeleton

Requirement IDs: REQ-001, REQ-002, REQ-003, REQ-009

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, ENG-SOL-001, ENG-VER-001

Depends on: TASK-P0-01, TASK-P0-02

Goal: 建立领域类型和 JSON/Scenario Schema 骨架，固定 Snapshot/Problem/KPI/Error 等顶层合同但不实现 P1 数据管道。

Inputs: `docs/domain/**`、`docs/contracts/**`、data authority、time rules。

Files allowed to change: `schemas/**`、`backend/app/domain/**` 的纯类型骨架、Schema contract tests，以及下方 `Documents to update` 的明确文档路径。

Files forbidden to change: import pipeline、ORM/migrations、API、Celery、`planning/backends/cp_sat/**`。

Implementation steps: 定义 versioned schema IDs；建立 canonical ID/time/duration 类型；创建 Snapshot/Problem/KPI/Error/ValidationReport 顶层 skeleton；添加 round-trip/invalid schema tests。

Outputs: Schema skeleton、纯领域类型、data dictionary 初版、contract test results。

Documentation impact: required

Documents to update: `docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/contracts/planning-snapshot.md`、`docs/contracts/planning-problem.md`、`docs/domain/domain-model.md`、`docs/domain/operation-instance-and-resource-options.md`、`docs/domain/time-calendar-and-material-boundaries.md`、`docs/domain/kpi-contract.md`、`docs/domain/error-model.md`、`docs/governance/traceability-matrix.md`、`docs/governance/document-inventory.md`、本 Task Card。

Documentation impact rationale: Schema 和纯领域类型会固定合同字段、版本、不变量及序列化语义。

Change-impact matrix rows reviewed: schemas/domain DTO；domain entities/invariants；snapshots；planning/problem；只修改文档。

Traceability updates: REQ-001/002/003/009、NFR-DET/TRC、ENG-SOL/VER 到 Schema、contract tests 和 data dictionary artifacts 的关系。

Schema changes: 首次发布 `v1` skeleton；字段未知时 required/optional 规则不得猜测生产默认值。

Migration: 无数据库迁移。

Error behavior: invalid version/reference/time/duration 明确拒绝。

Tests: Schema positive/negative、UTC/duration、unknown field policy、serialization round-trip。

Benchmark impact: 无 Solver Benchmark；记录 serialization baseline 可选。

Simulation scenarios: 只提供 Schema sample，不生成正式场景。

Acceptance commands: Schema validator、contract tests、type check。

Artifacts: published schema files、schema index、test report。

Explicitly excluded: Normalization、Snapshot builder/hash 实现、Solver、生产 Adapter。

PROD_OPEN: OPEN-001/002/003/004/007/013/015 引用但不关闭。

SIM_ASSUMPTIONS: sample 数据显式 synthetic。

Rollback: 使用 schema version/compatibility 规则回退；已发布版本不可无痕覆盖。
