---
doc_id: TASK-P3-10
title: Planning Workspace HTTP API
status: planned
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [58, 63, 65, 66, 68, 77, 78, 93]
last_reviewed: 2026-08-24
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

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `backend/app/api/app.py`、`backend/app/api/contracts.py`、`backend/app/api/routers/planning_workspace.py`、`backend/app/api/dependencies/authorization.py`、对应`__init__.py`、限定contract/integration/security tests、OpenAPI/machine CLI及`Documents to update`；实际路径激活前固定。

Files forbidden to change: domain/application business semantics、Solver/Validator、Schema/migration/dependency、repository、Frontend、external identity/MES/storage adapter、P4。

Implementation steps: route/read/command mapping；Schema request/response；principal/capability injection与Production deny；HTTP error/status/idempotency；correlation/audit/no-secret；OpenAPI stability；negative auth/state/payload/mixed-plane/race tests；确保router只调用application。

Outputs: P3 HTTP API、OpenAPI/contract report、security/error evidence。

Documentation impact: required

Documents to update: `docs/contracts/planning-workspace-api.md`、`docs/contracts/authorization-and-audit.md`、`docs/frontend/planning-workspace.md`、`docs/frontend/gantt-command-contract.md`、`docs/frontend/approval-publication-flow.md`、`docs/domain/error-model.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、全部governance/trace/OPEN/risk/impact/inventory必审文档、本Task卡。

Documentation impact rationale: 首次产品API/authorization/error/OpenAPI边界影响用户行为、安全、状态门和审计。

Change-impact matrix rows reviewed: `IMPACT-API`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

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
