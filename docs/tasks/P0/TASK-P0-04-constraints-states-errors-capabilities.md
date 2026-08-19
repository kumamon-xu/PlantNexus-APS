---
doc_id: TASK-P0-04
title: Constraints States Errors and Capabilities
status: planned
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [8, 26, 27, 30, 32, 33, 34, 91, 98]
last_reviewed: 2026-08-19
---

# TASK-P0-04 — Constraints, States, Errors and Capabilities

Requirement IDs: REQ-004, REQ-005, REQ-007, REQ-008

NFR / ENG IDs: NFR-COR-001, ENG-VAL-001, ENG-ERR-001

Depends on: TASK-P0-02, TASK-P0-03

Goal: 把 C-001～C-011、Deferred capabilities、三套状态机和产品错误分类转为可测试 rule sheet/contract skeleton。

Inputs: constraint catalog、state machine docs、error model、capability matrix。

Files allowed to change: rule/schema contracts、纯状态/错误枚举、P0 rule-sheet tests，以及下方 `Documents to update` 的明确文档路径。

Files forbidden to change: CpModel/IntervalVar、真实 Solver、审批/发布业务实现、P1 pipeline。

Implementation steps: 为每个 Constraint 定义输入、公式、positive/negative example、error/violation shape、Test ID；定义允许状态转移；定义 unsupported precheck 行为。

Outputs: Validator Rule Sheet、state transition table、error/capability contracts。

Documentation impact: required

Documents to update: `docs/core/capability-matrix.md`、`docs/domain/error-model.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/planning/constraint-catalog.md`、`docs/planning/schedule-validator.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/validator-mutation-tests.md`、`docs/contracts/schema-index.md`、`docs/governance/traceability-matrix.md`、`docs/governance/document-inventory.md`、本 Task Card。

Documentation impact rationale: Constraint、状态、错误和能力合同是规范性核心，任何可执行 rule sheet 都必须与人类文档保持双向一致。

Change-impact matrix rows reviewed: planning/validation；PlanningRun/ScheduleVersion/ExportJob；schemas；tests/fixtures；只修改文档。

Traceability updates: REQ-004/005/007/008、NFR-COR、ENG-VAL/ERR、C-001～C-018、状态/错误 tests 与 rule-sheet artifact。

Schema changes: ValidationReport/Error/State skeleton 版本化更新。

Migration: 无。

Error behavior: unsupported、invalid transition、validation violation 均保持独立类别。

Tests: rule sheet completeness、transition positive/negative、error mapping、all C-ID unique。

Benchmark impact: 无。

Simulation scenarios: future-capability examples 只验证明确拒绝。

Acceptance commands: contract/unit tests、rule sheet completeness validator。

Artifacts: machine/human-readable rule sheet、test report。

Explicitly excluded: 用任何 Solver 验证 rule sheet。

PROD_OPEN: OPEN-004/005/006/008/009。

SIM_ASSUMPTIONS: 未支持能力场景的 expected result 可为 `UNSUPPORTED_CAPABILITY`。

Rollback: 回退合同版本；不删除已分配 C-ID/状态历史。
