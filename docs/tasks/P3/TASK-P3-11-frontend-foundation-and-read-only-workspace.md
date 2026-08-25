---
doc_id: TASK-P3-11
title: Frontend Foundation and Read-only Workspace
status: done
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [11, 68, 77]
last_reviewed: 2026-08-25
---

# TASK-P3-11 — Frontend Foundation and Read-only Workspace

Task batch role: phase-plan-member

Requirement IDs: REQ-003, REQ-004, REQ-005, REQ-007, REQ-009

NFR / ENG IDs: NFR-TRC-001, NFR-ISO-001, NFR-SEC-001, NFR-OBS-001, NFR-PER-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P3-01, TASK-P3-10

Start gate: P3-01/10=`done`且provider成功；用户明确授权；clean synchronized main；记录immutable Diff base；冻结OpenAPI/payload/route；激活前在Task卡逐字确定Node/npm/React/TypeScript/Ant Design/TanStack Query/Vite/test pins与lock策略。

Goal: 建立locked React+TypeScript frontend、routing/query/error/accessibility基础，并实现Data Health、Runs、Orders、Operations、Resources、Calendars、KPI、Diagnostics、Audit的read-only workspace页面。

Non-goals: 不实现Gantt/resource load/comparison/control actions，不复制Solver/Validator逻辑，不做Production deployment/identity integration。

Inputs: P3-01 page spec、P3-10 API/OpenAPI、技术栈、Simulation/Production isolation规则。

Diff base: 26dd519b1f1f84e08d415cfdfce43f286fa82988

Activation evidence: 用户于2026-08-25明确授权执行TASK-P3-11。启动复核确认`main=origin/main=HEAD=26dd519b1f1f84e08d415cfdfce43f286fa82988`、ahead/behind=`0/0`且working tree clean；TASK-P3-01/10均为`done`。P3-01 closure `a8fcec3383ea0f8d9dca4101056aff37d7eea08c`的run/job/artifact=`32685213833`/`97308956420`/`9505465582`与P3-10 closure `26dd519b1f1f84e08d415cfdfce43f286fa82988`的`32812850599`/`97695423162`/`9550448943`均success、未过期且由GitHub Actions app `15368`提供required `validate`；下载复核分别为20/20与29/29 JSON PASS，Task报告精确为43/51 committed、0 working paths、4/7 rows、19 checks、0 issues。该HEAD因此冻结为完整Task range的不可变Diff base。

Frozen frontend toolchain and direct pins: Node=`24.19.0`、npm=`11.17.0`、lockfileVersion=`3`。Runtime direct pins为`react=19.2.8`、`react-dom=19.2.8`、`antd=6.6.1`、`@tanstack/react-query=5.102.3`、`react-router-dom=7.18.2`。Development direct pins为`typescript=6.0.3`、`vite=8.2.2`、`@vitejs/plugin-react=6.1.0`、`vitest=4.1.11`、`jsdom=30.0.1`、`eslint=10.9.1`、`typescript-eslint=8.68.0`、`eslint-plugin-react-hooks=7.1.1`、`eslint-plugin-react-refresh=0.5.4`、`globals=17.11.0`、`@types/node=24.13.3`、`@types/react=19.2.18`、`@types/react-dom=19.2.5`、`@testing-library/dom=10.4.1`、`@testing-library/react=16.3.2`、`@testing-library/jest-dom=7.0.1`、`@testing-library/user-event=14.6.6`、`axe-core=4.13.0`、`@playwright/test=1.62.1`。Playwright本Task只锁定foundation，不安装browser或形成E2E；browser控制流仍归P3-13。所有direct spec必须无range operator，npm lock只允许由npm `11.17.0`生成且禁止手改。

TypeScript ESLint approval boundary: 用户于2026-08-25明确允许采用当时latest `typescript-eslint=8.68.0`。该批准不允许浮动版本；门禁固定三方兼容组`typescript-eslint=8.68.0`、`eslint=10.9.1`、`typescript=6.0.3`，并要求TypeScript满足其`>=4.8.4 <6.1.0` peer边界。CI/lock检查必须同时拒绝range、版本漂移、peer conflict或P3-12/13未审查升级。

Files allowed to change: `frontend/.gitignore`、`frontend/.nvmrc`、`frontend/package.json`、`frontend/package-lock.json`、`frontend/tsconfig.json`、`frontend/tsconfig.app.json`、`frontend/tsconfig.node.json`、`frontend/vite.config.ts`、`frontend/eslint.config.js`、`frontend/index.html`、`frontend/scripts/report-utils.mjs`、`frontend/scripts/run-audit.mjs`、`frontend/scripts/check-licenses.mjs`、`frontend/scripts/frontend-evidence.mjs`、`frontend/src/main.tsx`、`frontend/src/vite-env.d.ts`、`frontend/src/api/canonical.ts`、`frontend/src/api/client.ts`、`frontend/src/api/contracts.ts`、`frontend/src/api/query.ts`、`frontend/src/api/runtime.ts`、`frontend/src/api/session.ts`、`frontend/src/api/types.ts`、`frontend/src/app/context.tsx`、`frontend/src/app/PlanningWorkspaceApp.tsx`、`frontend/src/app/routeInventory.ts`、`frontend/src/app/state.ts`、`frontend/src/app/useScheduleVersion.ts`、`frontend/src/components/AuthorityPanel.tsx`、`frontend/src/components/ReadOnlyTable.tsx`、`frontend/src/components/ScheduleVersionPanel.tsx`、`frontend/src/components/WorkspaceStatePanel.tsx`、`frontend/src/pages/PlanningRunPage.tsx`、`frontend/src/pages/ScheduleVersionPage.tsx`、`frontend/src/pages/ValidationPage.tsx`、`frontend/src/pages/WorkspaceCollectionPage.tsx`、`frontend/src/styles/app.css`、`frontend/tests/accessibility.test.tsx`、`frontend/tests/apiClient.test.ts`、`frontend/tests/canonical.test.ts`、`frontend/tests/fixtures.ts`、`frontend/tests/routeInventory.test.ts`、`frontend/tests/runtimeIsolation.test.ts`、`frontend/tests/setup.ts`、`frontend/tests/workspaceStates.test.tsx`、`.github/workflows/ci.yml`、`backend/tests/integration/test_ci_contract.py`及下方`Documents to update`逐字路径。目录通配表达只说明设计意图，不作为checker授权；以上逐字文件才是可执行allow-list。不得创建Gantt/resource-load/comparison/locks/action模块；build、coverage、`node_modules`、`*.tsbuildinfo`和machine reports只允许生成在ignored路径，不得提交。

Files forbidden to change: backend business/API semantics、Schema/migration、Python dependency/`uv.lock`、Gantt/action UI、Solver/Validator logic、Production deployment/infra、P4。

Implementation steps: exact dependency/lock/SCA review；app shell/routes/query client/generated-or-checked API types；loading/empty/error/auth-denied states；read-only pages/table virtualization/accessibility；unit/component tests；CI install/lint/type/test/build；no direct business calculation scan。

Local implementation evidence: exact npm `11.17.0` lockfile v3现固定5 runtime + 19 development direct pins并只解析official registry integrity；`typescript-eslint=8.68.0` lock peer逐字为TypeScript `>=4.8.4 <6.1.0`且ESLint peer包含`^10.0.0`。13条route、GET-only client、canonical query fingerprint、Version precondition、carrier/payload-reference alignment、default no-token/no-storage、raw UTC/lineage/fingerprint、seven-state UI、opaque cursor与virtual table已形成；无Gantt/load/comparison/control module。25项Vitest/component/contract/accessibility tests、typecheck、zero-warning lint、build、official npm SCA 0 advisory、336 package license review与9-check `p3-frontend-report.v1`本地PASS；bundle observation为944682 JS/1365 CSS bytes。Python全仓604项、CI contract 28项、全部历史machine/P2 Gate/XS、Compose与build也已重跑通过；full docs为165 docs/30 roots/30 trace rows/48 tests/15 OPEN/13 SIM/13 risks/53 tasks，Task diff为74 working paths/6 rows/19 checks/0 issues。该段保留提交前local事实，不替代下述provider证据。

Implementation provider evidence: implementation `567e8693db881ea3dfffa011de9021fef9641361`的唯一父提交为不可变Diff base。Push run `32818657951`（attempt 1）与required `validate` job/check `97712018632`均为`completed/success`，check由GitHub Actions app `15368`提供且branch protection继续精确要求`validate`/app `15368`。Artifact `9552386549`（`plantnexus-ci-evidence-32818657951`）未过期，size=`103338` bytes、digest=`sha256:8d558b57453db04cb32ad55d8a42ff738b215100071f2564d46d185a78631aea`、expiry=`2026-11-23T06:49:23Z`。

下载复核32/32 JSON顶层PASS且0 parse failure。Frontend报告绑定implementation SHA、TASK-P3-11与Diff base，复现9/9 checks、24 direct dependencies、13 routes、7 states、23 source files、944682/1365 JS/CSS bytes、read-only=true、browser E2E/P4/Production readiness=false及`issues=[]`；SCA为0 vulnerability，license为336 packages/0 issue。Task报告绑定同一SHA/Diff base并记录74 committed/0 working paths、6 Impact rows、19 checks、0 issues；provider log复现604 Python tests与6 files/25 Frontend tests。Completion conditions满足，故本evidence-only closure将Task标为`done`；P3-12～15仍为`planned`且未获执行授权。

Outputs: reproducible frontend build、read-only workspace、frontend machine/CI evidence。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/milestones/README.md`、`docs/milestones/P3-planning-workspace.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P3/TASK-P3-11-frontend-foundation-and-read-only-workspace.md`、`docs/frontend/README.md`、`docs/frontend/planning-workspace.md`、`docs/contracts/planning-workspace-api.md`、`docs/domain/state-machines/schedule-version.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`、`docs/architecture/technology-stack.md`、`docs/architecture/repository-layout.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/operations/README.md`、`docs/operations/security.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/adr/README.md`。被Impact Rule要求review但无语义变化的state/replanning/Validator/Template文件允许保持零diff，Completion evidence必须逐项说明。

Documentation impact rationale: 首次Frontend/runtime dependencies/lock/CI build及用户可见页面形成。

Change-impact matrix rows reviewed: `IMPACT-FRONTEND`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-003/004/005/007/009→TASK-P3-11→TEST-WORKSPACE-FRONTEND-001/TEST-WORKSPACE-API-001→frontend build/component report。

Schema changes: none；API types由P3-02/10合同生成或逐字段验证，不新建第二套Schema。

Migration: none。

Dependency changes: required；上述24个exact frontend pins与npm v3 `package-lock.json`，point-in-time SCA固定为`npm --prefix frontend run audit:sca -- --report ../build/validation/ci-p3-frontend-sca.json`，license review固定为`npm --prefix frontend run licenses:check -- --report ../build/validation/ci-p3-frontend-licenses.json`，lock复验固定为`npm --prefix frontend ci`。High/Critical advisory、未知或deny-listed license、direct range、lock drift均阻断；Python依赖与`uv.lock`保持逐字不变。

ADR impact: P3-01应已决定Frontend/toolchain；若实际选择偏离React/TS/Ant/TanStack或引入SSR/microfrontend，先建ADR。

State-machine impact: read-only显示状态，不触发transition；未知state fail visibly。

Error behavior: HTTP/auth/contract/network/empty/stale状态分别显示且不伪造数据；不记录token/PII；Production不显示Simulation-only入口。

Tests: TEST-WORKSPACE-FRONTEND-001、TEST-WORKSPACE-API-001、accessibility/component/contract tests；后续Playwright控制流仍PLANNED。

Benchmark impact: bundle size、render/query rows和virtualization observation；不设Production SLA，阈值须经task-local development baseline。

Simulation scenarios: unit/component tests只使用显式in-memory synthetic/versioned fixture；runtime loader对Simulation/Development plane fail closed，Production build与navigation没有Simulation-only页面/seed。

Acceptance commands: `npm --prefix frontend ci`；`npm --prefix frontend run audit:sca -- --report ../build/validation/ci-p3-frontend-sca.json`；`npm --prefix frontend run licenses:check -- --report ../build/validation/ci-p3-frontend-licenses.json`；`npm --prefix frontend run lint`；`npm --prefix frontend run typecheck`；`npm --prefix frontend test -- --run`；`npm --prefix frontend run build`；`npm --prefix frontend run evidence -- --report ../build/validation/ci-p3-frontend.json`；`uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；全仓八类pytest suites；全部既有machine reports/P2 Gate/XS Benchmark；`uv build`；`docker compose --env-file .env.example config --quiet`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P3/TASK-P3-11-frontend-foundation-and-read-only-workspace.md --check-diff --report build/traceability/TASK-P3-11-report.json`；`git diff --check`；按Diff base核验Schema、migration、`pyproject.toml`/`uv.lock`、backend business/API semantics、P2/v1 bytes、P3-12+、P4与Production deployment零差异。

Artifacts: frontend lock/build/test/bundle report、Task report、provider artifact。

Provider evidence: required workflow必须在exact implementation/closure SHA执行Node locked install、lint/type/component/build及既有Python gates，并上传Task/frontend报告；核对required `validate`和artifact。

Completion conditions: locked reproducible build；所有read-only页面与loading/empty/error/auth/accessibility状态形成；CI/provider/docs闭环；无Gantt/actions/业务逻辑/Production deployment。

Failure handling: dependency advisory、type/contract/accessibility/build失败阻断后继；不得跳过script或`continue-on-error`。

Explicitly excluded: Gantt/resource load/comparison、edit/lock/approve/reject/publish/export UI、real identity、Production hosting、P4。

PROD_OPEN: OPEN-010/012保持OPEN；UI不定义角色或Production performance承诺。

SIM_ASSUMPTIONS: synthetic fixture显式隔离且不进入Production build入口。

Rollback: 可回退frontend bundle/lock但保留失败audit；依赖升级用新lock与provider evidence，不手改lock；API合同不随UI回退而改写。
