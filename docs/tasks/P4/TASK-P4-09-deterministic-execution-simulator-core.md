---
doc_id: TASK-P4-09
title: Deterministic Execution Simulator Core
status: planned
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# TASK-P4-09 — Deterministic Execution Simulator Core

Task batch role: phase-plan-member

Requirement IDs: REQ-008, REQ-009, REQ-012, REQ-013

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-OBS-001, NFR-PER-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P4-02, TASK-P4-04

Start gate: 前序依赖全部`done`且其implementation/closure exact provider均成功；用户对TASK-P4-09另行明确授权；启动时`main=origin/main=remote main`、ahead/behind=`0/0`、working tree clean；把该时点完整40字符HEAD写入不可变Diff base；先将planned范围展开为逐字exact allow-list。

Goal: 实现以PUBLISHED ScheduleVersion、Scenario、seed、versioned disruption config和deterministic clock为输入的ExecutionSimulator核心，只输出标准ExecutionEvent stream并通过共同事件入口。

Non-goals: 不直接写计划数据库、不调用特殊Solver/Replan、不定义五类完整Gate、不提供Production telemetry或digital twin承诺。

Inputs: TASK-P4-01 accepted Execution Simulator Common-Path ADR、P4 event contract/ingestion、P0-P2 Scenario provenance和P3 PUBLISHED package。

Diff base: not assigned; record the clean provider-verified 40-character HEAD only when this Task is separately authorized and activated

Files allowed to change: `backend/app/simulation/execution/**`、有界scenario adapter、unit/property/simulation tests、machine report/CI及命中文档；以及`Documents to update`中的逐字路径。激活前必须把目录范围展开为exact paths。

Files forbidden to change: Schema/migration/dependency、Planning solver/application、API/UI、P3 repositories/publication/export、Production connector、P5+

Implementation steps: 固定virtual clock/queue/tie-break；输入版本/seed/hash/plane guard；输出canonical event stream；same-input replay；invalid config/source/Production reject；证明只经P4-04 public ingress。

Outputs: ExecutionSimulator core与`p4-execution-simulator-report.v1`。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `docs/simulation/README.md`、`docs/simulation/execution-simulator-and-disruptions.md`、`docs/simulation/scenario-spec-and-provenance.md`、`docs/simulation/scenario-library-and-matrix.md`、`docs/contracts/execution-events-and-replan-request.md`、`docs/architecture/simulation-first-dual-channel.md`、`docs/architecture/provenance-and-versioning.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/traceability-matrix.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/tasks/P4/TASK-P4-09-deterministic-execution-simulator-core.md`

Documentation impact rationale: 本Task会改变其owner能力的合同/实现证据和追踪状态；所有Impact Rule必审文档须在激活前逐字确认，未修改者在Completion evidence逐项说明。

Change-impact matrix rows reviewed: `IMPACT-SIM-EXECUTION`、`IMPACT-SIM-SCENARIO`、`IMPACT-TESTS`、`IMPACT-INFRA`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-008/009/012/013→Simulator core→TEST-EXECUTION-SIMULATOR-001、TEST-EXECUTION-EVENT-CONTRACT-001、TEST-SCENARIO-REPLAY、TEST-SIM-ISOLATION、TEST-PROPERTY→report。

Contract impact: consumer-only；实现P4-02 simulator manifest/event与既有Scenario provenance，不发明simulation-only event或state语义。

Schema changes: none；消费P4-02 manifest/event carriers。

Migration: none。

Dependency changes: none expected；使用标准库/既有依赖，任何新包先扩卡并exact lock/SCA/ADR review。

ADR impact: none；实现ADR-0001、ADR-0009及TASK-P4-01 accepted Execution Simulator Common-Path ADR。

State-machine impact: Simulator run status只使用P4-02 carrier；不推进业务ScheduleVersion/Replan状态。

Error behavior: 未知版本/类型/状态/authority、重复ID不同fingerprint、stale base、跨plane、缺失provenance或任何Validator/contract失败均fail closed；不得把UNKNOWN写成INFEASIBLE、把Simulation值写成Production默认或把partial result写成成功。

Tests: TEST-EXECUTION-SIMULATOR-001、TEST-EXECUTION-EVENT-CONTRACT-001、TEST-SCENARIO-REPLAY、TEST-SIM-ISOLATION、TEST-PROPERTY。

Test IDs: TEST-EXECUTION-SIMULATOR-001, TEST-EXECUTION-EVENT-CONTRACT-001, TEST-SCENARIO-REPLAY, TEST-SIM-ISOLATION, TEST-PROPERTY

Benchmark impact: 只记录development correctness/quality/runtime/memory观察；不得建立Production capacity/SLA。若本Task不执行Benchmark，明确复用并冻结P2 XS/S/M baseline。

Simulation scenarios: core仅覆盖clock/order/replay primitives；定量disruption由P4-10登记SIM_ASSUMPTION。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；Task-specific focused tests与machine command；完整registered pytest；必要的Frontend/Playwright/SCA/license；全部历史machine contracts与P2/P3 Gates；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-09-deterministic-execution-simulator-core.md --check-diff --report build/traceability/TASK-P4-09-report.json`；`git diff --check`；相对Diff base的forbidden-scope核验。

Artifacts: `p4-execution-simulator-report.v1`、event stream hashes、Task/provider artifact。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`；implementation与evidence-only closure必须分别绑定exact SHA的required `validate`（GitHub Actions app `15368`）、未过期artifact、Task/Diff base/Impact Rules/checks/issues一致性；失败run保留并以新corrective SHA重跑。

Completion conditions: same input/version/seed产生exact event bytes/hash；无数据库/Solver捷径；Production fail closed；exact provider闭环。；文档/追踪/OPEN/SIM/risk/inventory一致；实现与evidence-only closure均经exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: Simulator不形成Production twin、真实event source、external adapter、deployment、UAT或capacity/SLA。

P5 boundary: Simulator必须显式拒绝而非模拟近似P5 advanced capabilities。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: 停用Simulator入口并保留manifest/event evidence；不影响Production或P3数据。

## Completion evidence

保持空白直到本Task获得独立授权并执行。计划卡不是实现、测试PASS、provider evidence或Production声明。
