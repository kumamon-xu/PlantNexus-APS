---
doc_id: TASK-P3-07
title: Approval Rejection and Audit Service
status: planned
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [4, 33, 35, 66, 78, 94]
last_reviewed: 2026-08-24
---

# TASK-P3-07 — Approval Rejection and Audit Service

Task batch role: phase-plan-member

Requirement IDs: REQ-007, REQ-009

NFR / ENG IDs: NFR-TRC-001, NFR-ISO-001, NFR-SEC-001, NFR-HUM-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001, ENG-LOG-001

Depends on: TASK-P3-03, TASK-P3-04

Start gate: 依赖均`done`且provider成功；用户明确授权；clean synchronized main；记录immutable Diff base；P3-01 permission matrix和OPEN-010 default-deny边界仍有效。

Goal: 实现READY_FOR_REVIEW→APPROVED/REJECTED的capability-based human decision service、actor/reason/audit/idempotency与并发保护；Production role mapping未知时默认拒绝。

Non-goals: 不定义真实组织角色/身份提供商，不发布/导出，不编辑schedule，不实现HTTP/UI。

Inputs: permission/authorization contract、ScheduleVersion repository/state、append-only audit、ADR-0007/0009、TASK-P3-01 accepted Workspace ADR、OPEN-010。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `backend/app/application/approval.py`、`backend/app/domain/authorization.py`、相关`__init__.py`、限定unit/contract/integration/security tests、machine CLI及`Documents to update`；实际路径激活前固定。

Files forbidden to change: Schema/migration/dependency、API/Frontend、publication/export、Solver/Validator、真实RBAC/SSO adapter、P4。

Implementation steps: principal/capability/reason precheck；Simulation test policy与Production default deny；transactional approve/reject/audit；idempotent replay/conflict/CAS；invalid state/unauthorized/missing reason/concurrency负例；redaction/structured event。

Outputs: authority-neutral approval/rejection service、audit trail与machine evidence。

Documentation impact: required

Documents to update: `docs/contracts/authorization-and-audit.md`、`docs/frontend/approval-publication-flow.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/error-model.md`、`docs/architecture/data-authority.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、全部governance/trace/OPEN/risk/impact/inventory必审文档、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: human control、authorization、audit与OPEN-010边界首次形成行为证据。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-APPLICATION`、`IMPACT-STATE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-007/009→TASK-P3-07→TEST-APPROVAL-AUTHORIZATION-001/TEST-AUDIT-TRAIL-001/TEST-STATE-TRANSITION-001→decision report。

Schema changes: none；消费P3-02 actor/decision/audit合同。

Migration: none；消费P3-03 repository/audit。

Dependency changes: none；不引入身份SDK。

ADR impact: implement ADR-0007/0009及TASK-P3-01 accepted Workspace ADR；真实RBAC/identity provider选择需独立ADR和Authority，不在本Task猜测。

State-machine impact: 只实现READY_FOR_REVIEW→APPROVED/REJECTED；REJECTED终态且修订由新DRAFT，不能self-transition或回滚原行。

Error behavior: 未授权/Production无mapping/缺actor或reason/invalid state/stale version/idempotency conflict均fail closed并写允许的拒绝audit，不泄漏credential。

Tests: TEST-APPROVAL-AUTHORIZATION-001、TEST-AUDIT-TRAIL-001、TEST-STATE-TRANSITION-001、TEST-IDEMPOTENCY、TEST-SIM-ISOLATION；正反权限、reason、race、replay、redaction。

Benchmark impact: 只观察decision transaction，不形成Production SLA。

Simulation scenarios: test principal/capability仅用于Simulation；不得成为Production角色证据。

Acceptance commands: 定向unit/contract/integration/security tests与decision CLI；full tests/Ruff/Pyright/locked sync；full/diff docs治理；`git diff --check`与禁止范围diff。

Artifacts: authorization/decision/audit report、Task report、provider artifact。

Provider evidence: exact implementation/closure required validate/artifact；核对permission cases、state/audit counts、Task exact SHA/Impact/checks/issues。

Completion conditions: only READY + authorized capability可approve/reject；actor/reason/audit/idempotency/race完整；Production未知角色默认拒绝；provider/docs闭环；无publish/API/UI。

Failure handling: authorization/audit原子性失败即不改变状态并停止P3-08/10；不得临时放宽Production guard。

Explicitly excluded: 真实RBAC/SSO、Production role approval、publish/export、HTTP/Frontend、P4。

PROD_OPEN: OPEN-010保持OPEN；本Task形成capability机制，不形成角色责任closure。

SIM_ASSUMPTIONS: test actor为非定量synthetic boundary，不用于关闭OPEN。

Rollback: 回退service不得删除decision/audit；错误授权只能追加纠正记录/新Version，不改写历史。
