---
doc_id: TASK-P4-01
title: Dynamic Replanning Contract and ADR Baseline
status: planned
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# TASK-P4-01 — Dynamic Replanning Contract and ADR Baseline

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-007, REQ-008, REQ-009, REQ-013

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-SEC-001, NFR-HUM-001, ENG-ARCH-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P4-00

Start gate: 前序依赖全部`done`且其implementation/closure exact provider均成功；用户对TASK-P4-01另行明确授权；启动时`main=origin/main=remote main`、ahead/behind=`0/0`、working tree clean；把该时点完整40字符HEAD写入不可变Diff base；先将planned范围展开为逐字exact allow-list。

Goal: 在任何P4 Schema、migration或代码前，冻结ExecutionEvent→权威事实→新Snapshot→ReplanRequest→lexicographic Solver→fresh Validator→new ScheduleVersion/ChangeReport的语义、事务、状态和Simulation隔离决定，并形成三份新的accepted ADR。

Non-goals: 不发布Schema、不建表、不实现事件、Solver、Simulator、API或UI；不选择Production freeze、真实authority、external target、capacity或SLA。

Inputs: P4 Milestone、总规§35/47～50/79～80、ADR-0001/0002/0005/0006/0007/0009/0012、P3 provider-verified closure与P4-00规划基线。

Diff base: not assigned; record the clean provider-verified 40-character HEAD only when this Task is separately authorized and activated

Files allowed to change: `docs/adr/`下三份future ADR（ExecutionEvent Authority / Fact Projection / Replan Lineage、Freeze / Stability / ChangeReport、Deterministic Execution Simulator Common-Path）及启动时扩展后的精确合同/架构/领域/规划/仿真/质量/治理文档 allow-list；stable ID/filename必须在激活时经registry precheck分配，且在任何文件修改前把目录范围展开为exact paths；以及`Documents to update`中的逐字路径。

Files forbidden to change: `backend/**`、`schemas/**`、`frontend/**`、`fixtures/**`、`benchmarks/**`、`infra/**`、`.github/workflows/**`、`pyproject.toml`、`uv.lock`、migration、P0～P3历史事实和P5+文档

Implementation steps: 审查既有合同缺口；分别决定事件/事实投影与Replan lineage、freeze/OBJ-002/ChangeReport、Simulator共同路径；明确是否需要ReplanRequest状态机及事务边界；同步合同和追踪；只运行文档治理。

Outputs: 三份新accepted ADR（使用启动时分配的next stable IDs）与一致的人类合同；后继Schema、migration和实现的唯一语义输入。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `docs/adr/README.md`、`docs/contracts/execution-events-and-replan-request.md`、`docs/contracts/planning-policy-and-solve-limits.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/export-package.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/simulation-first-dual-channel.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/domain/kpi-contract.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/planning/objective-policy.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`、`docs/simulation/execution-simulator-and-disruptions.md`、`docs/governance/traceability-matrix.md`、`docs/governance/risk-register.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/P4/TASK-P4-01-dynamic-replanning-contract-and-adr-baseline.md`

Documentation impact rationale: 本Task会改变其owner能力的合同/实现证据和追踪状态；所有Impact Rule必审文档须在激活前逐字确认，未修改者在Completion evidence逐项说明。

Change-impact matrix rows reviewed: `IMPACT-STATE`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-008/009/013与相关NFR/ENG→本Task→三份ADR/合同→TEST-EXECUTION-EVENT-CONTRACT-001、TEST-REPLAN-REQUEST-CONTRACT-001、TEST-FREEZE-WINDOW-001、TEST-STABILITY-OBJECTIVE-001、TEST-CHANGE-REPORT-001→未来provider artifact。

Contract impact: required；形成ExecutionEvent/ReplanRequest/freeze/OBJ-002/ChangeReport/Simulator的人类规范、compatibility、authority、transaction、error与rollback边界，但不发布机器carrier。

Schema changes: none；只登记TASK-P4-02预期additive P4 schema set和兼容策略，不创建或改写任何Schema。

Migration: none；只决定P4-03是否需要新状态/事务载体及rollback约束。

Dependency changes: none；Python/npm direct pins与两个lockfile保持逐字不变。

ADR impact: required；创建上述三份ADR，ID必须由启动时registry precheck分配，均不得改写accepted历史。若无法形成一致决定，本Task失败且P4-02不得启动。

State-machine impact: 决定ReplanRequest是否拥有独立状态机；不得在决定前预设pair，也不得改变PlanningRun/ScheduleVersion/ExportJob既有pair。

Error behavior: 未知版本/类型/状态/authority、重复ID不同fingerprint、stale base、跨plane、缺失provenance或任何Validator/contract失败均fail closed；不得把UNKNOWN写成INFEASIBLE、把Simulation值写成Production默认或把partial result写成成功。

Tests: 文档/ADR一致性和现有治理回归；新P4 Test ID仅保持PLANNED，不修改测试断言。

Test IDs: TEST-EXECUTION-EVENT-CONTRACT-001, TEST-REPLAN-REQUEST-CONTRACT-001, TEST-FREEZE-WINDOW-001, TEST-STABILITY-OBJECTIVE-001, TEST-CHANGE-REPORT-001

Benchmark impact: 只记录development correctness/quality/runtime/memory观察；不得建立Production capacity/SLA。若本Task不执行Benchmark，明确复用并冻结P2 XS/S/M baseline。

Simulation scenarios: 只定义五类连续异常的合同边界；不生成事件流或定量概率。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；Task-specific focused tests与machine command；完整registered pytest；必要的Frontend/Playwright/SCA/license；全部历史machine contracts与P2/P3 Gates；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-01-dynamic-replanning-contract-and-adr-baseline.md --check-diff --report build/traceability/TASK-P4-01-report.json`；`git diff --check`；相对Diff base的forbidden-scope核验。

Artifacts: `p4-contract-adr-report.v1`、Task diff report和exact provider artifact。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`；implementation与evidence-only closure必须分别绑定exact SHA的required `validate`（GitHub Actions app `15368`）、未过期artifact、Task/Diff base/Impact Rules/checks/issues一致性；失败run保留并以新corrective SHA重跑。

Completion conditions: 三份ADR accepted且互相一致；六项P4核心能力的owner/输入/输出/guard/rollback清晰；状态/Schema/migration影响可执行；full/diff docs治理与双提交provider成功；业务代码零差异。；文档/追踪/OPEN/SIM/risk/inventory一致；实现与evidence-only closure均经exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: 所有决定限于Simulation/development；不形成真实identity/approval/event authority、external integration、deployment、UAT或capacity/SLA。

P5 boundary: ADR不得引入secondary resource、batch、sequence setup、tool/fixture capacity、多工厂、alternative route、decomposition或rolling/hybrid策略。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: consumer形成前可通过新的superseding ADR撤回规划；不得删除或原地改写已accepted ADR。

## Completion evidence

保持空白直到本Task获得独立授权并执行。计划卡不是实现、测试PASS、provider evidence或Production声明。
