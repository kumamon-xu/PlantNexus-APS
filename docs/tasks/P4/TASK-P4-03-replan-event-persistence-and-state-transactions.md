---
doc_id: TASK-P4-03
title: Replan Event Persistence and State Transactions
status: done
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

Diff base: 7b9bfc3069de5d3738e5cc5827d27d197ed3d226

Files allowed to change: `.github/workflows/ci.yml`、`backend/migrations/versions/0005_replan_event_persistence.py`、`backend/app/infrastructure/__init__.py`、`backend/app/infrastructure/replan_persistence.py`、`backend/app/infrastructure/execution_event_repository.py`、`backend/app/infrastructure/replan_repository.py`、`backend/app/infrastructure/replan_persistence_check.py`、`backend/tests/unit/test_replan_persistence.py`、`backend/tests/integration/test_p4_replan_persistence.py`、`backend/tests/integration/test_migrations_and_infrastructure.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`逐字列出的文档；这是激活时冻结的exact allow-list。

Files forbidden to change: `schemas/**`、event fact projection、Planning/Solver/Validator、Simulator/scenarios、API/UI、dependencies/locks、P5+

Implementation steps: 设计0005 additive tables/index/unique/FK/check；实现append/replay/conflict/CAS/transaction ports；empty/populated upgrade/downgrade；plane isolation和audit rollback；输出机器证据。

Outputs: durable P4 storage primitives与`p4-replan-persistence-report.v1`。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/milestones/P4-dynamic-replanning.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P4/TASK-P4-03-replan-event-persistence-and-state-transactions.md`、`docs/contracts/README.md`、`docs/contracts/execution-events-and-replan-request.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/domain/domain-model.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/adr/README.md`、`docs/architecture/data-authority.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/architecture/repository-layout.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/planning/replanning.md`、`docs/operations/README.md`、`docs/operations/observability-and-audit.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/operations/security.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`

Documentation impact rationale: 本Task会改变其owner能力的合同/实现证据和追踪状态；所有Impact Rule必审文档须在激活前逐字确认，未修改者在Completion evidence逐项说明。

Change-impact matrix rows reviewed: `IMPACT-STATE`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。Domain implementation路径已审查但不命中：ADR-0013禁止新增ReplanRequest状态，本Task无需修改`backend/app/domain/**`。

Traceability updates: REQ-007/008/009/013→storage/state transaction→TEST-P4-PERSISTENCE-001、TEST-IDEMPOTENCY、TEST-AUDIT-TRAIL-001、TEST-SIM-ISOLATION→persistence report/provider。

Contract impact: consumer-only；严格持久化P4-02 carriers与P4-01 state/transaction语义，禁止私建repository-only业务字段或第二权威。

Schema changes: none；只消费P4-02，不改Schema bytes。

Migration: required additive `0005_replan_event_persistence`；empty/populated upgrade/downgrade、数据损失说明和PostgreSQL/SQLite边界必测。

Dependency changes: none expected；沿用SQLAlchemy/Alembic exact lock。

ADR impact: none if conforming；新增outbox/external exactly-once/topology须先新ADR。

State-machine impact: ReplanRequest没有业务state或transition pair；本Task只实现projection checkpoint的operational CAS以及request→PlanningRun attempt→terminal result的append-only关系。ExecutionEvent保持append-only ledger，不用self-transition伪造replay；PlanningRun/ScheduleVersion/ExportJob既有state set/pair逐字不变。

Error behavior: 未知版本/类型/状态/authority、重复ID不同fingerprint、stale base、跨plane、缺失provenance或任何Validator/contract失败均fail closed；不得把UNKNOWN写成INFEASIBLE、把Simulation值写成Production默认或把partial result写成成功。

Tests: TEST-P4-PERSISTENCE-001、TEST-IDEMPOTENCY、TEST-AUDIT-TRAIL-001、TEST-STATE-TRANSITION-001、TEST-SIM-ISOLATION。

Test IDs: TEST-P4-PERSISTENCE-001, TEST-IDEMPOTENCY, TEST-AUDIT-TRAIL-001, TEST-STATE-TRANSITION-001, TEST-SIM-ISOLATION

Benchmark impact: 只记录development correctness/quality/runtime/memory观察；不得建立Production capacity/SLA。若本Task不执行Benchmark，明确复用并冻结P2 XS/S/M baseline。

Simulation scenarios: storage tests用有界synthetic events；不声称连续disruption或Production concurrency。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run pytest -q backend/tests/unit/test_replan_persistence.py backend/tests/integration/test_p4_replan_persistence.py backend/tests/integration/test_migrations_and_infrastructure.py backend/tests/integration/test_ci_contract.py`；`uv run python -m app.infrastructure.replan_persistence_check --root . --report build/validation/TASK-P4-03-replan-persistence.json`；完整registered pytest；Frontend Vitest/Playwright/SCA/license回归；全部历史machine contracts与P2/P3 Gates；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-03-replan-event-persistence-and-state-transactions.md --check-diff --report build/traceability/TASK-P4-03-report.json`；`git diff --check`；相对Diff base的forbidden-scope核验。

Artifacts: `p4-replan-persistence-report.v1`、migration matrix、Task/provider evidence。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`；implementation与evidence-only closure必须分别绑定exact SHA的required `validate`（GitHub Actions app `15368`）、未过期artifact、Task/Diff base/Impact Rules/checks/issues一致性；失败run保留并以新corrective SHA重跑。

Completion conditions: migration/repository/state/idempotency/audit/rollback/plane isolation全部PASS；无业务投影或Solver调用；历史P3 rows不可变；文档/追踪/OPEN/SIM/risk/inventory一致；实现与evidence-only closure均经exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: migration/repository证据不形成Production HA、backup/restore、真实actor/source、external integration或capacity/SLA。

P5 boundary: persistence不得预建P5 capability tables、columns、state或outbox topology。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: 停止入口后按可逆migration downgrade；已形成历史事件/请求不得删除，Production destructive downgrade仍禁止。

## Activation evidence

2026-08-27用户明确授权执行TASK-P4-03。激活前确认`main=origin/main=remote main=7b9bfc3069de5d3738e5cc5827d27d197ed3d226`、ahead/behind=`0/0`且working tree clean；TASK-P4-02=`done`，其implementation/closure为直接父子提交`539cdbbdcdd406daba25b8d6b8caaa5133691e76`→`7b9bfc3069de5d3738e5cc5827d27d197ed3d226`。两者required `validate`均由GitHub Actions app `15368`成功提供，未过期artifact `9636892191`/`9637303205`下载后共复核90 files/78 JSON、0 parse/SHA/top-level/check/issue异常，并精确绑定TASK-P4-02、Diff base `4026597ab1015b5ea3a89d241f0d12b5b481dee3`、87/0 paths、12 Impact Rules、19/19 checks及P4 machine 8/8。

启动时冻结P4 carrier Git object：ExecutionEvent=`ea7c6faad66ec09f3f463179b008203e82121adf`、ReplanRequest=`0c5cff65affcd0e79b3e7b1d84ff3e29c2b25dfe`、ChangeReport=`c895267d70dbad18ad78b446ee877b9a58aaca71`；state registry=`cd9fedc3a9c4b521646b16ec5628b00d99d249f2`、`0004`=`bd999449fd14f883c0945d7e19ab607afa4629c1`、`uv.lock`=`a04b1285e0e1da0d2a2341a879d5e8cc718522b7`。本Task只增加`0005_replan_event_persistence`、plane-scoped durable primitives、tests与单一required machine-evidence step；Schema/state pair/dependency/lock、业务projection/Solver/Simulator/API/UI及Production/P5+保持禁止。

## Completion evidence

本地实现与required-equivalent验收已完成：新增7张P4表、5个plane-scoped repository surfaces和9/9 `p4-replan-persistence-report.v1`；4 unit + 6 integration新用例、51项focused组合、643项完整Backend、Ruff/Pyright均PASS。Frontend以exact `npm@11.17.0`完成67 Vitest、主E2E及两轮Gate Chromium各12/12、SCA/license/build与两份machine report；默认npm `12.0.2`的首轮证据因版本不符被正确拒绝，未作为PASS。全部历史machine、P2 11/11、P3 14/14、Compose、Python build均PASS。

治理报告相对不可变base得到0 committed-range/52 working-tree paths、精确`IMPACT-STATE/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`六行、21/21 expected/observed documents、19/19 checks、0 issues；forbidden tracked/untracked均为0，P4 carrier/state registry/0004/uv.lock六个冻结Git object hash逐字一致。下方写回implementation exact provider事实；这不是Production/P5+声明，P4-04不得自动启动。

Implementation `60f8e8900ecab60f0d64311912ae27f09a4d002f`的required `validate` run/job=`33055784278`/`98462103078`由GitHub Actions app `15368`成功提供；branch protection仍精确要求`validate`/app `15368`且`strict=false`。Artifact `9639720666`未过期至2026-11-25T08:50:05Z，provider与下载ZIP digest均为`sha256:70cacbf0534403d3e114a245c96db28770884e1198b54e0b47689b5bd01c96b6`。下载的46 files/40 JSON精确绑定SHA、TASK-P4-03与Diff base，复现52 committed/0 working paths、六条Impact Rules、21/21 expected/observed documents、19/19 checks、`issues=[]`、P4 persistence 9/9、7 tables、5 repositories、8 DB guard rejects、1 Production reject、P3 row retention、P2/P3 Gate、Frontend/i18n及三轮12/12 Chromium；40份JSON共253个checks且0 parse/SHA/top-level/check/issue/gap异常。因此本evidence-only closure把Task标为`done`；closure自身必须post-push取得并核验exact required check/artifact，TASK-P4-04保持`planned`且不会自动启动。
