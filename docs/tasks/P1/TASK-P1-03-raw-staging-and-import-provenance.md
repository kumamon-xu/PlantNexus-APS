---
doc_id: TASK-P1-03
title: Raw Staging and Import Provenance
status: planned
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [9, 15, 62, 65, 66, 73, 93, 94, 95]
last_reviewed: 2026-08-19
---

# TASK-P1-03 — Raw Staging and Import Provenance

Requirement IDs: REQ-001, REQ-009

NFR / ENG IDs: NFR-TRC-001, NFR-REL-001, NFR-SEC-001, NFR-ISO-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-02

Goal: 建立可审计、幂等、与 canonical consumer 隔离的 Raw Staging 批次/行存储，保留 source/version/file hash/row location/received-at 和 synthetic provenance，但不解析或规范化业务值。

Inputs: Standard Import v2 contract、`docs/contracts/import-and-normalization.md`、worker reliability/idempotency baseline、ADR-0009。

Diff base: 进入 `in_progress` 前记录当时完整 40 字符 HEAD SHA

Files allowed to change: `backend/app/importers/__init__.py`、`backend/app/importers/contracts.py`、`backend/app/importers/staging.py`、`backend/app/importers/repository.py`、`backend/app/infrastructure/import_staging_repository.py`、`backend/migrations/versions/0002_raw_import_staging.py`、`backend/tests/unit/test_import_staging.py`、`backend/tests/integration/test_raw_import_staging.py`、`backend/tests/integration/test_migrations_and_infrastructure.py`、生成但不提交的 `build/traceability/TASK-P1-03-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: Schema、source Adapter/CSV/Excel reader、normalization/data validation/order expansion、Snapshot/Problem、Simulation、API、Celery business task、Solver、Production deployment。

Implementation steps: 定义 immutable staged batch/row与 repository protocol；以 content digest + source version + idempotency key 处理 exact replay/conflict；SQLAlchemy adapter和 Alembic reversible migration只保存原始值/定位/安全 metadata；同一 transaction原子落库，synthetic/production data plane不允许交叉；raw rows不得直接供 Problem/Solver 消费。

Outputs: Raw Staging contracts、repository、reversible migration、unit/integration/idempotency evidence。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/contracts/import-and-normalization.md`、`docs/architecture/data-authority.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/technology-stack.md`、`docs/domain/error-model.md`、`docs/operations/README.md`、`docs/operations/security.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/risk-register.md`、`docs/governance/document-inventory.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/P1/TASK-P1-03-raw-staging-and-import-provenance.md`。

Documentation impact rationale: 新增持久化、幂等、来源追踪和数据平面隔离行为，影响 Import、Infrastructure、Operations、Error 与追踪合同。

Change-impact matrix rows reviewed: `IMPACT-IMPORT`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-001/009、NFR-TRC/REL/SEC/ISO、ENG-ARCH/ERR/VER → TASK-P1-03 → TEST-IMPORT-STAGING-001/TEST-IDEMPOTENCY → migration、repository tests与 provenance artifact。

Schema changes: Business Schema none；关系表属于 internal persistence schema，不能冒充 Standard Import contract。

Migration: 新增 `0002_raw_import_staging`，必须在空库和含样例批次库验证 upgrade/downgrade；downgrade是破坏性开发回滚，执行时需记录数据影响。

Error behavior: digest/idempotency冲突、source/version缺失、跨 data-plane 引用、重复 row identity、事务失败以稳定错误返回；不保存或回显 Secret/异常原文。

Tests: `TEST-IMPORT-STAGING-001`、`TEST-IDEMPOTENCY`；batch/row immutable semantics、exact replay、conflict、transaction rollback、synthetic/production isolation、migration round-trip、raw-not-canonical boundary。

Benchmark impact: 只记录小型 synthetic staging 行数/耗时用于回归观察，不设生产阈值、不运行 Solver Benchmark。

Simulation scenarios: 使用显式 synthetic inline records；不修改正式 Scenario/Fixture，不将 staging 样例作为生产数据。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/importers backend/app/infrastructure/import_staging_repository.py backend/tests/unit/test_import_staging.py backend/tests/integration`；`uv run pyright backend/app/importers backend/app/infrastructure/import_staging_repository.py backend/tests/unit/test_import_staging.py backend/tests/integration`；`uv run pytest -q backend/tests/unit/test_import_staging.py backend/tests/integration/test_raw_import_staging.py backend/tests/integration/test_migrations_and_infrastructure.py`（该 integration suite必须实际执行空库及含样例批次的 upgrade/downgrade）；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-03-raw-staging-and-import-provenance.md --check-diff --report build/traceability/TASK-P1-03-report.json`；`git diff --check`。

Artifacts: migration revision、staging test result、traceability report；不提交真实源文件或 credentials。

Completion conditions: staged metadata字段齐全且 immutable；replay/conflict/rollback/isolation/migration tests PASS；raw rows无直接 Snapshot/Problem/Solver入口；文档/追踪与提交前后 governance PASS。

Explicitly excluded: 解析、字段映射、单位转换、业务校验、API/Worker 编排、真实 PostgreSQL 生产部署、Solver。

PROD_OPEN: OPEN-002/015 保持 OPEN；internal staging列不是外部接口或字段权威决定。

SIM_ASSUMPTIONS: 不新增工厂参数；测试批次显式 synthetic。

Rollback: 使用 migration downgrade与 repository feature removal；已被 Snapshot 引用的数据不得无审计删除，执行时需先确认开发测试数据范围。

## Completion evidence

执行时填写 migration revision/DB、changed paths、source counts、命令退出码、数据影响、文档与追踪结果。
