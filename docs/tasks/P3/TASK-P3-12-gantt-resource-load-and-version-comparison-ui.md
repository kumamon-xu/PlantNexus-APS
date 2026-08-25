---
doc_id: TASK-P3-12
title: Gantt Resource Load and Version Comparison UI
status: done
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [4, 68, 69, 77, 78]
last_reviewed: 2026-08-25
---

# TASK-P3-12 — Gantt Resource Load and Version Comparison UI

Task batch role: phase-plan-member

Requirement IDs: REQ-003, REQ-004, REQ-005, REQ-007, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-TRC-001, NFR-OBS-001, NFR-PER-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P3-05, TASK-P3-10, TASK-P3-11

Start gate: 依赖均`done`且provider成功；用户明确授权；clean synchronized main；记录immutable Diff base；read-model/API fingerprints和frontend foundation冻结。

Goal: 实现virtualized Gantt、Resource Load、Order/Operation关联、KPI/diagnostics overlay与两Version comparison的read-only交互和可访问替代视图。

Non-goals: 不提交edit/lock/approve/publish/export命令，不在浏览器计算约束/可行性/KPI，不实现ChangeReport或P4。

Inputs: workspace read models/API、P3 page/Gantt contracts、frontend foundation。

Diff base: 3bca1cc10ebedc4d47227bafb2f3f66854ccb526

Activation evidence: 用户于2026-08-25明确授权执行TASK-P3-12。启动复核确认`main=origin/main=HEAD=3bca1cc10ebedc4d47227bafb2f3f66854ccb526`、ahead/behind=`0/0`且working tree clean；TASK-P3-05/10/11均为`done`且其implementation与evidence-only closure提交均为当前HEAD祖先。三项closure required run/job/artifact分别为P3-05 `32707242260`/`97370830393`/`9512779675`、P3-10 `32812850599`/`97695423162`/`9550448943`、P3-11 `32819640902`/`97714885416`/`9552720216`，均为push、`completed/success`、未过期并由GitHub Actions app `15368`提供branch protection唯一required `validate`。下载复核分别为24/29/32份可解析JSON且顶层全PASS；Task报告依次为50/51/74 committed、0 working paths，7/7/6 Impact rows、19 checks、0 issues。该HEAD因此冻结为完整Task range不可变Diff base。

Frozen consumer contracts: P3-05 read-model closure报告为8/8、14 views、Gantt 4、Resource Load 2、comparison fingerprint=`sha256:5a24b392ff6064de06f9ba8eaa5112dc66a8a8a3b6c370650706cb2a1a4145dc`且query/comparison Solver调用为0；P3-10 HTTP报告为8/8、17 paths/operations、OpenAPI fingerprint=`sha256:fbabcc5b9005f5ec22f3a6e8b6351bcf0469dbaa176682caa954191c0d697b36`，comparison只允许`POST /api/v1/schedule-version-comparisons` read-query与双Version exact precondition，不得携带Idempotency-Key或调用command端点；P3-11 closure冻结24个direct pins、Node `24.19.0`、npm `11.17.0`、`typescript-eslint=8.68.0`/`eslint=10.9.1`/`typescript=6.0.3`兼容组、13条foundation route和七种UI状态。本Task不升级任何依赖、不改lock，只在既有Playwright `1.62.1`上形成只读browser evidence。

Files allowed to change: `frontend/package.json`、`frontend/playwright.config.ts`、`frontend/scripts/frontend-evidence.mjs`、`frontend/src/api/client.ts`、`frontend/src/api/contracts.ts`、`frontend/src/api/query.ts`、`frontend/src/api/types.ts`、`frontend/src/app/PlanningWorkspaceApp.tsx`、`frontend/src/app/routeInventory.ts`、`frontend/src/app/useWorkspaceView.ts`、`frontend/src/components/WorkspaceStatePanel.tsx`、`frontend/src/pages/ScheduleVersionPage.tsx`、`frontend/src/features/gantt/GanttPage.tsx`、`frontend/src/features/gantt/GanttTimeline.tsx`、`frontend/src/features/resource-load/ResourceLoadPage.tsx`、`frontend/src/features/version-comparison/VersionComparisonPage.tsx`、`frontend/src/styles/app.css`、`frontend/tests/accessibility.test.tsx`、`frontend/tests/apiClient.test.ts`、`frontend/tests/fixtures.ts`、`frontend/tests/ganttTimeline.test.tsx`、`frontend/tests/routeInventory.test.ts`、`frontend/tests/visualizationContracts.test.ts`、`frontend/tests/visualizationPages.test.tsx`、`frontend/tests/workspaceStates.test.tsx`、`frontend/e2e/read-only-visualizations.spec.ts`、`.github/workflows/ci.yml`、`backend/tests/integration/test_ci_contract.py`及下方`Documents to update`逐字路径。以上是完整可执行allow-list；build、browser、coverage、`node_modules`、`*.tsbuildinfo`与machine reports只允许生成在ignored路径，不得提交。

Files forbidden to change: 上述单个CI contract test之外的`backend/**`、全部Schema/sample/rules、migration/database、`pyproject.toml`/`uv.lock`、`frontend/package-lock.json`及任何dependency pin、command/action UI、Solver/Validator/KPI算法、P2 fixture/benchmark/baseline、P4+与Production deployment/identity/authority。

Implementation steps: 时间轴/row virtualization；zoom/filter/select/link；resource load/order cross-highlight；comparison changed/unchanged view；server-provided KPI/diagnostic display；keyboard/screen-reader/table fallback；large synthetic render tests；no-business-logic scan。

Outputs: Gantt/resource load/comparison UI与component/visual/E2E evidence。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/milestones/README.md`、`docs/milestones/P3-planning-workspace.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P3/TASK-P3-12-gantt-resource-load-and-version-comparison-ui.md`、`docs/frontend/README.md`、`docs/frontend/planning-workspace.md`、`docs/frontend/gantt-command-contract.md`、`docs/contracts/planning-workspace-api.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/repository-layout.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/domain/state-machines/schedule-version.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`、`docs/operations/README.md`、`docs/operations/security.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/adr/README.md`。由Impact Rule要求review但无语义变化的state/replanning/Validator/Task Template/ADR允许保持零diff，完成证据必须逐项说明。

Documentation impact rationale: 核心P3可视化和版本比较改变用户信息架构、性能/可访问性与server-authority边界。

Change-impact matrix rows reviewed: `IMPACT-FRONTEND`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-003/004/005/007/009→TASK-P3-12→TEST-WORKSPACE-FRONTEND-001/TEST-WORKSPACE-READ-MODEL-001→Gantt/render/comparison report。

Schema changes: none；消费现有API payload。

Migration: none。

Dependency changes: none；使用P3-11冻结的React/Ant Design与`@playwright/test=1.62.1`，`package.json`只允许新增read-only E2E script，并让既有Vitest script显式排除`e2e/**`以避免两个runner重复收集同一Playwright spec；`package-lock.json`必须逐字不变。任何新Gantt/virtualization库或pin升级均超出本Task，必须停止并另行批准扩卡。

ADR impact: none expected；任何client-side scheduling/derived authority或new rendering architecture先ADR。

State-machine impact: read-only；显示immutable version/status，不触发transition。

Error behavior: partial/missing/too-large/invalid timestamp/unknown state显示稳定失败或fallback，不静默丢operation或推断可行。

Tests: TEST-WORKSPACE-FRONTEND-001、TEST-WORKSPACE-READ-MODEL-001；component/accessibility/virtualization/contract/read-only Playwright。

Benchmark impact: versioned synthetic row/span/render/bundle observations；只设development regression boundary，不形成Production SLA。

Simulation scenarios: 使用`VERSIONED_SYNTHETIC_UI_120@1.0.0`（SIM-ASSUMPTION-014）的120-row只读render fixture；不改变P2 Benchmark Profile或容量含义。

Acceptance commands: `npm --prefix frontend ci`；`npm --prefix frontend run audit:sca -- --report ../build/validation/ci-p3-frontend-sca.json`；`npm --prefix frontend run licenses:check -- --report ../build/validation/ci-p3-frontend-licenses.json`；`npm --prefix frontend run lint`；`npm --prefix frontend run typecheck`；`npm --prefix frontend test -- --run`；`npm --prefix frontend run build`；`npx --prefix frontend playwright install chromium`；`npm --prefix frontend run test:e2e`；`npm --prefix frontend run evidence -- --report ../build/validation/ci-p3-frontend.json`；`uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；全仓八类pytest suites；全部既有machine reports/P2 Gate/XS Benchmark；`uv build`；`docker compose --env-file .env.example config --quiet`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P3/TASK-P3-12-gantt-resource-load-and-version-comparison-ui.md --check-diff --report build/traceability/TASK-P3-12-report.json`；`git diff --check`；按Diff base核验backend业务、Schema/sample/rules、migration、dependency/lock、P2 bytes、action/P4/Production范围零差异。

Artifacts: component/E2E/accessibility/render report、screenshots/traces（失败保留）、Task/provider report。

Provider evidence: exact implementation/closure required validate/artifact；核对frontend report、Task exact SHA/Impact/checks/issues和失败trace保留策略。

Completion conditions: Gantt/load/order/comparison正确显示server facts、virtualized且可访问；无client solver/command；负向/规模/provider/docs闭环。

Failure handling: 数据错位/性能/可访问性失败阻断控制UI；不得隐藏row、降低assertion或用静态截图替代behavior。

Explicitly excluded: edit/lock/approve/reject/publish/export actions、client Solver、ChangeReport/Replan/OBJ-002、Production SLA。

PROD_OPEN: OPEN-001/003/012保持OPEN；显示不猜timezone/topology/capacity。

SIM_ASSUMPTIONS: 视图规模数据synthetic-only；若新增定量profile先登记。

Rollback: UI可回退而不改server state；已发布payload/contract不随UI回退改写，dependency lock按versioned rollback处理。

## Local implementation evidence

Implementation-time scope clarification：Playwright规范固定在Task已允许的`frontend/e2e/read-only-visualizations.spec.ts`，Vitest默认glob会误收集该文件，因此同一已允许`frontend/package.json`除新增`test:e2e`外，把既有`test`命令收紧为`vitest --exclude e2e/**`。这只分离两个既有runner的测试所有权，不改变assertion、dependency pin/lock、CI required job或产品行为；allow-list路径未扩张。

Browser-review scope clarification：真实浏览器快照发现P3-12页面复用的`WorkspaceStatePanel`仍使用Ant Design 6已弃用的`Alert.message`并产生console error。先把该单一既有组件加入allow-list，再只做语义等价的`message`→`title`兼容替换；七类状态、copy、tests、dependency与阶段边界不变，其他component路径不扩张。

截至2026-08-25，strict Gantt/Resource Load/Version Comparison payload与client、request/response query/correlation/Version-pair绑定、18条read-only route、三层Gantt、server filter/select/link、resource-load cross-link、server classification comparison、可访问完整table fallback、vertical windowing和read-only Chromium已形成。Local typecheck/lint、9个Vitest files/37 tests、build、4/4 Playwright及`p3-frontend-visualization-report.v1` 12/12 PASS；报告记录120 total/最多24 mounted rows、28 source files、1030697 JS/4106 CSS bytes、24 pins/lock零漂移与`issues=[]`。

首轮Playwright为2/4，两个strict locator因同名heading/link产生多重匹配；失败截图/video/trace保留在ignored `build/playwright/local-failure-20260825-first-run/`，断言只收紧role后4/4 PASS，没有隐藏row、跳过spec或降低业务边界。CI使用`if: always()`收集`build/playwright/**`。这些local事实在implementation provider形成前不曾被写作provider-verified；P3-13 actions、P4与Production未启动。

随后收紧response↔outbound binding时首轮Vitest为35 PASS/2 FAIL，原因是test fixture顶层correlation仍硬编码旧值；修正fixture使其回显request correlation后37/37 PASS，query/correlation/Version-pair负向断言全部保留。该本地失败不改产品阶段边界，也不得从历史中删去。

完整local acceptance另通过`npm ci`、SCA 0 advisory、336 package license/0 issue、604 Python tests、Ruff/Pyright、32/32 required validation JSON、P2 XS 8/8与vertical Gate 11/11、Compose、Python package build、165-doc full governance及55 working paths/6 Impact rows/19 checks/0 issues Task diff。最终禁止差异核对确认Schema/sample/rules、migration/database、Python/Frontend locks、Backend business/API semantics、state machine、P2 bytes、command/action、P4与Production均零违规，`package-lock.json`与Diff base blob同为`6e053d1aa2db87fb789015f0a01807f326a0749f`；当时未预填任何provider字段。

## Provider closure evidence

Implementation `a719fe5bf2c2ea2d59e1582e8f4dfd3f2674ac69`已直接push `main`。GitHub push run `32826371613`、required `validate` job/check `97735176425`（GitHub Actions app `15368`）均`completed/success`，全部53个列示job step（含post/complete）成功；branch protection仍只要求`validate`/app `15368`。

Artifact `9555196470`=`plantnexus-ci-evidence-32826371613`，`expired=false`、105525 bytes、expiry=`2026-11-23T08:23:37Z`、digest=`sha256:6c6a1f05b6f66217256cec96ad8d3f6aea547dd57c0e7ce6bc5e73b679b7279f`。下载复核33/33 JSON可解析且顶层全PASS，25份`code_commit`报告绑定同一SHA；Frontend为12/12、18 routes、7 states、4 browser specs、120/24 rows、28 source files、1030697 JS/4106 CSS bytes与`issues=[]`，Playwright为4 expected/0 unexpected/0 flaky并绑定同一SHA/run。Task report精确绑定Diff base，复现55 committed/0 working paths、六个Impact rows、19 checks、0 issues；SCA为0 advisory、license为336 packages/0 issue，P2 vertical Gate仍11/11且`blocking_gaps=[]`。

逐字范围复核确认state/replanning/Validator/Task Template/ADR由Impact Rule审阅但保持零diff；Schema/sample/rules、migration/database、Python/Frontend locks与24 pins、Backend business/API semantics、state machine、P2 fixture/baseline、command/action、P4和Production均零违规。故本evidence-only closure把TASK-P3-12标为`done`；P3 Milestone仍`active`，TASK-P3-13～15保持`planned`且未获启动授权。该证据不形成Production readiness、approval、publish、P4或外部系统能力；closure提交自身仍须按相同规则核验exact required provider。
