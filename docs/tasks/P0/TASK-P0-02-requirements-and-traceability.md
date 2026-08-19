---
doc_id: TASK-P0-02
title: Requirements and Traceability
status: planned
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [5, 6, 59, 60, 61, 98, 99]
last_reviewed: 2026-08-19
---

# TASK-P0-02 — Requirements and Traceability

Requirement IDs: REQ-001～REQ-015

NFR / ENG IDs: NFR-TRC-001, ENG-VER-001

Depends on: TASK-P0-01

Goal: 固定 REQ/NFR/ENG 根 ID、追踪规则、开放问题/假设/风险注册表，并提供可自动检测孤立 ID 和伪造路径的机制。

Inputs: `docs/governance/*`、Milestone、Task Template。

Files allowed to change: 文档追踪校验脚本和对应测试，以及下方 `Documents to update` 的明确文档路径。

Files forbidden to change: Backend/Frontend 业务实现、Schema 语义、Solver。

Implementation steps: 审核 ID 唯一性；建立 registry parser/validator；验证 Task 引用存在；初始化矩阵到真实路径；定义关闭 PROD_OPEN 的证据格式。

Outputs: 可验证 registries、traceability report、无重复 ID。

Documentation impact: required

Documents to update: `docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、本 Task Card。

Documentation impact rationale: 本 Task 的交付本身就是注册表、追踪规则与自动一致性合同。

Change-impact matrix rows reviewed: 只修改文档；milestones/current phase；tests/fixtures（校验器测试部分）。

Traceability updates: REQ-001～015、全部已登记 NFR/ENG、TASK-P0-02 与 registry validator tests/artifact 的关系。

Schema changes: 仅文档/注册表格式；若引入 machine-readable registry，需单独版本字段。

Migration: 无。

Error behavior: duplicate/missing ID、不存在路径或非法状态导致 validation fail。

Tests: registry parse、duplicate ID、broken reference、缺失文档影响字段、diff/impact matrix 不匹配、PROD_OPEN/SIM_ASSUMPTION 混用负例。

Benchmark impact: 无。

Simulation scenarios: 无。

Acceptance commands: 运行文档/registry validator、以实际 Git diff 校验 impact matrix 覆盖，并运行相关 unit tests。

Artifacts: traceability validation report。

Explicitly excluded: 将 PLANNED TEST/ARTIFACT 伪装为已实现；关闭生产问题。

PROD_OPEN: OPEN-001～015 保持 OPEN，除非有外部权威证据。

SIM_ASSUMPTIONS: 只登记明确场景假设。

Rollback: 恢复到上一个 registry version，保留已经分配的 ID 不复用。
