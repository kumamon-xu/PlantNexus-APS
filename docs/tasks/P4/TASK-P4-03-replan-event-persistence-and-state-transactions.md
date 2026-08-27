---
doc_id: TASK-P4-03
title: Replan Event Persistence and State Transactions
status: planned
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# TASK-P4-03 — Replan Event Persistence and State Transactions

Task batch role: phase-plan-member

Requirement IDs: REQ-007, REQ-008, REQ-009, REQ-013

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-OBS-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001, ENG-LOG-001

Depends on: TASK-P4-02

Start gate: 前序依赖全部`done`且其implementation/closure exact provider均成功；用户对TASK-P4-03另行明确授权；启动时`main=origin/main=remote main`、ahead/behind=`0/0`、working tree clean；把该时点完整40字符HEAD写入不可变Diff base；先将planned范围展开为逐字exact allow-list。

Goal: 以additive可逆migration与plane-scoped repository形成ExecutionEvent ledger、ReplanRequest/result/ChangeReport引用、幂等、CAS、append-only audit和经ADR批准的状态事务原语。

Non-goals: 不解释事件业务含义、不生成Snapshot、不调用Solver/Simulator、不自动publish/export，不形成Production database或exactly-once external delivery。

Inputs: P4-02 strict carriers、P3 ScheduleVersion/Audit repositories和现有0004 migration。

Diff base: not assigned; record the clean provider-verified 40-character HEAD only when this Task is separately authorized and activated

Files allowed to change: `backend/migrations/**`、`backend/app/infrastructure/**`、有界domain persistence state、限定unit/integration/migration tests、machine report/CI step及命中文档；以及`Documents to update`中的逐字路径。激活前必须把目录范围展开为exact paths。

Files forbidden to change: `schemas/**`、event fact projection、Planning/Solver/Validator、Simulator/scenarios、API/UI、dependencies/locks、P5+

Implementation steps: 设计0005 additive tables/index/unique/FK/check；实现append/replay/conflict/CAS/transaction ports；empty/populated upgrade/downgrade；plane isolation和audit rollback；输出机器证据。

Outputs: durable P4 storage primitives与`p4-replan-persistence-report.v1`。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `docs/domain/domain-model.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/architecture/data-authority.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/operations/observability-and-audit.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/governance/traceability-matrix.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/tasks/P4/TASK-P4-03-replan-event-persistence-and-state-transactions.md`

Documentation impact rationale: 本Task会改变其owner能力的合同/实现证据和追踪状态；所有Impact Rule必审文档须在激活前逐字确认，未修改者在Completion evidence逐项说明。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-STATE`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-007/008/009/013→storage/state transaction→TEST-P4-PERSISTENCE-001、TEST-IDEMPOTENCY、TEST-AUDIT-TRAIL-001、TEST-SIM-ISOLATION→persistence report/provider。

Contract impact: consumer-only；严格持久化P4-02 carriers与P4-01 state/transaction语义，禁止私建repository-only业务字段或第二权威。

Schema changes: none；只消费P4-02，不改Schema bytes。

Migration: required additive `0005`（最终名称在激活时冻结）；empty/populated upgrade/downgrade、数据损失说明和PostgreSQL/SQLite边界必测。

Dependency changes: none expected；沿用SQLAlchemy/Alembic exact lock。

ADR impact: none if conforming；新增outbox/external exactly-once/topology须先新ADR。

State-machine impact: 只实现ADR/P4-02批准的ReplanRequest pair；ExecutionEvent保持append-only fact，不用self-transition伪造replay。

Error behavior: 未知版本/类型/状态/authority、重复ID不同fingerprint、stale base、跨plane、缺失provenance或任何Validator/contract失败均fail closed；不得把UNKNOWN写成INFEASIBLE、把Simulation值写成Production默认或把partial result写成成功。

Tests: TEST-P4-PERSISTENCE-001、TEST-IDEMPOTENCY、TEST-AUDIT-TRAIL-001、TEST-STATE-TRANSITION-001、TEST-SIM-ISOLATION。

Test IDs: TEST-P4-PERSISTENCE-001, TEST-IDEMPOTENCY, TEST-AUDIT-TRAIL-001, TEST-STATE-TRANSITION-001, TEST-SIM-ISOLATION

Benchmark impact: 只记录development correctness/quality/runtime/memory观察；不得建立Production capacity/SLA。若本Task不执行Benchmark，明确复用并冻结P2 XS/S/M baseline。

Simulation scenarios: storage tests用有界synthetic events；不声称连续disruption或Production concurrency。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；Task-specific focused tests与machine command；完整registered pytest；必要的Frontend/Playwright/SCA/license；全部历史machine contracts与P2/P3 Gates；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-03-replan-event-persistence-and-state-transactions.md --check-diff --report build/traceability/TASK-P4-03-report.json`；`git diff --check`；相对Diff base的forbidden-scope核验。

Artifacts: `p4-replan-persistence-report.v1`、migration matrix、Task/provider evidence。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`；implementation与evidence-only closure必须分别绑定exact SHA的required `validate`（GitHub Actions app `15368`）、未过期artifact、Task/Diff base/Impact Rules/checks/issues一致性；失败run保留并以新corrective SHA重跑。

Completion conditions: migration/repository/state/idempotency/audit/rollback/plane isolation全部PASS；无业务投影或Solver调用；历史P3 rows不可变；exact provider闭环。；文档/追踪/OPEN/SIM/risk/inventory一致；实现与evidence-only closure均经exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: migration/repository证据不形成Production HA、backup/restore、真实actor/source、external integration或capacity/SLA。

P5 boundary: persistence不得预建P5 capability tables、columns、state或outbox topology。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: 停止入口后按可逆migration downgrade；已形成历史事件/请求不得删除，Production destructive downgrade仍禁止。

## Completion evidence

保持空白直到本Task获得独立授权并执行。计划卡不是实现、测试PASS、provider evidence或Production声明。
