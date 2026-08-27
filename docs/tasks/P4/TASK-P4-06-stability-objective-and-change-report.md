---
doc_id: TASK-P4-06
title: OBJ-002 Stability and ChangeReport
status: planned
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# TASK-P4-06 — OBJ-002 Stability and ChangeReport

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-008, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-OBS-001, NFR-HUM-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P4-01, TASK-P4-02

Start gate: 前序依赖全部`done`且其implementation/closure exact provider均成功；用户对TASK-P4-06另行明确授权；启动时`main=origin/main=remote main`、ahead/behind=`0/0`、working tree clean；把该时点完整40字符HEAD写入不可变Diff base；先将planned范围展开为逐字exact allow-list。

Goal: 实现独立、整数、可重放的OBJ-002 stability计算和ChangeReport builder/completeness validator，比较base/new assignment、资源变化、start shift、changed count、锁/事实保护及before/after tardiness。

Non-goals: 不修改CP-SAT objective、不编排Replan、不发布/导出、不把报告变成approval或Production KPI。

Inputs: TASK-P4-01 accepted Freeze/Stability/ChangeReport ADR、P4-02 carriers、base/new Problem/ScheduleVersion与既有KPI公式。

Diff base: not assigned; record the clean provider-verified 40-character HEAD only when this Task is separately authorized and activated

Files allowed to change: planning reporting/policy pure calculations、domain ChangeReport values、限定unit/property/contract tests、machine evidence/CI及命中文档；以及`Documents to update`中的逐字路径。激活前必须把目录范围展开为exact paths。

Files forbidden to change: Schema/migration/dependency、CP-SAT model/strategy、application/API/UI/Simulator、P3 publication state、P5+

Implementation steps: 定义stability components/units/canonical ordering；独立计算base/new delta与reasons；验证facts/locks completeness；deterministic ID/hash；negative/mutation/property replay。

Outputs: OBJ-002 calculator、ChangeReport builder/validator与`p4-stability-change-report.v1`。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `docs/planning/objective-policy.md`、`docs/planning/replanning.md`、`docs/domain/kpi-contract.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/export-package.md`、`docs/architecture/provenance-and-versioning.md`、`docs/quality/property-tests.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/traceability-matrix.md`、`docs/tasks/P4/TASK-P4-06-stability-objective-and-change-report.md`

Documentation impact rationale: 本Task会改变其owner能力的合同/实现证据和追踪状态；所有Impact Rule必审文档须在激活前逐字确认，未修改者在Completion evidence逐项说明。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-POLICY`、`IMPACT-REPORTING`、`IMPACT-TESTS`、`IMPACT-INFRA`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/008/009→OBJ-002/ChangeReport→TEST-STABILITY-OBJECTIVE-001、TEST-CHANGE-REPORT-001、TEST-PROPERTY、TEST-VALIDATOR-MUTATION→report/provider。

Contract impact: consumer-only；实现P4-02 Policy/ChangeReport carrier与accepted整数stability/completeness语义，禁止私有权重或字段。

Schema changes: none；消费P4-02 ChangeReport/Policy carrier。

Migration: none。

Dependency changes: none。

ADR impact: none；严格实现TASK-P4-01 accepted Freeze/Stability/ChangeReport ADR，禁止混合浮点权重。

State-machine impact: none。

Error behavior: 未知版本/类型/状态/authority、重复ID不同fingerprint、stale base、跨plane、缺失provenance或任何Validator/contract失败均fail closed；不得把UNKNOWN写成INFEASIBLE、把Simulation值写成Production默认或把partial result写成成功。

Tests: TEST-STABILITY-OBJECTIVE-001、TEST-CHANGE-REPORT-001、TEST-PROPERTY、TEST-VALIDATOR-MUTATION。

Test IDs: TEST-STABILITY-OBJECTIVE-001, TEST-CHANGE-REPORT-001, TEST-PROPERTY, TEST-VALIDATOR-MUTATION

Benchmark impact: 只记录development correctness/quality/runtime/memory观察；不得建立Production capacity/SLA。若本Task不执行Benchmark，明确复用并冻结P2 XS/S/M baseline。

Simulation scenarios: fixed base/new pairs覆盖zero-change、resource change、shift、unavoidable change与tamper；不运行Simulator。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；Task-specific focused tests与machine command；完整registered pytest；必要的Frontend/Playwright/SCA/license；全部历史machine contracts与P2/P3 Gates；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-06-stability-objective-and-change-report.md --check-diff --report build/traceability/TASK-P4-06-report.json`；`git diff --check`；相对Diff base的forbidden-scope核验。

Artifacts: `p4-stability-change-report.v1`、golden delta vectors、Task/provider artifact。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`；implementation与evidence-only closure必须分别绑定exact SHA的required `validate`（GitHub Actions app `15368`）、未过期artifact、Task/Diff base/Impact Rules/checks/issues一致性；失败run保留并以新corrective SHA重跑。

Completion conditions: stability/ChangeReport独立于Solver且确定；facts/locks、tardiness与reason completeness可拒绝缺失/篡改；exact provider闭环。；文档/追踪/OPEN/SIM/risk/inventory一致；实现与evidence-only closure均经exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: stability权重与tardiness对比仅为Simulation证据，不形成Production KPI target、priority、approval、external integration或SLA。

P5 boundary: ChangeReport不得暗含P5 capability approximation或相关优化成本。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: 移除尚未被Replan消费的calculator版本；已发布ChangeReport只能由后继版本纠正。

## Completion evidence

保持空白直到本Task获得独立授权并执行。计划卡不是实现、测试PASS、provider evidence或Production声明。
