---
doc_id: TASK-P0-05
title: Simulation Contracts and Skeleton
status: planned
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [10, 37, 38, 39, 40, 41, 42, 70, 71, 104]
last_reviewed: 2026-08-19
---

# TASK-P0-05 — Simulation Contracts and Skeleton

Requirement IDs: REQ-011, REQ-012, REQ-013, REQ-014, REQ-015

NFR / ENG IDs: NFR-DET-001, NFR-ISO-001, NFR-TRC-001

Depends on: TASK-P0-03, TASK-P0-04

Goal: 建立 FactoryProfile/ScenarioSpec/manifest Schema、Simulation 模块边界和 deterministic generator protocol skeleton。

Inputs: `docs/simulation/**`、dual-channel architecture、schema index。

Files allowed to change: `schemas/scenario/**`、`backend/app/simulation/**` 纯协议/空实现骨架、simulation contract tests，以及下方 `Documents to update` 的明确文档路径。

Files forbidden to change: CpModel、Solver backend、直接 PlanningProblem generator、生产配置/数据库。

Implementation steps: 定义 version/seed/provenance；分层 generator protocols；建立 canonical package output contract；实现 seed plumbing 和空/最小 deterministic primitives；验证 synthetic isolation flags。

Outputs: versioned Simulation schemas、module skeleton、determinism/isolation tests。

Documentation impact: required

Documents to update: `docs/architecture/simulation-first-dual-channel.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/provenance-and-versioning.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/simulation/README.md`、`docs/simulation/factory-profile.md`、`docs/simulation/scenario-spec-and-provenance.md`、`docs/simulation/synthetic-generator-and-determinism.md`、`docs/simulation/scenario-library-and-matrix.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/traceability-matrix.md`、`docs/governance/document-inventory.md`、本 Task Card。

Documentation impact rationale: Profile、Scenario、Generator、provenance 和隔离均属于版本化 Simulation 合同。

Change-impact matrix rows reviewed: simulation/profiles；simulation/scenarios；simulation/generators；schemas；infrastructure/config；只修改文档。

Traceability updates: REQ-011～015、NFR-DET/ISO/TRC、Scenario/Profile/Generator Schema versions、replay/isolation tests 与 manifests。

Schema changes: FactoryProfile/ScenarioSpec/ScenarioManifest v1 skeleton。

Migration: 无。

Error behavior: missing version/seed、production target、unsupported capability 声明错误时拒绝。

Tests: schema contract、same seed replay primitive、different version provenance、production isolation。

Benchmark impact: 只建立 report/profile contract，不运行性能宣称。

Simulation scenarios: 仅 Schema samples；SIM-MINIMAL 在下一 Task。

Acceptance commands: contract/unit tests、determinism smoke test。

Artifacts: schemas、generator protocol、manifest sample、test report。

Explicitly excluded: 大规模 Generator、Execution Simulator 行为、真实 Benchmark、Solver。

PROD_OPEN: 无关闭。

SIM_ASSUMPTIONS: 所有 sample `synthetic_only=true`。

Rollback: 保留旧 schema/version；移除未被 Fixture 引用的新 skeleton。
