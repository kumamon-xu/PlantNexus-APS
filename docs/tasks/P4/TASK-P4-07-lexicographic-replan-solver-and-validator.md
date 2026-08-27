---
doc_id: TASK-P4-07
title: Lexicographic Replan Solver and Validator
status: planned
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# TASK-P4-07 — Lexicographic Replan Solver and Validator

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-008, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-OBS-001, NFR-PER-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P4-04, TASK-P4-05, TASK-P4-06

Start gate: 前序依赖全部`done`且其implementation/closure exact provider均成功；用户对TASK-P4-07另行明确授权；启动时`main=origin/main=remote main`、ahead/behind=`0/0`、working tree clean；把该时点完整40字符HEAD写入不可变Diff base；先将planned范围展开为逐字exact allow-list。

Goal: 在冻结Replan Problem上实现Delivery→Stability→Makespan词典序多轮CP-SAT，保持事实/锁约束并让每轮candidate通过fresh independent Validator与ChangeReport复核。

Non-goals: 不做decomposition、rolling/hybrid、不改变OR-Tools版本、不接受混合权重、不创建ScheduleVersion/Request事务、不设Production SLA。

Inputs: P2 Global CP-SAT/Validator、P4 freeze projection、OBJ-002/ChangeReport pure components和versioned Simulation Policy/Limits。

Diff base: not assigned; record the clean provider-verified 40-character HEAD only when this Task is separately authorized and activated

Files allowed to change: `backend/app/planning/backends/cp_sat/**`、`backend/app/planning/strategies/**`、有界policy/reporting/validation integration、tests/machine CI及命中文档；以及`Documents to update`中的逐字路径。激活前必须把目录范围展开为exact paths。

Files forbidden to change: Schema/migration/dependency/lock、event repository/application、Simulator/scenarios、API/UI、publication/export、P5 capabilities

Implementation steps: 按stage冻结前一轮最优/可接受界；记录每轮value/bound/gap/budget/stop；复用完整C-001～C-011模型；fresh Validator/ChangeReport；limits/UNKNOWN/INFEASIBLE诚实映射；tiny oracle/property/replay。

Outputs: P4 lexicographic strategy与`p4-replan-solver-report.v1`。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `docs/planning/objective-policy.md`、`docs/planning/planning-strategies.md`、`docs/planning/solver-backend-contract.md`、`docs/planning/schedule-validator.md`、`docs/planning/replanning.md`、`docs/domain/kpi-contract.md`、`docs/quality/benchmark-regression.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/architecture/technology-stack.md`、`docs/adr/README.md`、`docs/governance/traceability-matrix.md`、`docs/tasks/P4/TASK-P4-07-lexicographic-replan-solver-and-validator.md`

Documentation impact rationale: 本Task会改变其owner能力的合同/实现证据和追踪状态；所有Impact Rule必审文档须在激活前逐字确认，未修改者在Completion evidence逐项说明。

Change-impact matrix rows reviewed: `IMPACT-POLICY`、`IMPACT-STRATEGY`、`IMPACT-BACKEND`、`IMPACT-VALIDATOR`、`IMPACT-REPORTING`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/008/009→lexicographic strategy→OBJ-001/002/003+C-001～C-011→TEST-REPLAN、TEST-STABILITY-OBJECTIVE-001、TEST-VALIDATOR-MUTATION、TEST-SOLVER-UPGRADE、TEST-PROPERTY→solver report。

Contract impact: consumer-only；落实P4-02 Policy/SolverReport与既有Constraint/Validator合同，objective顺序和honest status不得私自变化。

Schema changes: none；消费P4-02 Policy/SolverReport versions。

Migration: none。

Dependency changes: none；`ortools==9.15.6755`与`uv.lock`冻结，升级需新ADR和完整Gate。

ADR impact: none；落实ADR-0004、ADR-0005、ADR-0006、ADR-0011及TASK-P4-01 accepted Freeze/Stability/ChangeReport ADR。任何decomposition或objective顺序变化须superseding ADR。

State-machine impact: PlanningRun只使用既有计算状态或P4-01批准映射；不创建ScheduleVersion。

Error behavior: 未知版本/类型/状态/authority、重复ID不同fingerprint、stale base、跨plane、缺失provenance或任何Validator/contract失败均fail closed；不得把UNKNOWN写成INFEASIBLE、把Simulation值写成Production默认或把partial result写成成功。

Tests: TEST-REPLAN、TEST-STABILITY-OBJECTIVE-001、TEST-VALIDATOR-MUTATION、TEST-PROPERTY、TEST-SOLVER-UPGRADE、TEST-INF-LOCK/RUNNING。

Test IDs: TEST-REPLAN, TEST-STABILITY-OBJECTIVE-001, TEST-VALIDATOR-MUTATION, TEST-PROPERTY, TEST-SOLVER-UPGRADE

Benchmark impact: 只记录development correctness/quality/runtime/memory观察；不得建立Production capacity/SLA。若本Task不执行Benchmark，明确复用并冻结P2 XS/S/M baseline。

Simulation scenarios: tiny exhaustive与fixed replan pairs；连续disruption在P4-10/14。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；Task-specific focused tests与machine command；完整registered pytest；必要的Frontend/Playwright/SCA/license；全部历史machine contracts与P2/P3 Gates；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-07-lexicographic-replan-solver-and-validator.md --check-diff --report build/traceability/TASK-P4-07-report.json`；`git diff --check`；相对Diff base的forbidden-scope核验。

Artifacts: `p4-replan-solver-report.v1`、stage raw reports、Task/provider artifact。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`；implementation与evidence-only closure必须分别绑定exact SHA的required `validate`（GitHub Actions app `15368`）、未过期artifact、Task/Diff base/Impact Rules/checks/issues一致性；失败run保留并以新corrective SHA重跑。

Completion conditions: 三阶段顺序与等价锁定可证明；事实/锁/Validator/ChangeReport全PASS；status/budget诚实；dependency零漂移；exact provider闭环。；文档/追踪/OPEN/SIM/risk/inventory一致；实现与evidence-only closure均经exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: solve timing/quality仅为Development/Benchmark observation，不形成Production optimality、capacity/SLA、authority或external integration。

P5 boundary: 禁止decomposition、rolling/hybrid、多工厂、alternative route、secondary resource、batch、sequence setup与tool/fixture capacity。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: feature entry停用后回到P2 single-stage strategy；保留所有P4 SolverReport，不覆盖历史。

## Completion evidence

保持空白直到本Task获得独立授权并执行。计划卡不是实现、测试PASS、provider evidence或Production声明。
