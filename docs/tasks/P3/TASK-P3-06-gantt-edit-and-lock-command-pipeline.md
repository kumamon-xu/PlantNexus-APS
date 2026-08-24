---
doc_id: TASK-P3-06
title: Gantt Edit and Lock Command Pipeline
status: planned
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [33, 35, 47, 48, 50, 69, 77, 78]
last_reviewed: 2026-08-24
---

# TASK-P3-06 — Gantt Edit and Lock Command Pipeline

Task batch role: phase-plan-member

Requirement IDs: REQ-005, REQ-007, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-HUM-001, ENG-ARCH-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P3-04, TASK-P3-05

Start gate: 依赖均`done`且provider成功；用户明确授权；clean synchronized main；记录immutable Diff base；P3-01 Gantt command contract与P3-02 command Schema保持冻结。

Goal: 实现Move/Assign/Lock/Unlock等明确Gantt Command→server semantic validation→新DRAFT ID→fresh independent Validator→可选READY流程，保证任何编辑都不原地修改旧Version或PUBLISHED。

Non-goals: 不重跑CP-SAT、不实现dynamic Replan/freeze/OBJ-002、不直接更新Problem/Snapshot、不审批/发布/导出、不做UI。

Inputs: immutable ScheduleVersion、workspace command contract、formal Validator、repositories/audit、ADR-0005/0007及TASK-P3-01 accepted Workspace ADR。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `backend/app/application/schedule_commands.py`、`backend/app/domain/schedule_commands.py`、相关`__init__.py`、限定unit/property/integration/validation tests、machine CLI及`Documents to update`；激活前逐字固定。

Files forbidden to change: CP-SAT Backend/Strategy/objective、Validator判断公式、PlanningProblem/Snapshot builder/hash、Schema/migration/dependency、API/Frontend、publication/export、P4 execution/replan/ChangeReport。

Implementation steps: command precheck/authorization capability carrier；copy-on-write assignment/lock；server invariant检查；新DRAFT content identity；fresh Validator；audit actor/reason/parent；exact idempotent replay/conflict；published/rejected source与invalid mutation负例。

Outputs: command pipeline、new-version lineage/audit、machine report。

Documentation impact: required

Documents to update: `docs/frontend/gantt-command-contract.md`、`docs/contracts/planning-workspace-api.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/error-model.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/planning/schedule-validator.md`、`docs/planning/replanning.md`、`docs/operations/observability-and-audit.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、全部governance/trace/impact/inventory必审文档、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: 人工编辑/lock首次成为状态命令，必须证明copy-on-write、Validator独立、audit和P3/P4分界。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-APPLICATION`、`IMPACT-STATE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-005/007/009→TASK-P3-06→TEST-GANTT-COMMAND-001/TEST-VALIDATOR-MUTATION/TEST-STATE-TRANSITION-001→command report。

Schema changes: none；消费P3-02，新增command字段必须先新Schema版本。

Migration: none；消费P3-03 repositories。

Dependency changes: none。

ADR impact: implement ADR-0005/0007及TASK-P3-01 accepted Workspace ADR；如果命令触发Solver/Replan或原地写入必须停止并提交新ADR，且仍不得提前P4。

State-machine impact: 编辑只创建新DRAFT；旧Version状态不转移，PUBLISHED/REJECTED内容不可变。DRAFT→READY仍复用P3-04 guard。

Error behavior: stale base、invalid resource/time/lock、published mutation、mixed plane、idempotency conflict、Validator FAIL均无成功副作用且返回稳定错误。

Tests: TEST-GANTT-COMMAND-001、TEST-VALIDATOR-MUTATION、TEST-STATE-TRANSITION-001、TEST-IDEMPOTENCY；含move/assign/lock/unlock、stale/replay/tamper/published负例和formula-independent Validator。

Benchmark impact: 记录command/validation latency和schedule size，仅development观察，不设SLA。

Simulation scenarios: 使用P2 versioned schedule执行命令正反例；不建立freeze/stability假设。

Acceptance commands: 定向unit/property/validation/integration tests与command machine CLI；full tests/Ruff/Pyright/locked sync；full/diff docs治理；`git diff --check`；冻结Solver/Validator/P4禁止路径diff。

Artifacts: command/validator/audit/idempotency report、Task report、provider artifact。

Provider evidence: exact implementation/closure required validate/artifact；核对old/new identities、Validator结果、Task SHA/Impact/checks/issues。

Completion conditions: 所有编辑/lock均command-only/new DRAFT/fresh Validator；old/PUBLISHED immutable；负向无副作用；docs/provider闭环；无Solver/Replan/UI。

Failure handling: Validator或identity不一致即保留失败version/audit策略定义并停止后继API/UI；不得修改Validator或旧version。

Explicitly excluded: OBJ-002/SOFT stability optimization、freeze window、ExecutionEvent/Replan/ChangeReport、approve/publish/export、Frontend。

PROD_OPEN: OPEN-005/010保持OPEN；P3 lock command不定义Production freeze或审批责任。

SIM_ASSUMPTIONS: command vectors引用既有synthetic schedule；不新增定量policy。

Rollback: 回退service不删除已产生Version/audit；错误命令结果保留可追踪失败，合同变化用新版本。
