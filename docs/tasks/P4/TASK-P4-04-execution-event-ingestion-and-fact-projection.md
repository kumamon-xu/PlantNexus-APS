---
doc_id: TASK-P4-04
title: ExecutionEvent Ingestion and Fact Projection
status: planned
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# TASK-P4-04 — ExecutionEvent Ingestion and Fact Projection

Task batch role: phase-plan-member

Requirement IDs: REQ-002, REQ-003, REQ-008, REQ-009, REQ-013

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P4-02, TASK-P4-03

Start gate: 前序依赖全部`done`且其implementation/closure exact provider均成功；用户对TASK-P4-04另行明确授权；启动时`main=origin/main=remote main`、ahead/behind=`0/0`、working tree clean；把该时点完整40字符HEAD写入不可变Diff base；先将planned范围展开为逐字exact allow-list。

Goal: 将幂等ExecutionEvent通过权威事实层投影为新的immutable PlanningSnapshot，保持event/source/order/hash lineage并拒绝重复、冲突、乱序或非法事实；Urgent Order仍走标准Import/Validation入口。

Non-goals: 不直接修改既有Snapshot/ScheduleVersion、不决定freeze、不求解、不创建Replan结果、不运行Simulator。

Inputs: P4-02 event contract、P4-03 ledger、P1 common ingress/Snapshot和P2 fact/lock contracts。

Diff base: not assigned; record the clean provider-verified 40-character HEAD only when this Task is separately authorized and activated

Files allowed to change: 有界domain fact projection、application ingestion、snapshot integration、限定tests/CI machine evidence及命中文档；以及`Documents to update`中的逐字路径。激活前必须把目录范围展开为exact paths。

Files forbidden to change: Schema/migration/dependency、CP-SAT objective/strategy、Replan orchestration、Simulator/scenario、API/UI、P3 publication/export语义、P5+

Implementation steps: 验证event identity/source/time/order/plane；append exact replay；投影completed/running/delay/down/material/lock facts；Urgent Order引用标准输入；构建新Snapshot及hash；证明失败无副作用。

Outputs: deterministic event→fact→Snapshot pipeline与`p4-execution-fact-projection-report.v1`。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `docs/contracts/execution-events-and-replan-request.md`、`docs/contracts/planning-snapshot.md`、`docs/contracts/import-and-normalization.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/architecture/data-authority.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/provenance-and-versioning.md`、`docs/planning/replanning.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/traceability-matrix.md`、`docs/tasks/P4/TASK-P4-04-execution-event-ingestion-and-fact-projection.md`

Documentation impact rationale: 本Task会改变其owner能力的合同/实现证据和追踪状态；所有Impact Rule必审文档须在激活前逐字确认，未修改者在Completion evidence逐项说明。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-APPLICATION`、`IMPACT-IMPORT`、`IMPACT-SNAPSHOT`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-002/003/008/009/013→ExecutionEvent ledger/fact projection/Snapshot→TEST-EXECUTION-EVENT-CONTRACT-001、TEST-EXECUTION-FACT-PROJECTION-001、TEST-SNAPSHOT-REPLAY-001、TEST-IDEMPOTENCY/PROPERTY→machine report。

Contract impact: consumer-only；实现P4-02 ExecutionEvent与既有Snapshot/Import contracts，任何authority/order/fact语义缺口须停止并回到合同/ADR治理。

Schema changes: none；消费P4-02 carriers和既有Snapshot version，若字段不足立即停止并回到additive Schema Task。

Migration: none；只使用P4-03 repositories。

Dependency changes: none。

ADR impact: none if exact conformance to TASK-P4-01 accepted Event/Fact/Replan ADR；事件排序/authority或snapshot semantics变化须superseding ADR。

State-machine impact: 事件不推进ScheduleVersion；只记录事实与新Snapshot identity，ReplanRequest状态留给P4-08。

Error behavior: 未知版本/类型/状态/authority、重复ID不同fingerprint、stale base、跨plane、缺失provenance或任何Validator/contract失败均fail closed；不得把UNKNOWN写成INFEASIBLE、把Simulation值写成Production默认或把partial result写成成功。

Tests: TEST-EXECUTION-FACT-PROJECTION-001、TEST-SNAPSHOT-REPLAY-001、TEST-IDEMPOTENCY、TEST-PROPERTY、TEST-SIM-ISOLATION。

Test IDs: TEST-EXECUTION-FACT-PROJECTION-001, TEST-SNAPSHOT-REPLAY-001, TEST-IDEMPOTENCY, TEST-PROPERTY, TEST-SIM-ISOLATION

Benchmark impact: 只记录development correctness/quality/runtime/memory观察；不得建立Production capacity/SLA。若本Task不执行Benchmark，明确复用并冻结P2 XS/S/M baseline。

Simulation scenarios: 每类event有positive/negative/reordering/replay synthetic vectors；连续场景仍由P4-10。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；Task-specific focused tests与machine command；完整registered pytest；必要的Frontend/Playwright/SCA/license；全部历史machine contracts与P2/P3 Gates；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-04-execution-event-ingestion-and-fact-projection.md --check-diff --report build/traceability/TASK-P4-04-report.json`；`git diff --check`；相对Diff base的forbidden-scope核验。

Artifacts: `p4-execution-fact-projection-report.v1`、event/snapshot replay vectors、Task/provider artifact。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`；implementation与evidence-only closure必须分别绑定exact SHA的required `validate`（GitHub Actions app `15368`）、未过期artifact、Task/Diff base/Impact Rules/checks/issues一致性；失败run保留并以新corrective SHA重跑。

Completion conditions: 九类event的合法/拒绝/idempotent投影可重放；事实、source、hash与失败原子性完整；Urgent Order无捷径；exact provider闭环。；文档/追踪/OPEN/SIM/risk/inventory一致；实现与evidence-only closure均经exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: synthetic event入口不形成真实MES source authority、external adapter、deployment、UAT或capacity/SLA。

P5 boundary: fact projection不得推断alternative route、secondary resource、batch、setup、tool/fixture或多工厂事实。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: 禁用event入口并保留ledger；错误事实用补偿event和新Snapshot纠正，绝不改写历史。

## Completion evidence

保持空白直到本Task获得独立授权并执行。计划卡不是实现、测试PASS、provider evidence或Production声明。
