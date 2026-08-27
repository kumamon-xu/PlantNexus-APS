---
doc_id: TASK-P4-05
title: Freeze Window and Effective Lock Projection
status: planned
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# TASK-P4-05 — Freeze Window and Effective Lock Projection

Task batch role: phase-plan-member

Requirement IDs: REQ-005, REQ-008, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-HUM-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P4-01, TASK-P4-02, TASK-P4-04

Start gate: 前序依赖全部`done`且其implementation/closure exact provider均成功；用户对TASK-P4-05另行明确授权；启动时`main=origin/main=remote main`、ahead/behind=`0/0`、working tree clean；把该时点完整40字符HEAD写入不可变Diff base；先将planned范围展开为逐字exact allow-list。

Goal: 实现versioned Simulation freeze policy与effective lock projection：COMPLETED/RUNNING/HARD不可变，freeze内按合同硬保护，SOFT保持稳定性成本输入，并以fail-closed precheck输出完整Replan Problem事实。

Non-goals: 不猜Production freeze、不计算OBJ-002、不调用Solver、不生成ChangeReport或新ScheduleVersion。

Inputs: TASK-P4-01 accepted Freeze/Stability/ChangeReport ADR、P4 event-derived Snapshot、base PUBLISHED ScheduleVersion、OPEN-005、既有C-007/C-008 contracts。

Diff base: not assigned; record the clean provider-verified 40-character HEAD only when this Task is separately authorized and activated

Files allowed to change: planning problem/policy projection、pure domain locks、formal precheck、限定unit/property/validator tests、machine report/CI及命中文档；以及`Documents to update`中的逐字路径。激活前必须把目录范围展开为exact paths。

Files forbidden to change: Schema/migration/dependency、backend objective/strategy、application Replan、Simulator/API/UI、Production defaults、P5+

Implementation steps: 固定anchor time/source/window；分类completed/running/HARD/SOFT/frozen tuples；生成solver-neutral Problem/Policy refs；拒绝冲突/缺失authority/跨plane；与formal Validator独立复验。

Outputs: `freeze-policy.v1` Simulation实例、effective lock projection与`p4-freeze-window-report.v1`。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `docs/contracts/planning-problem.md`、`docs/contracts/planning-policy-and-solve-limits.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/planning/constraint-catalog.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`、`docs/architecture/provenance-and-versioning.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/traceability-matrix.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/tasks/P4/TASK-P4-05-freeze-window-and-effective-lock-projection.md`

Documentation impact rationale: 本Task会改变其owner能力的合同/实现证据和追踪状态；所有Impact Rule必审文档须在激活前逐字确认，未修改者在Completion evidence逐项说明。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-PROBLEM`、`IMPACT-POLICY`、`IMPACT-VALIDATOR`、`IMPACT-TESTS`、`IMPACT-INFRA`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-005/008/009→freeze/effective locks→C-007/C-008→TEST-FREEZE-WINDOW-001、TEST-RUNNING、TEST-INF-LOCK、TEST-VALIDATOR-MUTATION、TEST-PROPERTY→report。

Contract impact: consumer-only；实现accepted freeze/effective-lock与既有C-007/C-008语义，Simulation policy必须versioned，Production value继续OPEN。

Schema changes: none unless P4-02-approved version requires generated bindings；历史Problem bytes必须冻结。

Migration: none。

Dependency changes: none。

ADR impact: none；实现TASK-P4-01 accepted Freeze/Stability/ChangeReport ADR。若freeze定义变化或HARD/SOFT语义偏离，先superseding ADR。

State-machine impact: none；projection不推进Request或Version state。

Error behavior: 未知版本/类型/状态/authority、重复ID不同fingerprint、stale base、跨plane、缺失provenance或任何Validator/contract失败均fail closed；不得把UNKNOWN写成INFEASIBLE、把Simulation值写成Production默认或把partial result写成成功。

Tests: TEST-FREEZE-WINDOW-001、TEST-RUNNING、TEST-INF-LOCK、TEST-VALIDATOR-MUTATION、TEST-PROPERTY。

Test IDs: TEST-FREEZE-WINDOW-001, TEST-RUNNING, TEST-INF-LOCK, TEST-VALIDATOR-MUTATION, TEST-PROPERTY

Benchmark impact: 只记录development correctness/quality/runtime/memory观察；不得建立Production capacity/SLA。若本Task不执行Benchmark，明确复用并冻结P2 XS/S/M baseline。

Simulation scenarios: 登记至少一个versioned Simulation freeze值及边界例；OPEN-005保持OPEN。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；Task-specific focused tests与machine command；完整registered pytest；必要的Frontend/Playwright/SCA/license；全部历史machine contracts与P2/P3 Gates；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-05-freeze-window-and-effective-lock-projection.md --check-diff --report build/traceability/TASK-P4-05-report.json`；`git diff --check`；相对Diff base的forbidden-scope核验。

Artifacts: `p4-freeze-window-report.v1`、frozen Problem/policy hashes、Task/provider artifact。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`；implementation与evidence-only closure必须分别绑定exact SHA的required `validate`（GitHub Actions app `15368`）、未过期artifact、Task/Diff base/Impact Rules/checks/issues一致性；失败run保留并以新corrective SHA重跑。

Completion conditions: 所有保护规则、边界时刻、跨horizon和拒绝路径可独立复验；Production无默认；no Solver/Version mutation；exact provider闭环。；文档/追踪/OPEN/SIM/risk/inventory一致；实现与evidence-only closure均经exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: 仅形成versioned Simulation freeze值；不关闭OPEN-005，不形成真实priority/authority、external integration、deployment或capacity/SLA。

P5 boundary: freeze projection不得加入secondary/tool/batch/setup/multi-factory/alternative-route或decomposition能力。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: 停止新policy版本并回退projection consumer；既有Problem/Policy evidence不可改写。

## Completion evidence

保持空白直到本Task获得独立授权并执行。计划卡不是实现、测试PASS、provider evidence或Production声明。
