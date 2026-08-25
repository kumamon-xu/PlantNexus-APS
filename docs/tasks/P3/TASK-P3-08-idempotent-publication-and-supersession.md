---
doc_id: TASK-P3-08
title: Idempotent Publication and Supersession
status: in_progress
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [4, 33, 35, 66, 78, 94]
last_reviewed: 2026-08-25
---

# TASK-P3-08 — Idempotent Publication and Supersession

Task batch role: phase-plan-member

Requirement IDs: REQ-006, REQ-007, REQ-009

NFR / ENG IDs: NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-HUM-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P3-03, TASK-P3-07

Start gate: 依赖均`done`且provider成功；用户明确授权；clean synchronized main；记录immutable Diff base；OPEN-002/010仍OPEN，Production publication必须default-deny，Gate只能使用明确Simulation/internal target。

Start evidence: P3-07 evidence-only closure `a53c0f7d4a0f0bcd4e02bfeaaa0f6fc4b93157b9`的required run/job/artifact=`32794963626`/`97644228513`/`9544539992`精确success，artifact digest=`sha256:76363c5b288f39b4b38c205a16ce1ac7df41ebde62f84c05bd11c486b1f1467d`；下载26/26 JSON全部可解析，P3-07 report 8/8与Task 50 committed/0 working paths、8 rows、19 checks、0 issues。启动时main/origin/main/HEAD一致且working tree clean。

Goal: 实现仅APPROVED可进入PUBLISHED的幂等publication、current reference与旧PUBLISHED→SUPERSEDED的原子切换，保持PUBLISHED内容不可变并完整审计。

Non-goals: 不向真实MES/ERP发送，不形成Production发布批准，不导出文件，不实现HTTP/UI，不支持rollback原行。

Inputs: approval service、publication repository、ScheduleVersion/publication contracts、ADR-0007/0009、TASK-P3-01 accepted Workspace ADR、OPEN-002/010。

Diff base: a53c0f7d4a0f0bcd4e02bfeaaa0f6fc4b93157b9

Files allowed to change: `.github/workflows/ci.yml`、`backend/app/application/__init__.py`、`backend/app/application/publication.py`、`backend/app/application/publication_check.py`、`backend/app/domain/__init__.py`、`backend/app/domain/publication.py`、`backend/tests/unit/test_publication_domain.py`、`backend/tests/contract/test_publication_contract.py`、`backend/tests/integration/test_publication.py`、`backend/tests/security/test_publication_authorization.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`的逐字路径；ignored machine report只允许写入`build/validation/ci-p3-publication.json`或本地同类路径，Task report只允许写入`build/traceability/TASK-P3-08-report.json`或CI同类路径；除此以外均禁止。

Files forbidden to change: external adapters/network、Schema/migration/dependency、API/Frontend、Exporter/ExportJob、Solver/Validator、P4 rollback/replan。

Implementation steps: validate target/plane/capability/state；request fingerprint/idempotency；transactional publish/current/supersede/audit；exact replay/conflict；DRAFT/READY/REJECTED/unauthorized/synthetic-production混用/double publish/published mutation负例。

Outputs: internal/Simulation publication service、supersession/current reference、audit/idempotency report。

Documentation impact: required

Documents to update: `docs/tasks/P3/TASK-P3-08-idempotent-publication-and-supersession.md`、`docs/current_phase.md`、`docs/milestones/P3-planning-workspace.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/contracts/authorization-and-audit.md`、`docs/contracts/planning-workspace-api.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/export-package.md`、`docs/frontend/approval-publication-flow.md`、`docs/domain/domain-model.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/error-model.md`、`docs/core/glossary.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/operations/README.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/adr/README.md`。

Documentation impact rationale: 首次publication/supersession side effect改变状态、幂等、隔离、安全、审计和人工控制证据。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-APPLICATION`、`IMPACT-STATE`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-006/007/009→TASK-P3-08→TEST-PUBLISH-IDEMPOTENCY-001/TEST-APPROVAL-AUTHORIZATION-001/TEST-AUDIT-TRAIL-001/TEST-STATE-TRANSITION-001→publication report。

Schema changes: none；消费P3-02 publication result。

Migration: none；消费P3-03 transactional repositories。

Dependency changes: none；不引入network/MES SDK。

ADR impact: implement ADR-0007/0009及TASK-P3-01 accepted Workspace ADR；外部outbox/adapter或Production promotion需要独立Task/ADR/Authority。

State-machine impact: 实现APPROVED→PUBLISHED与PUBLISHED→SUPERSEDED；只有新Version成为current时才supersede，历史内容不可变。

Error behavior: 非APPROVED、unauthorized、unknown target、mixed plane、conflicting replay、concurrent publish一律无重复副作用；外部未配置不能伪装成功。

Tests: TEST-PUBLISH-IDEMPOTENCY-001、TEST-APPROVAL-AUTHORIZATION-001、TEST-AUDIT-TRAIL-001、TEST-STATE-TRANSITION-001、TEST-IDEMPOTENCY、TEST-SIM-ISOLATION。

Benchmark impact: 观察transaction/idempotency并发，不设SLA。

Simulation scenarios: 只允许显式internal Simulation target的publish state evidence；`PUBLISHED`不等于Production部署。

Acceptance commands: 定向unit/contract/integration/security/idempotency tests与publication CLI；full tests/Ruff/Pyright/locked sync；full/diff docs治理；`git diff --check`；network/external adapter禁止扫描。

Artifacts: publication/supersession/audit/idempotency report、Task report、provider artifact。

Provider evidence: exact implementation/closure required validate/artifact；核对approved-only/double-publish/current/supersede cases、Task SHA/Impact/checks/issues。

Completion conditions: DRAFT/READY/REJECTED不可publish、仅authorized APPROVED可publish、PUBLISHED immutable、重试零重复、current/supersede原子；Production仍blocked；provider/docs闭环。

Local implementation evidence: `app.domain.publication`与`app.application.publication/publication_check`形成strict PUBLISH、server authorization-before-lookup、APPROVED-only、atomic new PUBLISHED/old SUPERSEDED/current/result/audit、historical replay/conflict、rollback与concurrent current CAS。Focused=`16 passed`、full repository=`577 passed`，locked sync、Ruff、Pyright、全部历史machine、P2 Gate、XS benchmark、Compose config、`uv build`、full/diff docs、`git diff --check`与禁止范围均PASS；`p3-publication-report.v1`为8/8、3 success、2 supersession、1 replay、1 conflict、2 denial、4无业务state拒绝、1 rollback、1 concurrent winner、Solver调用0且`issues=[]`。提交前Task report为51 working paths、8 Impact rows、19 checks、0 issues。Exact implementation provider尚未形成，故Task保持`in_progress`；P3-09不启动。

Failure handling: transaction/side-effect不确定即返回失败并保持可重试，不推进状态；不得人工修改DB修绿。

Explicitly excluded: real MES/ERP publish、Production approval、file ExportJob、HTTP/UI、rollback mutation、P4。

PROD_OPEN: OPEN-002/010保持OPEN并阻止Production target；不创建closure record。

SIM_ASSUMPTIONS: internal Simulation target只用于state/idempotency tests，不代表真实发布通道。

Rollback: publication历史不可回退删除；选择历史版本只能创建新参考Version，代码回滚保持published/audit/current记录完整。
