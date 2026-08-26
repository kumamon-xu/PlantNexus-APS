---
doc_id: TASK-P3-16
title: Frontend Bilingual Localization and Official Terminology
status: planned
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [6, 33, 47, 48, 50, 58, 69, 73, 74, 77, 78, 94, 98, 99, 100, 101, 103, 104, 111]
last_reviewed: 2026-08-26
---

# TASK-P3-16 — Frontend Bilingual Localization and Official Terminology

Task batch role: phase-plan-member

Requirement IDs: REQ-005, REQ-006, REQ-007, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-SEC-001, NFR-OBS-001, NFR-HUM-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P3-14, TASK-P3-15

Start gate: TASK-P3-14与TASK-P3-15均为`done`，两者implementation/closure exact required `validate`与artifact已按exact SHA下载复验；用户另行明确授权执行本Task；`main=origin/main=remote main`、working tree clean；启动时即时完整40字符HEAD写入本卡并冻结为不可变Diff base。未满足任一门时保持`planned`。

Goal: 为既有P3 Planning Workspace提供`zh-CN`与`en-US`动态展示切换，默认`zh-CN`；只在浏览器本地保存非敏感locale preference；切换时同步`document.documentElement.lang`和Ant Design locale；建立强类型、版本化、覆盖可检查的术语/业务值/错误值/格式化字典。所有页面、菜单、控件、提示、确认框、表格、可访问性文本、Gantt、Resource Load、Version Comparison、Validation、Audit与human-control surface均支持双语。中文模式显示官方中文业务名称并保留原始机器代码、ID、指纹及raw UTC；英文模式保持现有正式英文语义。

Non-goals: 不修改后端、数据库、ORM、migration、Schema、OpenAPI、API route/application service、状态机、Solver、Validator、KPI公式、publication/export authority或标准成果包bytes；不增加Accept-Language服务端协商；不生成服务端中文CSV/XLSX；不实现P4、Production identity/RBAC/SSO、MES/ERP、外部publish/deployment或Production readiness。

Inputs: `official-zh-cn-terminology.v1`、既有Frontend route/component/action集合、`error-code-registry.v2`、Workspace module-local reason与HTTP映射、ScheduleVersion/ExportJob状态合同、WorkspaceView/command/allowed action/comparison change kind、C-001～C-011、现有exact-pinned Frontend dependency与P3 Gate evidence。

Diff base: set only after a future explicit execution authorization and all start gates pass; must be the immediate full 40-character HEAD

Files allowed to change: `.github/workflows/ci.yml`仅可additive增加本Task命名machine-evidence step且不得改required check名/权限/触发器；`frontend/src/i18n/locale.ts`、`frontend/src/i18n/types.ts`、`frontend/src/i18n/dictionaries/en-US.ts`、`frontend/src/i18n/dictionaries/zh-CN.ts`、`frontend/src/i18n/business-labels.ts`、`frontend/src/i18n/error-labels.ts`、`frontend/src/i18n/formatters.ts`、`frontend/src/i18n/coverage.ts`、`frontend/src/main.tsx`、`frontend/src/app/PlanningWorkspaceApp.tsx`、`frontend/src/app/context.tsx`、`frontend/src/app/state.ts`、`frontend/src/app/routeInventory.ts`、`frontend/src/components/AuthorityPanel.tsx`、`frontend/src/components/ReadOnlyTable.tsx`、`frontend/src/components/ScheduleVersionPanel.tsx`、`frontend/src/components/WorkspaceStatePanel.tsx`、`frontend/src/pages/PlanningRunPage.tsx`、`frontend/src/pages/ScheduleVersionPage.tsx`、`frontend/src/pages/ValidationPage.tsx`、`frontend/src/pages/WorkspaceCollectionPage.tsx`、`frontend/src/features/gantt/GanttPage.tsx`、`frontend/src/features/gantt/GanttTimeline.tsx`、`frontend/src/features/resource-load/ResourceLoadPage.tsx`、`frontend/src/features/version-comparison/VersionComparisonPage.tsx`、`frontend/src/features/schedule-actions/ScheduleActionsPanel.tsx`、`frontend/src/features/schedule-actions/useHumanControlAction.ts`、`frontend/src/features/approval/ApprovalPanel.tsx`、`frontend/src/features/publication/PublicationPanel.tsx`、`frontend/src/features/export/ExportPanel.tsx`、`frontend/src/features/audit/AuditHistoryPanel.tsx`、`frontend/src/styles/app.css`、`frontend/tests/i18nDictionaries.test.ts`、`frontend/tests/i18nFormatting.test.ts`、`frontend/tests/i18nWorkspace.test.tsx`、`frontend/tests/accessibility.test.tsx`、`frontend/tests/apiClient.test.ts`、`frontend/tests/commandContracts.test.ts`、`frontend/tests/ganttTimeline.test.tsx`、`frontend/tests/humanControlActions.test.tsx`、`frontend/tests/routeInventory.test.ts`、`frontend/tests/runtimeIsolation.test.ts`、`frontend/tests/visualizationContracts.test.ts`、`frontend/tests/visualizationPages.test.tsx`、`frontend/tests/workspaceStates.test.tsx`、`frontend/e2e/bilingual-localization.spec.ts`、`frontend/e2e/read-only-visualizations.spec.ts`、`frontend/e2e/human-control-actions.spec.ts`、`frontend/scripts/i18n-evidence.mjs`、`frontend/scripts/report-utils.mjs`、`docs/tasks/P3/TASK-P3-16-frontend-bilingual-localization-and-official-terminology.md`、ignored `build/validation/TASK-P3-16-frontend-i18n.json`、ignored browser/trace/traceability outputs及`Documents to update`中的明确路径。

Files forbidden to change: 除上述逐字路径外的`frontend/**`；`backend/**`、`schemas/**`、`backend/migrations/**`、fixtures/benchmarks、`frontend/package.json`、`frontend/package-lock.json`、Python/npm dependency与任一lock、API/OpenAPI/Schema/state/ADR业务源、P3-00～15历史卡/evidence、P4与Production文件。若确需新i18n dependency，必须停止并先以独立治理修订扩卡，完成exact pin/lock/SCA/license/peer compatibility审查后才可实施。

Implementation steps: 建立versioned locale context与`zh-CN`默认/本地preference恢复；绑定Ant Design `zhCN/enUS`与document lang；建立typed dictionary namespace、business/error/format映射和全量coverage assertion；把逐字列明的route/page/component/action文本迁移到key；依据`namespace + product_error.code + workspace_control_error.reason + details.reason`映射错误；用Intl显示时间/数量/秒数/利用率，同时保留raw UTC/值；增加双语unit/component/accessibility/Playwright和zero-wire-drift证据；additive接入现有required `validate` artifact。

Outputs: `official-zh-cn-terminology.v1`的可执行强类型映射、`zh-CN`默认和`en-US`切换、本地非敏感preference、完整双语UI、`p3-frontend-i18n-report.v1`与exact provider artifact。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/agents/AGENTS.md`、`docs/agents/reading-order-and-context-policy.md`、`docs/architecture/technology-stack.md`、`docs/architecture/repository-layout.md`、`docs/contracts/planning-workspace-api.md`、`docs/domain/error-model.md`、`docs/domain/state-machines/schedule-version.md`、`docs/frontend/README.md`、`docs/frontend/planning-workspace.md`、`docs/frontend/gantt-command-contract.md`、`docs/frontend/approval-publication-flow.md`、`docs/frontend/official-zh-cn-terminology-map.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`、`docs/operations/README.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/milestones/P3-planning-workspace.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、本Task卡。

Documentation impact rationale: 用户可见双语语义、错误显示、时间/单位格式、a11y与机器合同零漂移同时影响Frontend规范、API/error边界、质量门和追踪治理；官方术语文档是唯一规范源，不能由组件内散落字符串替代。

Change-impact matrix rows reviewed: `IMPACT-FRONTEND`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-005/006/007/009与所列NFR/ENG→TASK-P3-16→TEST-FRONTEND-I18N-001，并复用TEST-ERROR-MAPPING-001/TEST-WORKSPACE-API-001/TEST-WORKSPACE-FRONTEND-001/TEST-P3-VERTICAL-SLICE-001→`p3-frontend-i18n-report.v1`、Playwright与exact provider Task report；不得把planned映射写成formed evidence。

Schema changes: none；API key、document/version、enum、operationId与canonical bytes逐字冻结。

Migration: none；不得新增DDL或改变repository语义。

Dependency changes: none；优先使用仓库内typed dictionary、Ant Design现有`zhCN/enUS`locale与原生Intl，`package.json`/lock必须零差异。

ADR impact: none；展示层策略不改变server authority、wire contract或架构决策。若需要后端协商、新依赖或wire语义变化，必须停止并单独评估ADR。

State-machine impact: none；发送到API的`APPROVE`、`READY_FOR_REVIEW`等命令/状态继续为英文机器值，中文只在展示层形成label。

Error behavior: UI只按namespace、`product_error.code`、`workspace_control_error.reason`与`details.reason`本地化；未知值必须显示原始值并fail visibly，不猜测中文；后端安全英文message仅为诊断fallback，不是中文主文案；中文错误仍显示correlation ID和原始code/reason；自由文本、用户输入、ID、actor reference、业务编码与fingerprint保持原样且不机器翻译。

Tests: TEST-FRONTEND-I18N-001覆盖两个locale的页面/菜单/控件/a11y、全部注册enum/error/reason mapping、未知值raw fallback、切换与刷新preference、document lang/Ant locale、Intl与raw UTC/ID/code/JSON可审计性；关键read/visualization/command/decision/publish/export workflow双语Playwright；API request/response、canonical fingerprint、idempotency、operationId和state/command值zero drift；既有Frontend、P2 regression与P3 Gate全部保持通过。

Benchmark impact: none；只记录existing build/browser observations，不形成Production性能、browser support或SLA。

Simulation scenarios: 复用既有versioned isolated Simulation fixtures；不新增/修改/retire SIM_ASSUMPTION，不把双语显示写成真实数据/UAT证据。

Acceptance commands: 验证exact Node/npm；`npm --prefix frontend ci --ignore-scripts`；`npm --prefix frontend run lint`；`npm --prefix frontend run typecheck`；`npm --prefix frontend exec -- vitest --run`；`npm --prefix frontend run test:e2e`并至少逐locale重放关键链；`node frontend/scripts/i18n-evidence.mjs --report build/validation/TASK-P3-16-frontend-i18n.json`；`npm --prefix frontend run build`；完整Python/security与既有machine contracts；P2 XS/Gate、P3 Gate repeat≥2；`uv run python scripts/check_docs.py`；当前Task diff/report；event-base动态发现；`git diff --check`；禁止范围相对Diff base零差异。

Artifacts: `p3-frontend-i18n-report.v1`、Vitest/Playwright JSON/JUnit/HTML/trace、build/SCA/license与P2/P3 Gate regressions、`traceability-report.v1`及GitHub exact artifact；所有报告绑定exact SHA、locale dictionary version和Task。

Provider evidence: repository=`kumamon-xu/PlantNexus-APS`、branch=`main`、workflow=`PlantNexus repository gates`、required check=`validate`/GitHub Actions app `15368`；implementation exact push run/job/artifact全部success且下载复核SHA/Task/base/Impact Rules/checks/issues、i18n report、双语Playwright与wire-drift checks后才可evidence-only closure；closure exact provider再次成功前不得标`done`。失败run/artifact必须保留。

Completion conditions: `zh-CN`默认与`en-US`切换/恢复、document lang/Ant locale、所有列明surface双语、术语/enum/error完备性、未知值raw fallback、raw UTC/ID/code/fingerprint/JSON可审计性、API机器合同zero drift均由自动化证据通过；dependency/schema/migration/state/backend/standard package零差异；full/diff治理与exact provider双提交闭环；TASK-P3-17仍未自动执行。

Failure handling: 任一缺失key、未知machine value、翻译猜测、wire漂移、a11y/Playwright/P3 Gate/provider失败即保持`in_progress`并fail closed；只在本卡allow-list内修复，新增dependency/后端/Schema需求必须停止并先修订治理，不得skip、降断言、改英文wire值或伪写PASS。

Explicitly excluded: 服务端locale协商/中文载体、P4 ExecutionEvent/Replan/OBJ-002/freeze/ChangeReport、Production identity/RBAC/SSO/UAT/readiness/approval/publish/deployment、外部系统定制实现。

PROD_OPEN: OPEN-001～015全部保持`OPEN`；本地化不得关闭真实identity、business timezone、data/interface、capacity/SLA、storage或Production authority问题。

SIM_ASSUMPTIONS: SIM-ASSUMPTION-001～015全部保持`ACTIVE`；locale不改变任何Scenario/Profile/seed/hash/measurement。

Rollback: 回退本Task implementation恢复既有英文UI和原wire行为；保留官方术语规范、失败provider和历史P3 evidence。不得通过删除中文key、静默退回英文或改变API值掩盖失败。
