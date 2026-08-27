---
doc_id: TASK-P4-04
title: ExecutionEvent Ingestion and Fact Projection
status: in_progress
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

Diff base: 3563bb236ce7b2c01794485110d4945a6e265105

Files allowed to change: `.github/workflows/ci.yml`、`backend/app/domain/execution_fact_projection.py`、`backend/app/importers/urgent_demand.py`、`backend/app/application/execution_fact_projection.py`、`backend/app/application/execution_fact_projection_check.py`、`backend/app/snapshots/projection.py`、`backend/app/infrastructure/execution_event_repository.py`、`backend/app/infrastructure/replan_repository.py`、`backend/app/infrastructure/snapshot_repository.py`、`backend/tests/unit/test_execution_fact_projection.py`、`backend/tests/property/test_execution_fact_projection_properties.py`、`backend/tests/integration/test_p4_execution_fact_projection.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`逐字列出的文档；这是激活时冻结的exact allow-list。

Files forbidden to change: Schema/migration/dependency、CP-SAT objective/strategy、Replan orchestration、Simulator/scenario、API/UI、P3 publication/export语义、P5+

Implementation steps: 验证event identity/source/time/order/plane；append exact replay；投影completed/running/delay/down/material/lock facts；Urgent Order引用标准输入；构建新Snapshot及hash；证明失败无副作用。

Outputs: deterministic event→fact→Snapshot pipeline与`p4-execution-fact-projection-report.v1`。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/milestones/P4-dynamic-replanning.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P4/TASK-P4-04-execution-event-ingestion-and-fact-projection.md`、`docs/contracts/README.md`、`docs/contracts/execution-events-and-replan-request.md`、`docs/contracts/planning-snapshot.md`、`docs/contracts/import-and-normalization.md`、`docs/core/glossary.md`、`docs/domain/domain-model.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/domain/error-model.md`、`docs/architecture/data-authority.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/architecture/repository-layout.md`、`docs/planning/replanning.md`、`docs/operations/README.md`、`docs/operations/observability-and-audit.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/operations/security.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`

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

Completion conditions: 全部11种已批准event（九类事实语义）的合法/拒绝/idempotent投影可重放；事实、source、hash与失败原子性完整；Urgent Order无捷径；exact provider闭环；文档/追踪/OPEN/SIM/risk/inventory一致；实现与evidence-only closure均经exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: synthetic event入口不形成真实MES source authority、external adapter、deployment、UAT或capacity/SLA。

P5 boundary: fact projection不得推断alternative route、secondary resource、batch、setup、tool/fixture或多工厂事实。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: 禁用event入口并保留ledger；错误事实用补偿event和新Snapshot纠正，绝不改写历史。

## Completion evidence

本地implementation candidate已形成Simulation-only strict event validation、ledger+audit ingress、pure full-prefix fact projection、new immutable Snapshot/checkpoint/audit、standard Urgent Import及exact replay。Snapshot中受hash保护的authority/stream/position/prefix lineage同时约束初始批次与连续第二批的immediate-predecessor lost-response replay，较旧或不一致base拒绝为stale。全部11种event均进入machine positive vectors；gap/reference/terminal/cross-plane、missing/mismatched urgent、stale base和故障注入均fail closed。SQLite Snapshot caller-transaction写入已改用现有方言感知savepoint，末端projection audit失败时新增Snapshot/checkpoint为0而已成功ingress ledger保留。

Task-specific 4 unit + 2 property + 4 migration-backed integration=`10 passed`，连同application boundary与CI contract的focused组合为`12 passed`；完整Backend为`654 passed`。Frontend为67 Vitest、主E2E与两轮Gate Chromium各12/12；locked sync、Ruff/Pyright、全部历史machine、P2 XS/P2 Gate/P3 Gate、SCA/license、Compose和Frontend/Package双build均PASS。Machine report `p4-execution-fact-projection-report.v1`为8/8、11 positive、4 negative、1 standard urgent、1 atomic rollback且`issues=[]`；Task governance report为54 changed paths、九个Impact Rules、27/27 expected/observed documents、19/19 checks与0 issues。完整required-equivalent本地回归已通过，implementation exact provider及artifact仍待执行，因此Task保持`in_progress`，这些local结果不构成provider evidence，也不启动TASK-P4-05。

## Activation evidence

2026-08-27用户明确授权执行TASK-P4-04。激活前确认`main=origin/main=remote main=3563bb236ce7b2c01794485110d4945a6e265105`、ahead/behind=`0/0`且working tree clean；TASK-P4-02/03均为`done`，其implementation/closure分别构成直接父子链`539cdbbdcdd406daba25b8d6b8caaa5133691e76`→`7b9bfc3069de5d3738e5cc5827d27d197ed3d226`与`60f8e8900ecab60f0d64311912ae27f09a4d002f`→`3563bb236ce7b2c01794485110d4945a6e265105`。四个required `validate`均由GitHub Actions app `15368`成功提供；artifact `9636892191`、`9637303205`、`9639720666`、`9640285305`均未过期，下载证据精确绑定Task、SHA、Diff base、Impact Rules、19/19 checks及`issues=[]`。

启动时冻结Git object：ExecutionEvent Schema=`ea7c6faad66ec09f3f463179b008203e82121adf`、PlanningSnapshot v2 Schema=`26c8f9f1d2fe870f95e4eccbb8896bfae7823623`、ImportPackage v2 Schema=`41fdcf020a89382ebf3c718aa1c66934abcbdc54`、`0005` migration=`cac0ab5b8607c08593f2f7fc3004a67437e9c8aa`、state registry=`cd9fedc3a9c4b521646b16ec5628b00d99d249f2`、`pyproject.toml`=`241ccc5d343c4527c4e7a419ae0c282fe29e6086`、`uv.lock`=`a04b1285e0e1da0d2a2341a879d5e8cc718522b7`。本Task只形成Simulation-only event ingress、确定性事实投影、新immutable Snapshot/checkpoint/audit、标准Urgent Import复用及机器证据；不形成ReplanRequest、freeze、OBJ-002、Solver/Validator、ChangeReport、ScheduleVersion、Simulator、API/UI、Production或P5+能力。
