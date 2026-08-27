---
doc_id: TASK-P4-10
title: Disruption Scenario Library and Continuous Replay
status: planned
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# TASK-P4-10 — Disruption Scenario Library and Continuous Replay

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-008, REQ-009, REQ-012, REQ-013

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-OBS-001, NFR-PER-001, ENG-ARCH-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P4-05, TASK-P4-08, TASK-P4-09

Start gate: 前序依赖全部`done`且其implementation/closure exact provider均成功；用户对TASK-P4-10另行明确授权；启动时`main=origin/main=remote main`、ahead/behind=`0/0`、working tree clean；把该时点完整40字符HEAD写入不可变Diff base；先将planned范围展开为逐字exact allow-list。

Goal: 建立versioned五类连续disruption场景库：Urgent Order、Machine Failure/Recovery、Material Delay、Processing Delay、Early Completion，按同一Simulator→Event→Snapshot→Replan→Validator链重放。

Non-goals: 不修改Solver/Validator公式、不调低expected掩盖回归、不建立Production probability/distribution/capacity/SLA。

Inputs: P4 Replan application、Simulator core、P2 fixtures/benchmark profiles和明确登记的Simulation assumptions。

Diff base: not assigned; record the clean provider-verified 40-character HEAD only when this Task is separately authorized and activated

Files allowed to change: versioned simulation scenario/profile assets、fixtures calculation notes、scenario orchestration、unit/property/simulation/integration tests、machine CI及命中文档；以及`Documents to update`中的逐字路径。激活前必须把目录范围展开为exact paths。

Files forbidden to change: Schema/migration/dependency、core Planning/Validator实现、API/UI、Production data/external connector、P5 capabilities

Implementation steps: 固定scenario/version/seed/config/hash；五类事件连续推进；每步验证fact/lock/Validator/ChangeReport；same-seed semantic replay；negative/tamper/plane isolation；登记SIM assumptions。

Outputs: 五类P4 scenario assets与`p4-disruption-replay-report.v1`。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `docs/simulation/scenario-library-and-matrix.md`、`docs/simulation/scenario-spec-and-provenance.md`、`docs/simulation/execution-simulator-and-disruptions.md`、`docs/simulation/performance-gates.md`、`docs/planning/replanning.md`、`docs/quality/fixtures-and-golden-tests.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/traceability-matrix.md`、`docs/tasks/P4/TASK-P4-10-disruption-scenario-library-and-replay.md`

Documentation impact rationale: 本Task会改变其owner能力的合同/实现证据和追踪状态；所有Impact Rule必审文档须在激活前逐字确认，未修改者在Completion evidence逐项说明。

Change-impact matrix rows reviewed: `IMPACT-SIM-PROFILE`、`IMPACT-SIM-SCENARIO`、`IMPACT-SIM-EXECUTION`、`IMPACT-FIXTURE`、`IMPACT-TESTS`、`IMPACT-INFRA`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/008/009/012/013→five disruption scenarios→TEST-DISRUPTION-REPLAY-001、TEST-EXECUTION-SIMULATOR-001、TEST-REPLAN、TEST-CHANGE-REPORT-001、TEST-SCENARIO-REPLAY→report。

Contract impact: none；只消费已版本化Scenario/Event/Replan/ChangeReport contracts，新增场景配置必须登记provenance且不得改变语义。

Schema changes: none。

Migration: none。

Dependency changes: none。

ADR impact: none；scenario evidence不得改变ADR decisions。

State-machine impact: 仅通过公开Replan service执行状态；scenario harness不得直接写repository。

Error behavior: 未知版本/类型/状态/authority、重复ID不同fingerprint、stale base、跨plane、缺失provenance或任何Validator/contract失败均fail closed；不得把UNKNOWN写成INFEASIBLE、把Simulation值写成Production默认或把partial result写成成功。

Tests: TEST-DISRUPTION-REPLAY-001、TEST-EXECUTION-SIMULATOR-001、TEST-REPLAN、TEST-CHANGE-REPORT-001、TEST-SCENARIO-REPLAY、TEST-SIM-ISOLATION。

Test IDs: TEST-DISRUPTION-REPLAY-001, TEST-EXECUTION-SIMULATOR-001, TEST-REPLAN, TEST-CHANGE-REPORT-001, TEST-SCENARIO-REPLAY

Benchmark impact: 只记录development correctness/quality/runtime/memory观察；不得建立Production capacity/SLA。若本Task不执行Benchmark，明确复用并冻结P2 XS/S/M baseline。

Simulation scenarios: 上述五类各至少一个versioned连续场景，明确seed、base schedule、event count/order、freeze policy、expected invariants；数值均进入SIM registry。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；Task-specific focused tests与machine command；完整registered pytest；必要的Frontend/Playwright/SCA/license；全部历史machine contracts与P2/P3 Gates；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-10-disruption-scenario-library-and-replay.md --check-diff --report build/traceability/TASK-P4-10-report.json`；`git diff --check`；相对Diff base的forbidden-scope核验。

Artifacts: `p4-disruption-replay-report.v1`、raw event/replan/change reports、Task/provider artifact。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`；implementation与evidence-only closure必须分别绑定exact SHA的required `validate`（GitHub Actions app `15368`）、未过期artifact、Task/Diff base/Impact Rules/checks/issues一致性；失败run保留并以新corrective SHA重跑。

Completion conditions: 五类场景连续PASS且same-seed replay一致；facts/locks/Validator/ChangeReport每步完整；Production边界明确；exact provider闭环。；文档/追踪/OPEN/SIM/risk/inventory一致；实现与evidence-only closure均经exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: 场景概率、时长、tardiness、stability与runtime均为synthetic evidence，不形成Production分布、authority、integration或SLA。

P5 boundary: 五类场景不得携带P5 capability，遇到相关输入必须显式UNSUPPORTED。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: 撤下有误的新scenario version并发布后继版本；不得覆盖历史asset/hash/expected失败证据。

## Completion evidence

保持空白直到本Task获得独立授权并执行。计划卡不是实现、测试PASS、provider evidence或Production声明。
