---
doc_id: TASK-P3-13
title: Human Control Actions and UI E2E
status: planned
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [4, 33, 34, 66, 68, 69, 77, 78, 94]
last_reviewed: 2026-08-24
---

# TASK-P3-13 — Human Control Actions and UI E2E

Task batch role: phase-plan-member

Requirement IDs: REQ-005, REQ-006, REQ-007, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-HUM-001, ENG-ARCH-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P3-06, TASK-P3-07, TASK-P3-08, TASK-P3-09, TASK-P3-10, TASK-P3-11, TASK-P3-12

Start gate: 所有依赖`done`且provider成功；用户明确授权；clean synchronized main；记录immutable Diff base；control API和permission matrix冻结，OPEN-010仍使Production action default-deny。

Goal: 实现Gantt edit/lock、validate/new Draft、approve/reject、internal Simulation publish、export/retry/download及audit/history的human-control UI，并用Playwright验证端到端状态门和失败可见性。

Non-goals: 不修改backend业务语义，不接真实身份/MES/Production，不实现P4 Replan/ExecutionEvent/OBJ-002，不声明UAT或Production approval。

Inputs: P3 command/publication/export APIs、Gantt/read UI、approval-publication/Gantt contracts。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `frontend/src/features/schedule-actions/**`、`frontend/src/features/approval/**`、`frontend/src/features/publication/**`、`frontend/src/features/export/**`、`frontend/src/features/audit/**`、相关components/routes/tests、`frontend/e2e/**`、Playwright config/CI有界接线及`Documents to update`；实际路径激活前固定。

Files forbidden to change: backend business/API contracts、Schema/migration/dependency（除非激活前批准Playwright exact pin已在P3-11未形成）、Solver/Validator、external Production integration、P4。

Implementation steps: capability/state-sensitive controls；confirm/reason/idempotency；drag→command→new version refresh；approval/rejection/publish/export/retry；audit/history；double-submit/network retry/stale/unauthorized/invalid state/PUBLISHED mutation负例；accessible dialogs/status/errors；CI browser artifacts。

Outputs: P3 human-control UI、Playwright E2E report/traces/screenshots。

Documentation impact: required

Documents to update: 三份`docs/frontend`P3规范、`docs/contracts/planning-workspace-api.md`、`docs/contracts/authorization-and-audit.md`、`docs/contracts/export-package.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/error-model.md`、`docs/architecture/module-boundaries.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、全部governance/trace/OPEN/risk/impact/inventory必审文档、本Task卡。

Documentation impact rationale: 人工控制与全部P3用户可见副作用首次通过UI/E2E闭环，必须同步权限、状态、失败、audit和CI evidence。

Change-impact matrix rows reviewed: `IMPACT-FRONTEND`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-005/006/007/009→TASK-P3-13→TEST-WORKSPACE-FRONTEND-001/TEST-GANTT-COMMAND-001/TEST-APPROVAL-AUTHORIZATION-001/TEST-PUBLISH-IDEMPOTENCY-001/TEST-EXPORT-JOB-001/TEST-AUDIT-TRAIL-001→Playwright report。

Schema changes: none；UI严格消费API contracts。

Migration: none。

Dependency changes: none expected；Playwright必须由P3-11 exact pin；若缺失先扩卡/lock/SCA。

ADR impact: implement TASK-P3-01 accepted Workspace ADR；任何client-side authority/direct DB/API bypass或Production identity integration需新ADR并明确授权。

State-machine impact: UI只提交server command并显示结果；不得乐观伪造terminal state或提供PUBLISHED edit。

Error behavior: unauthorized/invalid state/validation fail/idempotency conflict/network retry/export fail全部明确可见且不显示成功toast；token/credential不入trace。

Tests: TEST-WORKSPACE-FRONTEND-001、TEST-GANTT-COMMAND-001、TEST-APPROVAL-AUTHORIZATION-001、TEST-PUBLISH-IDEMPOTENCY-001、TEST-EXPORT-JOB-001、TEST-AUDIT-TRAIL-001；Playwright正反全流与component/accessibility回归。

Benchmark impact: action/render/browser timing仅development observation，不设SLA。

Simulation scenarios: E2E只在isolated synthetic plane/test actor运行；Production actions必须被拒绝/隐藏。

Acceptance commands: P3-11 npm ci/lint/type/test/build；`npm --prefix frontend run test:e2e`；backend/API full regression；full/diff docs治理；`git diff --check`；backend/Schema/P4禁止diff。

Artifacts: Playwright HTML/JUnit/traces/screenshots、frontend report、Task/provider artifact。

Provider evidence: exact implementation/closure required validate/artifact；检查E2E case matrix、Task exact SHA/Impact/checks/issues、browser artifacts与required context。

Completion conditions: 全部human controls经server state/permission gates；edit产生新Version；publish/export幂等；错误诚实可见；PUBLISHED无编辑入口；provider/docs闭环；Production/P4仍blocked。

Failure handling: browser/backend结果不一致或flaky即保留trace并阻断P3-14；不得retry掩盖race或降低assertion。

Explicitly excluded: real RBAC/Production identity、MES publish、Production UAT/readiness、P4 Replan/ExecutionEvent/ChangeReport/OBJ-002。

PROD_OPEN: OPEN-002/010/012保持OPEN；UI capability demo不构成Production role/approval/publish证据。

SIM_ASSUMPTIONS: E2E data/test actor均synthetic-only，browser timing不外推Production。

Rollback: UI回退不删除server Version/audit/export；错误action只能通过新命令/更正记录处理，不能改写PUBLISHED历史。
