---
doc_id: TASK-P3-04
title: Validated Solution to Reviewable ScheduleVersion
status: in_progress
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

Diff base: 62604d05964413a0aa7f763afd720afa2d53a887

Files allowed to change: `.github/workflows/ci.yml`、`backend/app/application/__init__.py`、`backend/app/application/schedule_versions.py`、`backend/app/application/schedule_version_lifecycle_check.py`、`backend/app/domain/__init__.py`、`backend/app/domain/schedule_version.py`、`backend/tests/unit/test_schedule_version_lifecycle.py`、`backend/tests/contract/test_schedule_version_lifecycle_contract.py`、`backend/tests/integration/test_schedule_version_lifecycle.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`的逐字路径；除此以外均禁止。

Files forbidden to change: Solver/Strategy/Backend/Validator公式、P2 fixtures/baselines/export bytes、Schema/migration/dependency、API/Frontend/Worker、approval/publication/export service、P4。

Implementation steps: 验证完整lineage/fresh PASS；构造content identity/new ID；repository insert DRAFT+audit；执行DRAFT→READY guard/transaction；exact replay/conflict；验证失败丢弃reviewable transition而保留诚实失败证据。

Outputs: ScheduleVersion creation/review lifecycle service、transition/audit evidence、machine report。

Documentation impact: required

Documents to update: `docs/tasks/P3/TASK-P3-04-validated-solution-to-reviewable-schedule-version.md`、`docs/current_phase.md`、`docs/milestones/P3-planning-workspace.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/authorization-and-audit.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/domain-model.md`、`docs/domain/error-model.md`、`docs/core/glossary.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/planning/schedule-validator.md`、`docs/operations/observability-and-audit.md`、`docs/operations/README.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/adr/README.md`。

Documentation impact rationale: 首次真实ScheduleVersion行为形成，影响Validator guard、状态分离、identity/provenance、audit及错误证据。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-APPLICATION`、`IMPACT-STATE`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

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

## Activation evidence

2026-08-24在用户明确授权后，以P3-03 evidence-only closure `62604d05964413a0aa7f763afd720afa2d53a887`作为不可变Diff base启动。启动前已确认`main=origin/main`、ahead/behind=`0/0`、working tree clean；P3-03 closure run/job/artifact=`32695127644`/`97335699708`/`9508601189`均为exact SHA成功，artifact digest=`sha256:bf24e80ff999eb96cac5f32c80914218657f080ee55c26cc9eb5878800c33645`且22/22 JSON PASS、Task report为52 committed/0 working paths、7 rows、19 checks、0 issues。

启动时复用首个P2 frozen correctness case并独立重算Validator/KPI，确认Snapshot/Problem/Solution/SolverReport/ValidationReport/KPI lineage完整、ValidationReport=`PASS`且hard violations=`0`。该复核仅证明输入可消费；lifecycle service仍必须显式接收`planning_run_state=COMPLETED`，不得把P2 solver outcome `SOLVED`篡改为PlanningRun状态，也不得调用Solver。CI只增加本Task machine evidence命令，required check名称、权限、Secret、service和deployment均不变，因此显式加入`IMPACT-INFRA`及其required documents。

## Local implementation evidence

本地已形成pure domain lifecycle与ports-only application service：完整且fresh的P2 ValidationReport/KPI/SolverReport lineage先通过无副作用guard，再在单一transaction中插入immutable DRAFT、以CAS推进到`READY_FOR_REVIEW`并追加`SUBMIT_FOR_REVIEW` audit。Same key/same request精确replay；same key/different request、mixed lineage、非`COMPLETED` PlanningRun、Validator失败、plane冲突、audit冲突及并发竞争均fail closed。核心application不静态依赖Infrastructure/SQLAlchemy，service Solver调用数为0。

验收结果：定向suite=`35 passed`，full repository=`515 passed`，Ruff全通过，Pyright=`0 errors, 0 warnings`；`p3-schedule-version-lifecycle-report.v1`为8/8 PASS、1 reviewable Version、1 atomic audit、1 exact replay、5个无副作用拒绝、`issues=[]`。全部既有machine contracts、P2 vertical Gate、XS benchmark、Compose与`uv build`也PASS。Full文档治理为165 docs/30 roots/30 trace rows/48 Test IDs/15 OPEN/13 SIM assumptions/13 risks/53 Tasks；Task diff为45 paths、8 Impact rows、19 checks、0 issues。Exact implementation provider形成前Task继续`in_progress`，P3-05～15不启动。
