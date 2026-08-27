---
doc_id: TASK-P4-13
title: Replanning Workspace UI and Browser E2E
status: planned
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# TASK-P4-13 — Replanning Workspace UI and Browser E2E

Task batch role: phase-plan-member

Requirement IDs: REQ-005, REQ-006, REQ-007, REQ-008, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-TRC-001, NFR-ISO-001, NFR-SEC-001, NFR-OBS-001, NFR-PER-001, NFR-HUM-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P4-09, TASK-P4-10, TASK-P4-11, TASK-P4-12

Start gate: 前序依赖全部`done`且其implementation/closure exact provider均成功；用户对TASK-P4-13另行明确授权；启动时`main=origin/main=remote main`、ahead/behind=`0/0`、working tree clean；把该时点完整40字符HEAD写入不可变Diff base；先将planned范围展开为逐字exact allow-list。

Goal: 在既有双语Planning Workspace中展示event timeline、Replan请求/状态、freeze边界、before/after tardiness/stability、ChangeReport和explicit actions，以浏览器E2E证明server authority与失败恢复。

Non-goals: 不在client计算事实/locks/Validator/OBJ-002、不直接控制Simulator或数据库、不新增Production authority/external publish/deployment。

Inputs: P4 API/read models/output、P3 typed i18n/official terminology/Gantt/human-control foundation。

Diff base: not assigned; record the clean provider-verified 40-character HEAD only when this Task is separately authorized and activated

Files allowed to change: `frontend/**`中精确P4 feature/test路径、browser fixtures/Playwright evidence、可选既有CI additive steps及命中文档；以及`Documents to update`中的逐字路径。激活前必须把目录范围展开为exact paths。

Files forbidden to change: backend/schema/migration/Python dependency、frontend package/lock unless separately approved、server business/state、external integration、P5+

Implementation steps: typed API adapter；event/replan/change panels；freeze/status/raw value/unknown fallback；confirm/retry/authority refresh；accessible bilingual views；browser positive/negative/tamper/network replay；wire zero drift。

Outputs: P4 replanning UI与`p4-replanning-frontend-report.v1`/Playwright evidence。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `docs/frontend/README.md`、`docs/frontend/planning-workspace.md`、`docs/frontend/approval-publication-flow.md`、`docs/frontend/official-zh-cn-terminology-map.md`、`docs/planning/replanning.md`、`docs/domain/state-machines/schedule-version.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/traceability-matrix.md`、`docs/governance/sim-assumption-register.md`、`docs/tasks/P4/TASK-P4-13-replanning-workspace-ui-and-browser-e2e.md`

Documentation impact rationale: 本Task会改变其owner能力的合同/实现证据和追踪状态；所有Impact Rule必审文档须在激活前逐字确认，未修改者在Completion evidence逐项说明。

Change-impact matrix rows reviewed: `IMPACT-FRONTEND`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-005/006/007/008/009→P4 UI→TEST-REPLAN-FRONTEND-001、TEST-REPLAN-API-001、TEST-WORKSPACE-FRONTEND-001、TEST-FRONTEND-I18N-001、TEST-CHANGE-REPORT-001→frontend/Playwright reports。

Contract impact: display/interaction-only；消费P4-12 OpenAPI与既有官方双语display contract，英文path/key/enum/error/fingerprint保持零漂移。

Schema changes: none；英文machine contracts零漂移。

Migration: none。

Dependency changes: none expected；package/lock冻结。若需新依赖先停止、扩卡、exact pin/SCA/license/peer/ADR review。

ADR impact: none；沿用ADR-0012、TASK-P4-01 accepted Freeze/Stability/ChangeReport与Execution Simulator Common-Path ADR及existing frontend stack。

State-machine impact: UI只显示server state/allowed_actions，不自行推进或推断。

Error behavior: 未知版本/类型/状态/authority、重复ID不同fingerprint、stale base、跨plane、缺失provenance或任何Validator/contract失败均fail closed；不得把UNKNOWN写成INFEASIBLE、把Simulation值写成Production默认或把partial result写成成功。

Tests: TEST-REPLAN-FRONTEND-001、TEST-REPLAN-API-001、TEST-WORKSPACE-FRONTEND-001、TEST-FRONTEND-I18N-001、TEST-CHANGE-REPORT-001、accessibility/Playwright。

Test IDs: TEST-REPLAN-FRONTEND-001, TEST-REPLAN-API-001, TEST-WORKSPACE-FRONTEND-001, TEST-FRONTEND-I18N-001, TEST-CHANGE-REPORT-001

Benchmark impact: 只记录development correctness/quality/runtime/memory观察；不得建立Production capacity/SLA。若本Task不执行Benchmark，明确复用并冻结P2 XS/S/M baseline。

Simulation scenarios: P4-10五类场景的browser-readable结果；E2E fixture显式Simulation且进入SIM registry。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；Task-specific focused tests与machine command；完整registered pytest；必要的Frontend/Playwright/SCA/license；全部历史machine contracts与P2/P3 Gates；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-13-replanning-workspace-ui-and-browser-e2e.md --check-diff --report build/traceability/TASK-P4-13-report.json`；`git diff --check`；相对Diff base的forbidden-scope核验。

Artifacts: `p4-replanning-frontend-report.v1`、Playwright JSON/JUnit/HTML/screenshot/trace/video、Task/provider artifact。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`；implementation与evidence-only closure必须分别绑定exact SHA的required `validate`（GitHub Actions app `15368`）、未过期artifact、Task/Diff base/Impact Rules/checks/issues一致性；失败run保留并以新corrective SHA重跑。

Completion conditions: 双语/a11y/unknown raw/server authority/positive-negative/unknown-outcome E2E PASS；wire/dependency零漂移；exact provider闭环。；文档/追踪/OPEN/SIM/risk/inventory一致；实现与evidence-only closure均经exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: test actor/UI controls不形成真实identity/approval authority、external publish、deployment、UAT或browser capacity/SLA。

P5 boundary: UI不得显示P5能力为available，也不得对未支持输入提供近似控制。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: 隐藏P4 routes/features并保留P3 UI；不删除server/event/replan历史。

## Completion evidence

保持空白直到本Task获得独立授权并执行。计划卡不是实现、测试PASS、provider evidence或Production声明。
