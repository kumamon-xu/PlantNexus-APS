---
doc_id: TASK-P3-10
title: Planning Workspace HTTP API
status: done
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [58, 63, 65, 66, 68, 77, 78, 93]
last_reviewed: 2026-08-25
---

# TASK-P3-10 — Planning Workspace HTTP API

Task batch role: phase-plan-member

Requirement IDs: REQ-001, REQ-004, REQ-005, REQ-006, REQ-007, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-OBS-001, NFR-HUM-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001, ENG-LOG-001

Depends on: TASK-P3-05, TASK-P3-06, TASK-P3-07, TASK-P3-08, TASK-P3-09

Start gate: 所有依赖`done`且provider成功；用户明确授权；clean synchronized main；记录immutable Diff base；P3-01 API/permission合同、P3-02 payload Schema与OPEN-010 default-deny冻结。

Goal: 以FastAPI暴露P3 workspace read endpoints与validate/edit/lock/approve/reject/publish/export commands，提供strict payload、pagination、error mapping、correlation/audit及capability guard，且Production未配置authority时fail closed。

Non-goals: 不在router复制业务/Validator/Solver逻辑，不实现真实身份提供商或外部MES，不改变状态/Schema/DB，不构建Frontend。

Inputs: P3 query/command/application services、Schema/authorization contracts、error model、现有health/config/log基础。

Diff base: f71c4a5a11a3fac0e203e2e92198c26124755927

Files allowed to change: `.github/workflows/ci.yml`、`backend/app/api/__init__.py`、`backend/app/api/app.py`、`backend/app/api/contracts.py`、`backend/app/api/planning_workspace_check.py`、`backend/app/api/dependencies/__init__.py`、`backend/app/api/dependencies/authorization.py`、`backend/app/api/routers/__init__.py`、`backend/app/api/routers/planning_workspace.py`、`backend/tests/contract/test_planning_workspace_http_api.py`、`backend/tests/integration/test_planning_workspace_api_integration.py`、`backend/tests/security/test_planning_workspace_http_authorization.py`、`backend/tests/integration/test_ci_contract.py`、`backend/tests/integration/test_config_and_health.py`及`Documents to update`逐字列出的文档；这是在任何API实现修改前冻结的精确allow-list；首轮pytest collection在业务测试运行前发现contract/integration同名模块，故先以唯一basename替换integration路径，测试内容与范围不扩大。

Files forbidden to change: domain/application business semantics、Solver/Validator、Schema/migration/dependency、repository、Frontend、external identity/MES/storage adapter、P4。

Implementation steps: route/read/command mapping；Schema request/response；principal/capability injection与Production deny；HTTP error/status/idempotency；correlation/audit/no-secret；OpenAPI stability；negative auth/state/payload/mixed-plane/race tests；确保router只调用application。

Outputs: P3 HTTP API、OpenAPI/contract report、security/error evidence。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/milestones/README.md`、`docs/milestones/P3-planning-workspace.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P3/TASK-P3-10-planning-workspace-http-api.md`、`docs/contracts/README.md`、`docs/contracts/planning-workspace-api.md`、`docs/contracts/authorization-and-audit.md`、`docs/frontend/planning-workspace.md`、`docs/frontend/gantt-command-contract.md`、`docs/frontend/approval-publication-flow.md`、`docs/domain/error-model.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/operations/README.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/adr/README.md`。

Documentation impact rationale: 首次产品API/authorization/error/OpenAPI边界影响用户行为、安全、状态门和审计。

Change-impact matrix rows reviewed: `IMPACT-API`、`IMPACT-STATE`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-001/004/005/006/007/009→TASK-P3-10→TEST-WORKSPACE-API-001/TEST-ERROR-MAPPING-001/TEST-APPROVAL-AUTHORIZATION-001/TEST-SIM-ISOLATION→OpenAPI/API report。

Schema changes: none；HTTP只序列化P3-02合同；OpenAPI不得成为第二套不一致Schema。

Migration: none。

Dependency changes: none expected；复用locked FastAPI/httpx；身份SDK明确排除。

ADR impact: implement ADR-0002/0009及TASK-P3-01 accepted Workspace ADR；API gateway/identity provider/async topology变化需新ADR。

State-machine impact: router不得自行转移状态；application service结果是唯一权威，invalid state映射明确。

Error behavior: 七类产品错误与auth/idempotency/invalid state映射为非500稳定响应；unknown exception sanitization；Production authority缺失拒绝；UNKNOWN不等于INFEASIBLE。

Tests: TEST-WORKSPACE-API-001、TEST-ERROR-MAPPING-001、TEST-APPROVAL-AUTHORIZATION-001、TEST-PUBLISH-IDEMPOTENCY-001、TEST-EXPORT-JOB-001、TEST-SIM-ISOLATION、TEST-OBS-001。

Benchmark impact: API payload/query latency只作development observation；无Production rate/SLA。

Simulation scenarios: API integration使用显式Simulation plane/test principal，不开放Production Simulation API。

Acceptance commands: 定向contract/integration/security API tests与OpenAPI report；full tests/Ruff/Pyright/locked sync；full/diff docs治理；`git diff --check`；AST no-business-logic与禁止范围检查。

Artifacts: OpenAPI fingerprint、API/error/auth report、Task report、provider artifact。

Provider evidence: exact implementation/closure required validate/artifact；核对route/OpenAPI/auth cases、Task exact SHA/Impact/checks/issues。

Completion conditions: 所有P3 read/command endpoints严格映射合同和application；权限/错误/idempotency/audit/plane guard完整；无router业务逻辑或Production authority猜测；provider/docs闭环。

Failure handling: contract/auth/state mismatch保持HTTP失败且无副作用，停止Frontend后继；不得返回200+error或吞500。

Explicitly excluded: OAuth/OIDC/SSO/RBAC角色落地、real MES/storage、Frontend、P4 endpoints、Production deployment。

PROD_OPEN: OPEN-002/010/015保持OPEN；API capability机制不形成Production角色或外部接口closure。

SIM_ASSUMPTIONS: integration actor/data仅synthetic；不成为Production入口。

Rollback: API路由可回退且不改业务历史；已发布payload/OpenAPI变化走versioned compatibility，不静默破坏consumer。

## Local implementation evidence

- 17个`/api/v1` operation、stable operation IDs、strict query/command/path/header binding、single application-port delegation、server-derived authorization、Production pre-provider default-deny、sanitized error/correlation/denial audit及thin-router边界已实现。
- `uv run python -m app.api.planning_workspace_check --root . --report build/validation/local-p3-planning-workspace-api.json`为8/8 PASS，17 paths/17 delegations、8 mapped errors、Production provider/application调用0、router state/Solver/Validator调用0、`issues=[]`。
- Contract/integration/security/health/CI focused suite为41 PASS；最终full repository为603 PASS，required当前29份JSON evidence、P2 Gate 11/11、XS benchmark 8/8、locked sync、Ruff/Pyright、Compose/build、full/diff docs均PASS。
- Schema、migration、dependency/lock、domain/application/repository、Frontend、P4与Production零修改；OPEN-002/010/015保持OPEN。
- Implementation provider evidence: implementation `4958ce5759812331f13fab2608fbec37f1f1ff76`的GitHub push run `32812163430` / required `validate` job/check `97693443111`（GitHub Actions app `15368`）均为success，所有steps通过。Artifact `9550224090`（101191 bytes）未过期，digest=`sha256:d8577d6429167d8782622722d4d64fb993e2db07cbca43a4f279bfd0ba3b9ecf`、expiry=`2026-11-23T05:16:01Z`；下载复核29/29 JSON顶层PASS。API report绑定exact SHA并为8/8、17 paths/operation IDs/delegations、8 mapped errors、Production provider/application调用0、router state/Solver/Validator调用0、`issues=[]`；Task report绑定同一SHA/Diff base并为51 committed/0 working paths、7 Impact rows、19 checks、0 issues。因此bounded implementation满足完成条件，本evidence-only closure只写回已验证事实且不启动P3-11；closure自身仍须exact provider核验。

## Local failure and recovery record

首轮full repository为601 PASS/1 FAIL；失败是本Task禁止修改的P3-09 `test_standard_package_is_byte_deterministic_and_preserves_p2_payloads`，同一进程的两次XLSX package hash瞬时不同。P3-10 diff未触及exporter/package/schema/dependency；该exact test随后独立连续5次PASS，完整suite重跑为602 PASS，API安全fail-closed加固后最终full为603 PASS。因未再现且不在冻结allow-list内，本Task未改写P3-09实现；若provider再次失败，必须停止closure并单独治理，不得在P3-10偷渡修正。
