---
doc_id: TASK-P3-13
title: Human Control Actions and UI E2E
status: in_progress
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [4, 33, 34, 66, 68, 69, 77, 78, 94]
last_reviewed: 2026-08-26
---

# TASK-P3-13 — Human Control Actions and UI E2E

## 当前已批准范围与本地实现候选

既有P3-10历史合同固定17个operation；用户于2026-08-26明确批准本Task additive增加`GET /api/v1/export-jobs/{export_job_id}/download`。该operation不是新业务carrier：只在server完成`export` capability与Job scope的pre-lookup授权后读取`SIMULATION`/`SIMULATION_INTERNAL`/`EXPORTED` v2 Job，逐字交叉验证Job attempt、ScheduleVersion reference、synthetic provenance、artifact manifest、package/storage/hash和completion audit lineage，再从root-confined flat directory生成deterministic ZIP。绝对路径、外部storage/network和Production target均禁止。

Frontend现按server `state`与`allowed_actions`显示DRAFT submit、Gantt Move/Assign/Lock、READY approve/reject、APPROVED显式确认的internal publish、PUBLISHED ExportJob create/refresh/retry/download与audit/history link。命令使用`workspace-command.v1`、canonical request fingerprint、header/body相同idempotency key和correlation；double submit被in-flight gate抑制，network/5xx unknown outcome保留原command/key/fingerprint，必须先刷新authority才允许same-request retry。PUBLISHED Gantt不渲染mutation入口。

本地Gate现已完成：Backend focused `44 passed`、全仓`607 passed`、Ruff与全量Pyright 0问题；Frontend locked install/SCA/license/lint/type、12个Vitest文件`54 passed`、build、12个Chromium E2E和`p3-frontend-human-control-report.v1` 12/12均PASS；P3 HTTP machine report为18 paths/operations/delegations并保留历史17+additive 1口径。全部required Python machine commands、P2 XS 8/8、P2 Gate 11/11且`blocking_gaps=[]`、Compose、package build、full docs及91 paths/11 Impact rows/19 checks/0 issues、`git diff --check`均PASS。Playwright首轮因缺少版本化synthetic provenance和locator竞态失败，failure trace/video/screenshot按策略保留并在修正fixture/等待条件后12/12通过。Implementation exact provider与evidence-only closure仍须完成，因此本卡保持`in_progress`，P3-14/15不得启动。

Task batch role: phase-plan-member

Requirement IDs: REQ-005, REQ-006, REQ-007, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-HUM-001, ENG-ARCH-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P3-06, TASK-P3-07, TASK-P3-08, TASK-P3-09, TASK-P3-10, TASK-P3-11, TASK-P3-12

Start gate: TASK-P3-06～12全部`done`且各closure exact provider成功；用户已明确授权TASK-P3-13，并于2026-08-26批准在发现既有17-operation HTTP合同没有成果包下载transport后进行下述有界范围扩展；`main=origin/main=3dacf83c0f0bf87a9fa673aa75d61f8ad8659386`、ahead/behind=`0/0`、working tree clean；该SHA及P3-06～12 closure ancestry/artifact已复核；control API和permission matrix冻结，OPEN-010仍使Production action default-deny。

Goal: 实现Gantt edit/lock、validate/new Draft、approve/reject、internal Simulation publish、export/retry/download及audit/history的human-control UI，并用Playwright验证端到端状态门和失败可见性。

Non-goals: 不修改ScheduleVersion/ExportJob状态pair、Solver/Validator或既有publish/export业务语义；不接真实身份、MES、外部storage/network或Production；不实现P4 Replan/ExecutionEvent/OBJ-002；不声明UAT、Production approval/readiness或external publish。

Inputs: P3 command/publication/export APIs、Gantt/read UI、approval-publication/Gantt contracts。

Diff base: 3dacf83c0f0bf87a9fa673aa75d61f8ad8659386

Files allowed to change: `backend/app/application/export_downloads.py`、`backend/app/exporters/standard_package.py`、`backend/app/jobs/export_package_store.py`、`backend/app/jobs/export_job.py`、`backend/app/api/contracts.py`、`backend/app/api/routers/planning_workspace.py`、`backend/app/api/planning_workspace_check.py`、`backend/tests/unit/test_standard_export_package.py`、`backend/tests/contract/test_planning_workspace_http_api.py`、`backend/tests/integration/test_planning_workspace_api_integration.py`、`backend/tests/security/test_planning_workspace_http_authorization.py`、`backend/tests/integration/test_ci_contract.py`、`backend/tests/integration/test_config_and_health.py`、`frontend/.env.e2e`、`frontend/playwright.config.ts`、`frontend/src/vite-env.d.ts`、`frontend/src/api/types.ts`、`frontend/src/api/canonical.ts`、`frontend/src/api/commands.ts`、`frontend/src/api/contracts.ts`、`frontend/src/api/client.ts`、`frontend/src/api/runtime.ts`、`frontend/src/app/PlanningWorkspaceApp.tsx`、`frontend/src/app/routeInventory.ts`、`frontend/src/pages/ScheduleVersionPage.tsx`、`frontend/src/features/gantt/GanttPage.tsx`、`frontend/src/features/gantt/GanttTimeline.tsx`、`frontend/src/styles/app.css`、`frontend/src/features/schedule-actions/ScheduleActionsPanel.tsx`、`frontend/src/features/schedule-actions/useHumanControlAction.ts`、`frontend/src/features/approval/ApprovalPanel.tsx`、`frontend/src/features/publication/PublicationPanel.tsx`、`frontend/src/features/export/ExportPanel.tsx`、`frontend/src/features/audit/AuditHistoryPanel.tsx`、`frontend/tests/fixtures.ts`、`frontend/tests/apiClient.test.ts`、`frontend/tests/runtimeIsolation.test.ts`、`frontend/tests/routeInventory.test.ts`、`frontend/tests/accessibility.test.tsx`、`frontend/tests/ganttTimeline.test.tsx`、`frontend/tests/visualizationPages.test.tsx`、`frontend/tests/workspaceStates.test.tsx`、`frontend/tests/commandContracts.test.ts`、`frontend/tests/humanControlActions.test.tsx`、`frontend/tests/exportDownload.test.ts`、`frontend/e2e/read-only-visualizations.spec.ts`、`frontend/e2e/human-control-actions.spec.ts`、`frontend/scripts/frontend-evidence.mjs`、`.github/workflows/ci.yml`，以及`Documents to update`逐字列出的全部路径。

- Backend bounded download transport：`backend/app/application/export_downloads.py`、`backend/app/exporters/standard_package.py`、`backend/app/jobs/export_package_store.py`、`backend/app/jobs/export_job.py`、`backend/app/api/contracts.py`、`backend/app/api/routers/planning_workspace.py`、`backend/app/api/planning_workspace_check.py`；
- Backend tests/CI contract：`backend/tests/unit/test_standard_export_package.py`、`backend/tests/contract/test_planning_workspace_http_api.py`、`backend/tests/integration/test_planning_workspace_api_integration.py`、`backend/tests/security/test_planning_workspace_http_authorization.py`、`backend/tests/integration/test_ci_contract.py`、`backend/tests/integration/test_config_and_health.py`；
- Frontend runtime/API/app：`frontend/.env.e2e`、`frontend/playwright.config.ts`、`frontend/src/vite-env.d.ts`、`frontend/src/api/types.ts`、`frontend/src/api/canonical.ts`、`frontend/src/api/commands.ts`、`frontend/src/api/contracts.ts`、`frontend/src/api/client.ts`、`frontend/src/api/runtime.ts`、`frontend/src/app/PlanningWorkspaceApp.tsx`、`frontend/src/app/routeInventory.ts`、`frontend/src/pages/ScheduleVersionPage.tsx`、`frontend/src/features/gantt/GanttPage.tsx`、`frontend/src/features/gantt/GanttTimeline.tsx`、`frontend/src/styles/app.css`；
- Frontend control modules：`frontend/src/features/schedule-actions/ScheduleActionsPanel.tsx`、`frontend/src/features/schedule-actions/useHumanControlAction.ts`、`frontend/src/features/approval/ApprovalPanel.tsx`、`frontend/src/features/publication/PublicationPanel.tsx`、`frontend/src/features/export/ExportPanel.tsx`、`frontend/src/features/audit/AuditHistoryPanel.tsx`；
- Frontend tests/evidence：`frontend/tests/fixtures.ts`、`frontend/tests/apiClient.test.ts`、`frontend/tests/runtimeIsolation.test.ts`、`frontend/tests/routeInventory.test.ts`、`frontend/tests/accessibility.test.tsx`、`frontend/tests/ganttTimeline.test.tsx`、`frontend/tests/visualizationPages.test.tsx`、`frontend/tests/workspaceStates.test.tsx`、`frontend/tests/commandContracts.test.ts`、`frontend/tests/humanControlActions.test.tsx`、`frontend/tests/exportDownload.test.ts`、`frontend/e2e/read-only-visualizations.spec.ts`、`frontend/e2e/human-control-actions.spec.ts`、`frontend/scripts/frontend-evidence.mjs`；
- Required CI/governance：`.github/workflows/ci.yml`、`README.md`及下方`Documents to update`逐字路径。

Files forbidden to change: 除上述bounded download transport外的backend业务/API实现；`schemas/**`、`backend/migrations/**`、`pyproject.toml`、`uv.lock`、`frontend/package-lock.json`及全部direct pins；domain state-machine实现、repository persistence语义、P2 package bytes、Solver/Strategy/Validator/KPI、fixture/benchmark；真实identity、external storage/network/MES/Production integration；P4+全部路径。

Implementation steps: 先保持既有17个P3-10 operation历史事实并additive新增第18个`GET /api/v1/export-jobs/{id}/download`；仅对internal Simulation `EXPORTED` Job执行pre-lookup authorization、root-confined package读取、v2 manifest/job/storage/hash/full payload复验及deterministic ZIP响应，不暴露绝对路径；再实现capability/state-sensitive controls、confirm/reason/idempotency、Gantt edit/lock→command→new Version authoritative refresh、approval/rejection/publish/export/retry/download、audit/history；覆盖double-submit、unknown network outcome same-key recovery、stale/401/403/409/422/500、invalid state、tamper/partial package及PUBLISHED mutation负例；提供accessible dialogs/status/errors与HTML/JUnit/trace/video/screenshot CI browser artifacts。

Outputs: P3 human-control UI、Playwright E2E report/traces/screenshots。

Documentation impact: required

Documents to update: `README.md`、`docs/current_phase.md`、`docs/milestones/README.md`、`docs/milestones/P3-planning-workspace.md`、`docs/tasks/README.md`、`docs/tasks/P3/TASK-P3-13-human-control-actions-and-ui-e2e.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/frontend/README.md`、`docs/frontend/planning-workspace.md`、`docs/frontend/gantt-command-contract.md`、`docs/frontend/approval-publication-flow.md`、`docs/contracts/planning-workspace-api.md`、`docs/contracts/authorization-and-audit.md`、`docs/contracts/export-package.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/error-model.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/architecture/repository-layout.md`、`docs/adr/README.md`、`docs/operations/README.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`。

Documentation impact rationale: 人工控制与全部P3用户可见副作用首次通过UI/E2E闭环，必须同步权限、状态、失败、audit和CI evidence。

Change-impact matrix rows reviewed: `IMPACT-APPLICATION`、`IMPACT-API`、`IMPACT-STATE`、`IMPACT-FRONTEND`、`IMPACT-EXPORT`、`IMPACT-JOBS`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-005/006/007/009→TASK-P3-13→TEST-WORKSPACE-FRONTEND-001/TEST-GANTT-COMMAND-001/TEST-APPROVAL-AUTHORIZATION-001/TEST-PUBLISH-IDEMPOTENCY-001/TEST-EXPORT-JOB-001/TEST-AUDIT-TRAIL-001→Playwright report。

Schema changes: none；`schedule-version.v1`、`workspace-command.v1`、`export-job.v2`、`export-manifest.v2`及全局set `2.7.0`逐字冻结；下载是HTTP binary transport，不发布新业务carrier。

Migration: none。

Dependency changes: none；复用P3-11 exact-pinned Playwright `1.62.1`、浏览器Web APIs及Python标准库`zipfile`，`package-lock.json`、24个direct pins、`pyproject.toml`和`uv.lock`必须字节不变。

ADR impact: implement TASK-P3-01 accepted Workspace ADR；任何client-side authority/direct DB/API bypass或Production identity integration需新ADR并明确授权。

State-machine impact: none；既有ScheduleVersion/ExportJob pair/version保持不变。UI只提交server command并重新读取server authority；下载只接受`EXPORTED`且verified artifact，不新增transition，不得乐观伪造terminal state或提供PUBLISHED edit。

Error behavior: unauthorized/invalid state/validation fail/idempotency conflict/network retry/export fail全部明确可见且不显示成功toast；token/credential不入trace。

Tests: TEST-WORKSPACE-FRONTEND-001、TEST-GANTT-COMMAND-001、TEST-APPROVAL-AUTHORIZATION-001、TEST-PUBLISH-IDEMPOTENCY-001、TEST-EXPORT-JOB-001、TEST-AUDIT-TRAIL-001；Playwright正反全流与component/accessibility回归。

Benchmark impact: action/render/browser timing仅development observation，不设SLA。

Simulation scenarios: E2E只在isolated synthetic plane/test actor运行；Production actions必须被拒绝/隐藏。

Acceptance commands: P3-11 npm ci/lint/type/test/build；`npm --prefix frontend run test:e2e`；backend/API full regression；full/diff docs治理；`git diff --check`；backend/Schema/P4禁止diff。

Artifacts: Playwright HTML/JUnit/traces/screenshots、frontend report、Task/provider artifact。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`的唯一required `validate`（GitHub Actions app ID `15368`）；implementation与evidence-only closure分别核对exact head SHA、push run/job conclusion、全部non-skippable steps、artifact ID/name/digest/expiry；下载并检查P3-10 additive 18-operation report、P3-13 frontend/control report、Playwright JSON/HTML/JUnit/trace/video/screenshot、Task exact SHA/Diff base/11 Impact Rules/全部checks/issues和禁止边界一致。

Completion conditions: 全部human controls经server state/permission gates；edit产生新Version；publish/export幂等；错误诚实可见；PUBLISHED无编辑入口；provider/docs闭环；Production/P4仍blocked。

Failure handling: browser/backend结果不一致或flaky即保留trace并阻断P3-14；不得retry掩盖race或降低assertion。

Explicitly excluded: real RBAC/Production identity、MES publish、Production UAT/readiness、P4 Replan/ExecutionEvent/ChangeReport/OBJ-002。

PROD_OPEN: OPEN-002/010/012保持OPEN；UI capability demo不构成Production role/approval/publish证据。

SIM_ASSUMPTIONS: 新增/登记有版本的P3-13 isolated synthetic human-control fixture与test actor假设；browser timing、mock transport和internal package download均不外推Production。

Rollback: UI回退不删除server Version/audit/export；错误action只能通过新命令/更正记录处理，不能改写PUBLISHED历史。
