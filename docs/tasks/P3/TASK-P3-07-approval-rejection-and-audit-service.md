---
doc_id: TASK-P3-07
title: Approval Rejection and Audit Service
status: done
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [4, 33, 35, 66, 78, 94]
last_reviewed: 2026-08-25
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

Diff base: 514224b8ff2d507b613797ae697245bab14f79eb

Files allowed to change: `.github/workflows/ci.yml`、`backend/app/application/__init__.py`、`backend/app/application/approval.py`、`backend/app/application/approval_decision_check.py`、`backend/app/domain/__init__.py`、`backend/app/domain/authorization.py`、`backend/tests/unit/test_authorization.py`、`backend/tests/contract/test_approval_decision_contract.py`、`backend/tests/integration/test_approval_decisions.py`、`backend/tests/security/test_approval_authorization.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`的逐字路径；ignored machine report只允许写入`build/validation/ci-p3-approval-decisions.json`或本地同类路径，Task report只允许写入`build/traceability/TASK-P3-07-report.json`或CI同类路径；除此以外均禁止。

Files forbidden to change: Schema/migration/dependency、API/Frontend、publication/export、Solver/Validator、真实RBAC/SSO adapter、P4。

Implementation steps: principal/capability/reason precheck；Simulation test policy与Production default deny；transactional approve/reject/audit；idempotent replay/conflict/CAS；invalid state/unauthorized/missing reason/concurrency负例；redaction/structured event。

Outputs: authority-neutral approval/rejection service、audit trail与machine evidence。

Documentation impact: required

Documents to update: `docs/tasks/P3/TASK-P3-07-approval-rejection-and-audit-service.md`、`docs/current_phase.md`、`docs/milestones/P3-planning-workspace.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/contracts/authorization-and-audit.md`、`docs/contracts/planning-workspace-api.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/frontend/approval-publication-flow.md`、`docs/domain/domain-model.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/error-model.md`、`docs/core/glossary.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/operations/README.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/adr/README.md`。

Documentation impact rationale: human control、authorization、audit与OPEN-010边界首次形成行为证据。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-APPLICATION`、`IMPACT-STATE`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

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

Local acceptance evidence: focused=`39 passed`、full repository=`562 passed`、Ruff/Pyright/locked sync均PASS；`p3-approval-decision-report.v1`为8/8且`issues=[]`，全部既有required machine reports、P2 Gate 11/11、XS benchmark、Compose与build均PASS。Full docs为165 docs/30 roots/30 trace rows/48 Test IDs/15 OPEN/13 SIM/13 risks/53 Tasks；Task diff为50 working paths、8 Impact rows、19 checks、0 issues，`git diff --check`与全部禁止范围均PASS。以上仅为local implementation evidence；exact implementation provider与evidence-only closure闭环前本Task保持`in_progress`。

Provider failure history: 初始implementation `3f85959e91e74966f6482426b9db296a45d715ef`的push run `32793980039` / required `validate` job `97641324105`在Linux repository tests失败，结果为`1 failed, 556 passed`且artifact因前置失败未生成。失败仅暴露machine evidence统计使用SQLite `BLOB LIKE`的跨平台差异：业务状态/audit测试均通过，但report把3个success与3个DENIED错误计为0；同时required suite未显式包含新`backend/tests/security`目录。该失败事实永久保留；修正改为解析canonical audit JSON计数并把security目录加入同一required suite。

Implementation provider evidence: corrective implementation `9aed9d8c5dd86a9a9b972f8e9c5491fd6d2dbaa6`的GitHub push run `32794370664` / required `validate` job/check `97642478274`（GitHub Actions app `15368`）均为success。Artifact `9544333991`（97281 bytes）未过期，digest=`sha256:b96ca2fe44c7dff726f67bb3b23c11017d07de71bd196c6f6cd6b93dfdb2310f`、expiry=`2026-11-23T00:37:21Z`；下载复核26/26 JSON顶层PASS。Decision report绑定exact SHA并为8/8、3 success、3 denial audit、2 replay、1 conflict、1 rollback、Solver 0、`issues=[]`；Task report绑定同一SHA/Diff base并为50 committed/0 working paths、8 Impact rows、19 checks、0 issues。因此bounded implementation满足完成条件，本evidence-only closure只写回已验证事实且不启动P3-08；closure自身仍须exact provider核验。

Failure handling: authorization/audit原子性失败即不改变状态并停止P3-08/10；不得临时放宽Production guard。

Explicitly excluded: 真实RBAC/SSO、Production role approval、publish/export、HTTP/Frontend、P4。

PROD_OPEN: OPEN-010保持OPEN；本Task形成capability机制，不形成角色责任closure。

SIM_ASSUMPTIONS: test actor为非定量synthetic boundary，不用于关闭OPEN。

Rollback: 回退service不得删除decision/audit；错误授权只能追加纠正记录/新Version，不改写历史。
