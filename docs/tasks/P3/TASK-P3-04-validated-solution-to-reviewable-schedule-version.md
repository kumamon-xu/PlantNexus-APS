---
doc_id: TASK-P3-04
title: Validated Solution to Reviewable ScheduleVersion
status: planned
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [29, 30, 31, 33, 35, 65, 77, 78]
last_reviewed: 2026-08-24
---

# TASK-P3-04 — Validated Solution to Reviewable ScheduleVersion

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-007, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-HUM-001, ENG-ARCH-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P3-03

Start gate: TASK-P3-02/03=`done`且exact provider成功；用户明确授权；clean synchronized main；记录immutable Diff base；复核P2 validated PlanningSolution/ValidationReport/SolverReport/KPI固定lineage。

Goal: 将完整、fresh Validator PASS的P2 solution原子创建为immutable DRAFT，并仅在hard=0/provenance完整时推进到READY_FOR_REVIEW；PlanningRun计算状态与ScheduleVersion评审状态严格分离。

Non-goals: 不审批/驳回/发布/导出，不编辑Gantt/locks，不重跑Solver，不创建HTTP/UI。

Inputs: validated P2 output、P3 contracts/repositories、ScheduleVersion state contract、ADR-0005/0007及TASK-P3-01 accepted Workspace ADR。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `backend/app/application/schedule_versions.py`、`backend/app/domain/schedule_version.py`、相关`__init__.py`、限定unit/contract/integration tests、machine CLI及`Documents to update`；实际路径激活前逐字固定。

Files forbidden to change: Solver/Strategy/Backend/Validator公式、P2 fixtures/baselines/export bytes、Schema/migration/dependency、API/Frontend/Worker、approval/publication/export service、P4。

Implementation steps: 验证完整lineage/fresh PASS；构造content identity/new ID；repository insert DRAFT+audit；执行DRAFT→READY guard/transaction；exact replay/conflict；验证失败丢弃reviewable transition而保留诚实失败证据。

Outputs: ScheduleVersion creation/review lifecycle service、transition/audit evidence、machine report。

Documentation impact: required

Documents to update: `docs/contracts/planning-solution-and-schedule-version.md`、三份state-machine文档、`docs/domain/domain-model.md`、`docs/domain/error-model.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/planning/schedule-validator.md`、`docs/operations/observability-and-audit.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、全部governance/trace/impact/inventory必审文档、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: 首次真实ScheduleVersion行为形成，影响Validator guard、状态分离、identity/provenance、audit及错误证据。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-APPLICATION`、`IMPACT-STATE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/007/009→TASK-P3-04→TEST-SCHEDULE-VERSION-LIFECYCLE-001/TEST-STATE-TRANSITION-001/TEST-VALIDATOR-MUTATION→lifecycle report。

Schema changes: none；消费P3-02，字段不足时停止并回到新Schema版本。

Migration: none；消费P3-03 repository，不修改DDL。

Dependency changes: none。

ADR impact: implement ADR-0005/0007及TASK-P3-01 accepted Workspace ADR；若试图跳过DRAFT或允许mutable version则停止并新ADR（预期拒绝）。

State-machine impact: 首次形成DRAFT→READY_FOR_REVIEW行为；其他pair仍仅合同。REJECTED/PUBLISHED终态不得有写路径。

Error behavior: incomplete/mixed/stale validation、lineage/hash/plane冲突在状态副作用前失败；VALIDATION_FAILED不升级READY，PlanningRun COMPLETED不等于approved。

Tests: TEST-SCHEDULE-VERSION-LIFECYCLE-001、TEST-STATE-TRANSITION-001、TEST-VALIDATOR-MUTATION、TEST-SIM-ISOLATION；positive、stale/tamper/mixed/failed/replay/concurrency负例。

Benchmark impact: 记录creation/validation transaction时间作观察，不设SLA；P2 solve benchmark保持只读。

Simulation scenarios: 复用P2 correctness solution创建synthetic ScheduleVersion；不产生Production publishability。

Acceptance commands: 定向unit/contract/integration pytest与lifecycle machine CLI；full repository tests、Ruff、Pyright、locked sync；full/diff docs治理；`git diff --check`及禁止范围diff。

Artifacts: lifecycle/transition/audit report、Task report、provider artifact。

Provider evidence: exact implementation/closure required `validate`/artifact，核对fresh validation、状态计数、exact SHA、Impact/checks/issues。

Completion conditions: 只有fresh PASS/hard=0/完整provenance进入READY；DRAFT/READY immutable identity与replay稳定；负向无副作用；provider/docs闭环；无approval/publish/export/API/UI。

Failure handling: 任一Validator/lineage/transaction问题保持版本不可评审并停止后继；不得修改Validator或expected结果迎合。

Explicitly excluded: approve/reject/publish/export、manual edit/lock、HTTP/Frontend、Solver rerun、P4。

PROD_OPEN: OPEN-010保持OPEN；READY不代表任何人已被授权审批。

SIM_ASSUMPTIONS: 使用既有P2 synthetic assets且保留其version/seed/hash；不新增定量值。

Rollback: 回退application service不得删除已创建版本/audit；测试数据库可按P3-03 migration边界清理，已发布合同/历史只追加更正。
