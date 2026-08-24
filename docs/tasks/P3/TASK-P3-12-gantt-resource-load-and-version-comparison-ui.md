---
doc_id: TASK-P3-12
title: Gantt Resource Load and Version Comparison UI
status: planned
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [4, 68, 69, 77, 78]
last_reviewed: 2026-08-24
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

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `frontend/src/features/gantt/**`、`frontend/src/features/resource-load/**`、`frontend/src/features/version-comparison/**`、相关routes/components/tests、Playwright read-only specs（若tooling已由P3-11形成）及`Documents to update`；激活前固定实际路径。

Files forbidden to change: backend/Schema/migration/dependency lock（除非激活前批准必要Gantt库exact pin）、command/action UI、Solver/Validator/KPI算法、P4。

Implementation steps: 时间轴/row virtualization；zoom/filter/select/link；resource load/order cross-highlight；comparison changed/unchanged view；server-provided KPI/diagnostic display；keyboard/screen-reader/table fallback；large synthetic render tests；no-business-logic scan。

Outputs: Gantt/resource load/comparison UI与component/visual/E2E evidence。

Documentation impact: required

Documents to update: `docs/frontend/README.md`、`docs/frontend/planning-workspace.md`、`docs/frontend/gantt-command-contract.md`、`docs/contracts/planning-workspace-api.md`、`docs/architecture/module-boundaries.md`、`docs/domain/state-machines/schedule-version.md`、`docs/planning/schedule-validator.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、全部governance/trace/risk/impact/inventory必审文档、本Task卡。

Documentation impact rationale: 核心P3可视化和版本比较改变用户信息架构、性能/可访问性与server-authority边界。

Change-impact matrix rows reviewed: `IMPACT-FRONTEND`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-003/004/005/007/009→TASK-P3-12→TEST-WORKSPACE-FRONTEND-001/TEST-WORKSPACE-READ-MODEL-001→Gantt/render/comparison report。

Schema changes: none；消费现有API payload。

Migration: none。

Dependency changes: none expected；若Gantt/virtualization新库不可避免，必须在activation前exact pin、lock/SCA并增加IMPACT/ADR审查。

ADR impact: none expected；任何client-side scheduling/derived authority或new rendering architecture先ADR。

State-machine impact: read-only；显示immutable version/status，不触发transition。

Error behavior: partial/missing/too-large/invalid timestamp/unknown state显示稳定失败或fallback，不静默丢operation或推断可行。

Tests: TEST-WORKSPACE-FRONTEND-001、TEST-WORKSPACE-READ-MODEL-001；component/accessibility/virtualization/contract/read-only Playwright。

Benchmark impact: versioned synthetic row/span/render/bundle observations；只设development regression boundary，不形成Production SLA。

Simulation scenarios: 使用P2/P3 synthetic XS/S/M-like view数据但不改变Benchmark Profile或容量含义。

Acceptance commands: P3-11 npm locked/lint/type/test/build命令；read-only Playwright suite；Python/API contract回归；full/diff docs治理；`git diff --check`；backend/action/P4禁止diff。

Artifacts: component/E2E/accessibility/render report、screenshots/traces（失败保留）、Task/provider report。

Provider evidence: exact implementation/closure required validate/artifact；核对frontend report、Task exact SHA/Impact/checks/issues和失败trace保留策略。

Completion conditions: Gantt/load/order/comparison正确显示server facts、virtualized且可访问；无client solver/command；负向/规模/provider/docs闭环。

Failure handling: 数据错位/性能/可访问性失败阻断控制UI；不得隐藏row、降低assertion或用静态截图替代behavior。

Explicitly excluded: edit/lock/approve/reject/publish/export actions、client Solver、ChangeReport/Replan/OBJ-002、Production SLA。

PROD_OPEN: OPEN-001/003/012保持OPEN；显示不猜timezone/topology/capacity。

SIM_ASSUMPTIONS: 视图规模数据synthetic-only；若新增定量profile先登记。

Rollback: UI可回退而不改server state；已发布payload/contract不随UI回退改写，dependency lock按versioned rollback处理。
