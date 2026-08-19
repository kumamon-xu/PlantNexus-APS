---
doc_id: TASK-P0-07
title: Invalid Fixtures and Validator Rules
status: planned
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [30, 31, 71, 72, 86]
last_reviewed: 2026-08-19
---

# TASK-P0-07 — Invalid Fixtures and Validator Rules

Requirement IDs: REQ-005

NFR / ENG IDs: NFR-COR-001, ENG-VAL-001, ENG-ERR-001

Depends on: TASK-P0-04, TASK-P0-06

Goal: 基于 Golden Schedule 创建至少三个明确非法 Fixture，并用独立 Rule Sheet 证明能够定位相应 Constraint。

Inputs: SIM-MINIMAL-001、Constraint Catalog、ValidationReport/Error schemas。

Files allowed to change: `fixtures/infeasible/**`、rule-sheet validator（非 Solver）、validator contract tests，以及下方 `Documents to update` 的明确文档路径。

Files forbidden to change: `planning/backends/cp_sat/**`、任何 Solver、修改 Golden 正例以掩盖问题。

Implementation steps: 先实现结构化 rule evaluator；注入 missing/wrong resource、overlap/calendar、precedence/duration/lock/horizon 等错误；覆盖至少三类并规划完整 mutation set；验证 violation details。

Outputs: illegal fixtures、expected validation reports、Rule Sheet PASS report。

Documentation impact: required

Documents to update: `docs/planning/schedule-validator.md`、`docs/planning/constraint-catalog.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/fixtures-and-golden-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/traceability-matrix.md`、`docs/governance/document-inventory.md`、本 Task Card。

Documentation impact rationale: 非法 Fixture 会固定 Validator 对各 C-ID 的错误定位、报告字段和测试覆盖。

Change-impact matrix rows reviewed: planning/validation；fixtures/Golden/Mutation；tests/fixtures；只修改文档。

Traceability updates: REQ-005、NFR-COR、ENG-VAL/ERR、C-001～C-011、TEST-VALIDATOR-MUTATION 与 expected validation artifacts。

Schema changes: 仅发现 ValidationReport/Error 缺口时版本化更新。

Migration: 无。

Error behavior: 每个错误返回明确 constraint_id/entity/observed/expected；不能只返回 false。

Tests: positive Golden remains PASS；每个 mutation FAIL 且定位正确；Validator 不导入 solver module 的依赖测试。

Benchmark impact: 无。

Simulation scenarios: SIM-MINIMAL-001 mutations。

Acceptance commands: validator rule tests、dependency boundary test、fixture validation。

Artifacts: invalid packages、expected reports、coverage matrix。

Explicitly excluded: 完整 P2 ScheduleValidator 性能实现、Solver comparison。

PROD_OPEN: 无关闭。

SIM_ASSUMPTIONS: Mutation 不是业务场景事实。

Rollback: 移除新增 mutation version，不修改原始 Golden。
