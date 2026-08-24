---
doc_id: TASK-P3-06
title: Gantt Edit and Lock Command Pipeline
status: done
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

Diff base: 67d38d030f8b129de7f1b2f6e5b75bd706655396

Files allowed to change: `.github/workflows/ci.yml`、`backend/app/application/__init__.py`、`backend/app/application/schedule_commands.py`、`backend/app/application/schedule_command_check.py`、`backend/app/domain/__init__.py`、`backend/app/domain/schedule_commands.py`、`backend/tests/unit/test_schedule_commands.py`、`backend/tests/property/test_schedule_command_properties.py`、`backend/tests/contract/test_schedule_command_contract.py`、`backend/tests/validation/test_schedule_command_validator_mutation.py`、`backend/tests/integration/test_schedule_command_transactions.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`的逐字路径；ignored machine report只允许写入`build/validation/ci-p3-schedule-commands.json`或本地同类路径，Task report只允许写入`build/traceability/TASK-P3-06-report.json`或CI同类路径；除此以外均禁止。

Files forbidden to change: CP-SAT Backend/Strategy/objective、Validator判断公式、PlanningProblem/Snapshot builder/hash、Schema/migration/dependency、API/Frontend、publication/export、P4 execution/replan/ChangeReport。

Implementation steps: command precheck/authorization capability carrier；copy-on-write assignment/lock；server invariant检查；新DRAFT content identity；每次非replay fresh Validator；显式`SUBMIT_FOR_REVIEW`二次fresh gate与既有DRAFT→READY CAS；audit actor/reason/parent；exact idempotent replay/conflict；published/rejected source与invalid mutation负例。

Outputs: 四类content command pipeline、显式review-submit pipeline、new-version/READY lineage与audit、machine report。

Documentation impact: required

Documents to update: `docs/tasks/P3/TASK-P3-06-gantt-edit-and-lock-command-pipeline.md`、`docs/current_phase.md`、`docs/milestones/P3-planning-workspace.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/frontend/gantt-command-contract.md`、`docs/frontend/planning-workspace.md`、`docs/contracts/planning-workspace-api.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/authorization-and-audit.md`、`docs/domain/domain-model.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/error-model.md`、`docs/core/glossary.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/planning/constraint-catalog.md`、`docs/planning/schedule-validator.md`、`docs/planning/replanning.md`、`docs/operations/README.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/adr/README.md`。

Documentation impact rationale: 人工编辑/lock首次成为状态命令，必须证明copy-on-write、Validator独立、audit和P3/P4分界。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-APPLICATION`、`IMPACT-STATE`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-005/007/009→TASK-P3-06→TEST-GANTT-COMMAND-001/TEST-VALIDATOR-MUTATION/TEST-STATE-TRANSITION-001/TEST-IDEMPOTENCY→`p3-schedule-command-report.v1`、Task report与exact provider artifacts。

Schema changes: none；消费P3-02，新增command字段必须先新Schema版本。

Migration: none；消费P3-03 repositories。

Dependency changes: none。

ADR impact: implement ADR-0005/0007及TASK-P3-01 accepted Workspace ADR；如果命令触发Solver/Replan或原地写入必须停止并提交新ADR，且仍不得提前P4。

State-machine impact: Move/Assign/Set/Remove Lock只创建新DRAFT，旧Version状态不转移，PUBLISHED/REJECTED内容不可变；独立`SUBMIT_FOR_REVIEW`仅对本Task manual/lock DRAFT复用既有DRAFT→READY pair，第二次fresh PASS后保持ID/content/fingerprint不变，decision仍空。没有新增state或pair。

Error behavior: stale base、invalid resource/time/lock、PUBLISHED原地mutation、mixed plane、idempotency conflict、Validator/lineage FAIL及CAS/audit失败均无成功副作用且返回稳定错误；失败candidate丢弃，不写成功Version/audit。

Tests: TEST-GANTT-COMMAND-001、TEST-VALIDATOR-MUTATION、TEST-STATE-TRANSITION-001、TEST-IDEMPOTENCY；含move/assign/lock/unlock/submit、same-content READY、stale/replay/tamper/published负例、insert/CAS rollback和formula-independent Validator。

Benchmark impact: 记录command/validation latency和schedule size，仅development观察，不设SLA。

Simulation scenarios: 使用P2 versioned schedule执行命令正反例；不建立freeze/stability假设。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；定向unit/property/contract/validation/integration与CI contract tests；`uv run python -m app.application.schedule_command_check --root . --report build/validation/ci-p3-schedule-commands.json`；`uv run pytest`；全部历史machine contracts、P2 Gate、XS benchmark、Compose config、`uv build`；full/diff docs治理与Task report；`git diff --check`；冻结Schema/migration/dependency/Solver/Validator/P4禁止路径diff。

Artifacts: command/validator/audit/idempotency report、Task report、provider artifact。

Provider evidence: exact implementation/closure required validate/artifact；核对old/new identities、Validator结果、Task SHA/Impact/checks/issues。

Completion conditions: 四类编辑/lock均command-only/new DRAFT/fresh Validator；显式submit second-fresh并同ID/content READY；old/PUBLISHED immutable；负向无副作用；docs/provider闭环；无Solver/Replan/UI/approval。

Local acceptance results: focused=`41 passed`；full repository=`546 passed`；`uv sync --locked`、Ruff、Pyright均PASS；`p3-schedule-command-report.v1`为8/8、5 command types、5 fresh Validator passes、2 exact replay、1 conflict、2 historical source states、6 rejected requests without side effect、Solver调用0、`issues=[]`。全部既有machine contracts、P2 Gate 11/11、XS benchmark、Compose config、`uv build`、full/diff docs、`git diff --check`前置检查均PASS；提交前Task report为57 working paths、8 Impact rows、19 checks、0 issues。上述为本地事实，最终状态由下述exact provider evidence闭环。

Failure handling: Validator、lineage、identity或transaction不一致即丢弃candidate/回滚本事务并停止后继API/UI；本Task不持久化失败Version或拒绝audit，不得修改Validator或历史Version。

Explicitly excluded: OBJ-002/SOFT stability optimization、freeze window、ExecutionEvent/Replan/ChangeReport、approve/publish/export、Frontend。

PROD_OPEN: OPEN-005/010保持OPEN；P3 lock command不定义Production freeze或审批责任。

SIM_ASSUMPTIONS: command vectors引用既有synthetic schedule；不新增定量policy。

Rollback: 代码回退不删除已提交Version/audit；未提交失败candidate本就不存在，已提交错误DRAFT只能由后续新command修订；合同变化使用新版本，不改写成功或失败历史事实。

## Implementation provider evidence

Implementation `08317637c7fbb51d46880d32523545bb0b4fe1c0`的push run `32713635045` / required `validate` job/check `97390177509`（GitHub Actions app `15368`）均为success。Artifact `9515126567`（95797 bytes）未过期，digest=`sha256:33e501d81fad861a0dba4f1f2760fb98ce0b22cf02c6ad04265174a6cb409e4e`、expiry=`2026-11-22T09:50:02Z`；下载复核25/25 JSON顶层PASS。

`ci-p3-schedule-commands.json`精确绑定implementation SHA且为8/8、5 command types（4 content + 1 submit）、5 fresh Validator passes、2 exact replay、1 conflict、2 historical source states、6 rejected requests without side effect、Solver调用0、`issues=[]`；边界为source content update=`FORBIDDEN_AND_ABSENT`、manual DRAFT READY=`EXPLICIT_CAS_SAME_CONTENT`、Production readiness=`NOT_CLAIMED`。`ci-current-task-report.json`绑定同一SHA/Diff base并记录57 committed/0 working paths、8 Impact rows、19/19 checks、0 issues。故TASK-P3-06=`done`；该结论不形成HTTP/UI、approval/rejection/publish/export、P4或Production authority/readiness，也不自动授权TASK-P3-07。
