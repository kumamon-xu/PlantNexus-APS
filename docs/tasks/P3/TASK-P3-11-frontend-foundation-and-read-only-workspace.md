---
doc_id: TASK-P3-11
title: Frontend Foundation and Read-only Workspace
status: planned
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [11, 68, 77]
last_reviewed: 2026-08-24
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

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `frontend/package.json`、`frontend/package-lock.json`、`frontend/tsconfig*.json`、`frontend/vite.config.ts`、`frontend/eslint.config.*`、`frontend/index.html`、`frontend/src/**`中foundation/read-only页面、`frontend/tests/**`、`.github/workflows/ci.yml`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`；激活前把实际glob展开为模块级明确边界。

Files forbidden to change: backend business/API semantics、Schema/migration、Python dependency/`uv.lock`、Gantt/action UI、Solver/Validator logic、Production deployment/infra、P4。

Implementation steps: exact dependency/lock/SCA review；app shell/routes/query client/generated-or-checked API types；loading/empty/error/auth-denied states；read-only pages/table virtualization/accessibility；unit/component tests；CI install/lint/type/test/build；no direct business calculation scan。

Outputs: reproducible frontend build、read-only workspace、frontend machine/CI evidence。

Documentation impact: required

Documents to update: `docs/frontend/README.md`、`docs/frontend/planning-workspace.md`、`docs/contracts/planning-workspace-api.md`、`docs/architecture/technology-stack.md`、`docs/architecture/repository-layout.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/operations/security.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、全部governance/trace/risk/impact/inventory必审文档、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: 首次Frontend/runtime dependencies/lock/CI build及用户可见页面形成。

Change-impact matrix rows reviewed: `IMPACT-FRONTEND`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-003/004/005/007/009→TASK-P3-11→TEST-WORKSPACE-FRONTEND-001/TEST-WORKSPACE-API-001→frontend build/component report。

Schema changes: none；API types由P3-02/10合同生成或逐字段验证，不新建第二套Schema。

Migration: none。

Dependency changes: required；exact frontend pins与`package-lock.json`，point-in-time audit/SCA、license/lock review；Python/uv lock保持不变。

ADR impact: P3-01应已决定Frontend/toolchain；若实际选择偏离React/TS/Ant/TanStack或引入SSR/microfrontend，先建ADR。

State-machine impact: read-only显示状态，不触发transition；未知state fail visibly。

Error behavior: HTTP/auth/contract/network/empty/stale状态分别显示且不伪造数据；不记录token/PII；Production不显示Simulation-only入口。

Tests: TEST-WORKSPACE-FRONTEND-001、TEST-WORKSPACE-API-001、accessibility/component/contract tests；后续Playwright控制流仍PLANNED。

Benchmark impact: bundle size、render/query rows和virtualization observation；不设Production SLA，阈值须经task-local development baseline。

Simulation scenarios: development UI可使用显式synthetic API fixture；Production build隐藏Simulation-only页面/seed。

Acceptance commands: `npm --prefix frontend ci`；`npm --prefix frontend run lint`；`npm --prefix frontend run typecheck`；`npm --prefix frontend test -- --run`；`npm --prefix frontend run build`；Python full gates；full/diff docs治理；`git diff --check`；lock/dependency audit命令在激活前固定。

Artifacts: frontend lock/build/test/bundle report、Task report、provider artifact。

Provider evidence: required workflow必须在exact implementation/closure SHA执行Node locked install、lint/type/component/build及既有Python gates，并上传Task/frontend报告；核对required `validate`和artifact。

Completion conditions: locked reproducible build；所有read-only页面与loading/empty/error/auth/accessibility状态形成；CI/provider/docs闭环；无Gantt/actions/业务逻辑/Production deployment。

Failure handling: dependency advisory、type/contract/accessibility/build失败阻断后继；不得跳过script或`continue-on-error`。

Explicitly excluded: Gantt/resource load/comparison、edit/lock/approve/reject/publish/export UI、real identity、Production hosting、P4。

PROD_OPEN: OPEN-010/012保持OPEN；UI不定义角色或Production performance承诺。

SIM_ASSUMPTIONS: synthetic fixture显式隔离且不进入Production build入口。

Rollback: 可回退frontend bundle/lock但保留失败audit；依赖升级用新lock与provider evidence，不手改lock；API合同不随UI回退而改写。
