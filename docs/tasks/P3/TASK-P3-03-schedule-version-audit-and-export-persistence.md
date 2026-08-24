---
doc_id: TASK-P3-03
title: ScheduleVersion Audit and Export Persistence
status: planned
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [23, 33, 34, 35, 65, 66, 94]
last_reviewed: 2026-08-24
---

# TASK-P3-03 — ScheduleVersion Audit and Export Persistence

Task batch role: phase-plan-member

Requirement IDs: REQ-006, REQ-007, REQ-009

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-HUM-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P3-02

Start gate: TASK-P3-02=`done`且P3 Schema/provider evidence成功；用户明确授权；clean synchronized main；记录immutable Diff base；先验证现有`0001～0003` empty/populated upgrade/downgrade和Snapshot insert-only证据。

Goal: 以可逆migration和plane-scoped repositories持久化immutable ScheduleVersion、append-only audit event、publication idempotency/current reference及ExportJob状态/lease/attempt，不执行业务审批、发布或导出。

Non-goals: 不创建HTTP/UI/Celery业务task，不改变state pair，不连接外部storage/MES，不把repository write当作状态门成功。

Inputs: P3 Schemas、ADR-0002/0007/0009、TASK-P3-01 accepted Workspace ADR、state-machines.v1、现有SQLAlchemy/Alembic/job primitives。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `backend/migrations/versions/0004_schedule_versions_audit_export_jobs.py`、`backend/app/infrastructure/schedule_version_repository.py`、`backend/app/infrastructure/audit_repository.py`、`backend/app/infrastructure/export_job_repository.py`、`backend/app/infrastructure/publication_repository.py`、`backend/app/domain/state_machines/schedule_version.py`、`backend/app/domain/state_machines/export_job.py`、对应`__init__.py`、限定unit/integration/migration tests及`Documents to update`；实际路径激活前逐字固定。

Files forbidden to change: P3/P2 Schema bytes、Planning/Solver/Validator、`backend/app/application/**`、`backend/app/api/**`、`backend/app/exporters/**`、`backend/app/jobs/celery_app.py`、`frontend/**`、dependency/lock、workflow（除非仅接入本Taskmachine evidence且激活前扩卡）、P4 tables/events。

Implementation steps: 设计FK/unique/check/index/plane；实现insert/exact replay/conflict/read与no-update/delete；audit append-only；state transition CAS/transaction primitive；ExportJob claim/heartbeat/retry；publication/current reference idempotency；empty/populated migration replay和rollback边界。

Outputs: `0004` migration、四类repository、持久化状态原语与machine report。

Documentation impact: required

Documents to update: 三份state-machine文档、`docs/domain/domain-model.md`、`docs/domain/error-model.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/export-package.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/operations/README.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、全部governance/trace/impact/inventory必审文档、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: 首次ScheduleVersion/ExportJob/audit durable state与migration影响不可变性、重试、隔离、安全、回滚及状态证据。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-STATE`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-006/007/009→TASK-P3-03→TEST-SCHEDULE-VERSION-REPOSITORY-001/TEST-EXPORT-JOB-001/TEST-AUDIT-TRAIL-001/TEST-IDEMPOTENCY→migration/repository report。

Schema changes: none；只消费TASK-P3-02合同，发现字段缺口返回P3-02新版本而非DB私有默认。

Migration: required；upgrade/downgrade、含synthetic rows的destructive边界、PostgreSQL/SQLite差异、备份/恢复未形成边界必须明确；历史P1 tables不可破坏。

Dependency changes: none；复用locked SQLAlchemy/Alembic，`pyproject.toml/uv.lock`零变化。

ADR impact: implement ADR-0002/0007/0009及TASK-P3-01 accepted Workspace ADR；若需要outbox/topology/state语义新决定，迁移前停止并建ADR。

State-machine impact: 实现既有pair的持久化原语和终态immutability；不新增pair/self-transition，idempotent replay由key/version识别。

Error behavior: identity/content/state/version/plane/owner/lease冲突用稳定错误；事务失败原子回滚且不泄漏SQL/credentials；不把Job success写成Export成功。

Tests: TEST-SCHEDULE-VERSION-REPOSITORY-001、TEST-EXPORT-JOB-001、TEST-AUDIT-TRAIL-001、TEST-IDEMPOTENCY、TEST-SIM-ISOLATION；含并发/CAS、mutation拒绝、retry、rollback、migration round-trip。

Benchmark impact: 记录query/index/row count但不设Production SLA；大规模/真实PostgreSQL capacity仍OPEN-012/P7。

Simulation scenarios: 测试数据显式synthetic/plane-scoped；不将SQLite值或行数外推Production。

Acceptance commands: 定向unit/integration/migration pytest；`alembic upgrade head`/有界test harness round-trip；`uv sync --locked`、Ruff、Pyright、full registered pytest；full/diff docs治理；`git diff --check`；禁止范围diff。

Artifacts: migration/repository/idempotency/audit report、Task report、provider artifact。

Provider evidence: exact implementation/closure required `validate`/artifact；核对migration report、Task exact SHA/Impact/checks/issues及branch required context。

Completion conditions: repositories durable/plane-scoped/immutable/append-only/idempotent；migration reversible且历史表保留；负向/rollback/provider闭环；无业务状态动作、API/UI/外部副作用。

Failure handling: migration/transaction/immutability失败即停止TASK-P3-04，保留失败DB/报告；不得删除用户volume或重写历史migration。

Explicitly excluded: approval/publish/export execution、API/Frontend、real RBAC/MES/storage、P4 event/replan。

PROD_OPEN: OPEN-002/010/012/015保持OPEN；repository不提供真实角色、目标或容量。

SIM_ASSUMPTIONS: 只用显式synthetic rows；不新增工厂定量假设。

Rollback: 代码回退配合`0004` downgrade仅用于有备份的非生产/测试；已产生的ScheduleVersion/audit历史不得原地改写，Production迁移需另行runbook授权。
